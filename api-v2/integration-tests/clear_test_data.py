#!/usr/bin/env python3
"""
Direct DynamoDB Test Data Cleanup Script

This script bypasses the broken API cleanup system and directly clears
all test data from DynamoDB tables using AWS SDK.

Usage:
    python clear_test_data.py [--dry-run] [--table TABLE_NAME]
"""
import boto3
import argparse
import sys
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
import time


class CognitoCleaner:
    """Direct Cognito User Pool cleaner"""
    
    def __init__(self, user_pool_id: str, dry_run: bool = False):
        """
        Initialize Cognito cleaner
        
        Args:
            user_pool_id: Cognito User Pool ID
            dry_run: If True, only show what would be deleted without actually deleting
        """
        self.cognito = boto3.client('cognito-idp', region_name='us-west-2')
        self.user_pool_id = user_pool_id
        self.dry_run = dry_run
        self.deleted_count = 0
        self.error_count = 0
    
    def list_test_users(self) -> List[Dict[str, Any]]:
        """
        List all test users in the Cognito User Pool
        
        Returns:
            List of test user records
        """
        test_users = []
        
        try:
            print(f"👥 Scanning Cognito User Pool: {self.user_pool_id}")
            
            # Use paginator to handle large user pools
            paginator = self.cognito.get_paginator('list_users')
            
            for page in paginator.paginate(UserPoolId=self.user_pool_id):
                users = page.get('Users', [])
                
                for user in users:
                    # Check if this is a test user
                    email = None
                    username = user.get('Username', '')
                    
                    # Find email attribute
                    for attr in user.get('Attributes', []):
                        if attr.get('Name') == 'email':
                            email = attr.get('Value', '')
                            break
                    
                    # Check if this is a test user based on email or username patterns
                    is_test_user = (
                        email and '@integrationtest.example.com' in email or
                        'admin-17562' in username or  # Timestamp pattern in usernames
                        'integtest' in username.lower() or
                        'testuser' in username.lower()
                    )
                    
                    if is_test_user:
                        test_users.append({
                            'username': username,
                            'email': email,
                            'status': user.get('UserStatus', ''),
                            'created': user.get('UserCreateDate', ''),
                            'user_record': user
                        })
                
                print(f"  👥 Scanned {len(users)} users (total test users: {len(test_users)})")
            
            print(f"✅ Found {len(test_users)} test users")
            return test_users
            
        except ClientError as e:
            print(f"❌ Error listing Cognito users: {e}")
            return []
    
    def delete_users_batch(self, users: List[Dict[str, Any]]) -> bool:
        """
        Delete Cognito users (one at a time, no batch API available)
        
        Args:
            users: List of user records to delete
            
        Returns:
            True if all deletions successful
        """
        print(f"🗑️  Deleting {len(users)} Cognito users...")
        
        success = True
        
        for i, user in enumerate(users):
            username = user['username']
            email = user['email']
            
            if self.dry_run:
                print(f"  🧪 DRY RUN - Would delete user {i+1}/{len(users)}: {username} ({email})")
                continue
            
            try:
                # Delete the user
                self.cognito.admin_delete_user(
                    UserPoolId=self.user_pool_id,
                    Username=username
                )
                
                print(f"  ✅ Deleted user {i+1}/{len(users)}: {username} ({email})")
                self.deleted_count += 1
                
                # Small delay to avoid throttling
                time.sleep(0.1)
                
            except ClientError as e:
                print(f"  ❌ Error deleting user {username}: {e}")
                self.error_count += 1
                success = False
        
        return success
    
    def clear_test_users(self) -> bool:
        """
        Clear all test users from Cognito
        
        Returns:
            True if successful
        """
        print(f"\n👥 Clearing Cognito test users")
        print("=" * 50)
        
        # Get test users
        test_users = self.list_test_users()
        if not test_users:
            print("✅ No test users found in Cognito")
            return True
        
        # Show sample of users to be deleted
        print(f"📋 Sample users to be deleted:")
        for i, user in enumerate(test_users[:5]):
            print(f"  • {user['username']} ({user['email']})")
        if len(test_users) > 5:
            print(f"  ... and {len(test_users) - 5} more")
        
        # Delete users
        success = self.delete_users_batch(test_users)
        
        if success and not self.dry_run:
            print(f"✅ Successfully cleared {len(test_users)} Cognito users")
        elif self.dry_run:
            print(f"🧪 DRY RUN: Would have deleted {len(test_users)} Cognito users")
        
        return success


class DynamoDBCleaner:
    """Direct DynamoDB table cleaner"""
    
    def __init__(self, dry_run: bool = False, auto_confirm: bool = False):
        """
        Initialize cleaner
        
        Args:
            dry_run: If True, only show what would be deleted without actually deleting
            auto_confirm: If True, automatically confirm deletions without prompting
        """
        self.dynamodb = boto3.client('dynamodb', region_name='us-west-2')
        self.dry_run = dry_run
        self.auto_confirm = auto_confirm
        self.deleted_count = 0
        self.error_count = 0
    
    def get_table_key_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get table key schema for proper deletions
        
        Args:
            table_name: DynamoDB table name
            
        Returns:
            Key schema information
        """
        try:
            response = self.dynamodb.describe_table(TableName=table_name)
            key_schema = response['Table']['KeySchema']
            
            # Extract hash and range key names
            hash_key = None
            range_key = None
            
            for key in key_schema:
                if key['KeyType'] == 'HASH':
                    hash_key = key['AttributeName']
                elif key['KeyType'] == 'RANGE':
                    range_key = key['AttributeName']
            
            return {
                'hash_key': hash_key,
                'range_key': range_key,
                'key_schema': key_schema
            }
            
        except ClientError as e:
            print(f"❌ Error describing table {table_name}: {e}")
            return None
    
    def scan_table_items(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Scan all items from a table
        
        Args:
            table_name: DynamoDB table name
            
        Returns:
            List of all items in the table
        """
        items = []
        
        try:
            # Use paginator to handle large tables
            paginator = self.dynamodb.get_paginator('scan')
            
            print(f"📊 Scanning table: {table_name}")
            
            for page in paginator.paginate(TableName=table_name):
                page_items = page.get('Items', [])
                items.extend(page_items)
                print(f"  📋 Scanned {len(page_items)} items (total: {len(items)})")
            
            print(f"✅ Scan complete: {len(items)} total items found")
            return items
            
        except ClientError as e:
            print(f"❌ Error scanning table {table_name}: {e}")
            return []
    
    def delete_items_batch(self, table_name: str, items: List[Dict[str, Any]], 
                          key_schema: Dict[str, Any]) -> bool:
        """
        Delete items in batches of 25 (DynamoDB limit)
        
        Args:
            table_name: DynamoDB table name
            items: List of items to delete
            key_schema: Table key schema information
            
        Returns:
            True if all deletions successful
        """
        hash_key = key_schema['hash_key']
        range_key = key_schema['range_key']
        
        # Process items in batches of 25
        batch_size = 25
        total_batches = (len(items) + batch_size - 1) // batch_size
        
        print(f"🗑️  Deleting {len(items)} items in {total_batches} batches...")
        
        success = True
        
        for i in range(0, len(items), batch_size):
            batch_items = items[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            if self.dry_run:
                print(f"  🧪 DRY RUN - Would delete batch {batch_num}/{total_batches} ({len(batch_items)} items)")
                continue
            
            # Build delete requests
            delete_requests = []
            
            for item in batch_items:
                # Extract key attributes for deletion
                key = {hash_key: item[hash_key]}
                if range_key and range_key in item:
                    key[range_key] = item[range_key]
                
                delete_requests.append({
                    'DeleteRequest': {
                        'Key': key
                    }
                })
            
            try:
                # Execute batch delete
                response = self.dynamodb.batch_write_item(
                    RequestItems={
                        table_name: delete_requests
                    }
                )
                
                # Handle unprocessed items
                unprocessed = response.get('UnprocessedItems', {})
                if unprocessed:
                    print(f"  ⚠️  Batch {batch_num}: {len(unprocessed.get(table_name, []))} unprocessed items")
                    # Could retry unprocessed items here if needed
                else:
                    print(f"  ✅ Batch {batch_num}/{total_batches} deleted successfully ({len(batch_items)} items)")
                
                self.deleted_count += len(batch_items) - len(unprocessed.get(table_name, []))
                
                # Small delay to avoid throttling
                time.sleep(0.1)
                
            except ClientError as e:
                print(f"  ❌ Error deleting batch {batch_num}: {e}")
                self.error_count += len(batch_items)
                success = False
        
        return success
    
    def clear_table(self, table_name: str) -> bool:
        """
        Clear all data from a specific table
        
        Args:
            table_name: DynamoDB table name
            
        Returns:
            True if successful
        """
        print(f"\n🧹 Clearing table: {table_name}")
        print("=" * 50)
        
        # Get table key schema
        key_schema = self.get_table_key_schema(table_name)
        if not key_schema:
            return False
        
        print(f"🔑 Table keys: hash={key_schema['hash_key']}, range={key_schema['range_key']}")
        
        # Scan all items
        items = self.scan_table_items(table_name)
        if not items:
            print("✅ Table is already empty")
            return True
        
        # Delete all items
        success = self.delete_items_batch(table_name, items, key_schema)
        
        if success and not self.dry_run:
            print(f"✅ Successfully cleared {len(items)} items from {table_name}")
        elif self.dry_run:
            print(f"🧪 DRY RUN: Would have deleted {len(items)} items from {table_name}")
        
        return success
    
    def get_test_tables(self) -> List[str]:
        """
        Get list of test DynamoDB tables
        
        Returns:
            List of test table names
        """
        try:
            response = self.dynamodb.list_tables()
            all_tables = response['TableNames']
            
            # Filter for test tables
            test_tables = [table for table in all_tables if '-test' in table]
            
            print(f"📋 Found {len(test_tables)} test tables:")
            for table in test_tables:
                print(f"  • {table}")
            
            return test_tables
            
        except ClientError as e:
            print(f"❌ Error listing tables: {e}")
            return []
    
    def clear_all_test_tables(self) -> bool:
        """
        Clear all test tables
        
        Returns:
            True if all successful
        """
        test_tables = self.get_test_tables()
        if not test_tables:
            print("ℹ️  No test tables found")
            return True
        
        print(f"\n🧹 Clearing {len(test_tables)} test tables...")
        
        if self.dry_run:
            print("🧪 DRY RUN MODE - No actual deletions will be performed\n")
        else:
            print("⚠️  LIVE MODE - Data will be permanently deleted\n")
            
            # Safety confirmation for live mode (unless auto-confirm is enabled)
            if not self.auto_confirm:
                confirm = input("Are you sure you want to delete all test data? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("❌ Cancelled by user")
                    return False
            else:
                print("🤖 Auto-confirming deletion (automated mode)")
        
        success = True
        
        for table_name in test_tables:
            table_success = self.clear_table(table_name)
            if not table_success:
                success = False
        
        # Summary
        print(f"\n📊 SUMMARY:")
        print("=" * 50)
        if self.dry_run:
            print(f"🧪 DRY RUN completed for {len(test_tables)} tables")
        else:
            print(f"✅ Deleted items: {self.deleted_count}")
            print(f"❌ Failed items: {self.error_count}")
            print(f"📋 Tables processed: {len(test_tables)}")
            
            if success and self.error_count == 0:
                print("🎉 All test data cleared successfully!")
            else:
                print("⚠️  Some errors occurred during cleanup")
        
        return success


def get_cognito_user_pool_id() -> Optional[str]:
    """
    Get Cognito User Pool ID from test configuration
    
    Returns:
        Cognito User Pool ID or None if not found
    """
    try:
        # Try to read from test config file
        import json
        config_path = 'config/config.json'
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Look for user pool ID in test environment config
        test_config = config.get('test', {})
        user_pool_id = test_config.get('cognito_user_pool_id')
        
        if user_pool_id:
            return user_pool_id
        
        # Also try looking in CloudFormation outputs format
        cognito_config = test_config.get('cognito', {})
        if cognito_config.get('user_pool_id'):
            return cognito_config['user_pool_id']
            
    except Exception as e:
        print(f"⚠️  Could not read Cognito config from test config: {e}")
    
    # Try to find via AWS CLI - list user pools and find test one
    try:
        cognito = boto3.client('cognito-idp', region_name='us-west-2')
        response = cognito.list_user_pools(MaxResults=50)
        
        for pool in response.get('UserPools', []):
            pool_name = pool.get('Name', '')
            if 'test' in pool_name.lower() or 'ops-wheel' in pool_name.lower():
                return pool['Id']
                
    except Exception as e:
        print(f"⚠️  Could not auto-detect Cognito User Pool: {e}")
    
    return None


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Clear AWS Ops Wheel test data from DynamoDB and Cognito')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--table', type=str, 
                       help='Clear specific DynamoDB table only')
    parser.add_argument('--dynamodb-only', action='store_true',
                       help='Clear only DynamoDB tables (skip Cognito)')
    parser.add_argument('--cognito-only', action='store_true',
                       help='Clear only Cognito users (skip DynamoDB)')
    parser.add_argument('--user-pool-id', type=str,
                       help='Cognito User Pool ID (auto-detected if not provided)')
    parser.add_argument('--auto-confirm', action='store_true',
                       help='Automatically confirm deletion without prompting (for automated use)')
    
    args = parser.parse_args()
    
    print("🧹 AWS Ops Wheel Test Data Cleaner")
    print("=" * 50)
    print("🔄 Clears both DynamoDB tables AND Cognito users")
    print()
    
    overall_success = True
    
    # Handle specific table cleanup
    if args.table:
        print("📋 Single table mode - clearing DynamoDB table only")
        dynamodb_cleaner = DynamoDBCleaner(dry_run=args.dry_run)
        success = dynamodb_cleaner.clear_table(args.table)
        sys.exit(0 if success else 1)
    
    # DynamoDB cleanup
    if not args.cognito_only:
        print("🗄️  PHASE 1: DynamoDB Cleanup")
        print("=" * 50)
        
        dynamodb_cleaner = DynamoDBCleaner(dry_run=args.dry_run, auto_confirm=args.auto_confirm)
        dynamodb_success = dynamodb_cleaner.clear_all_test_tables()
        
        if not dynamodb_success:
            overall_success = False
            print("❌ DynamoDB cleanup had errors")
        else:
            print("✅ DynamoDB cleanup completed successfully")
    
    # Cognito cleanup
    if not args.dynamodb_only:
        print("\n👥 PHASE 2: Cognito Cleanup")
        print("=" * 50)
        
        # Get User Pool ID
        user_pool_id = args.user_pool_id or get_cognito_user_pool_id()
        
        if not user_pool_id:
            print("❌ Could not determine Cognito User Pool ID")
            print("💡 Please provide it with --user-pool-id parameter")
            print("   You can find it in AWS Console > Cognito > User Pools")
            overall_success = False
        else:
            print(f"🎯 Using Cognito User Pool: {user_pool_id}")
            
            cognito_cleaner = CognitoCleaner(user_pool_id=user_pool_id, dry_run=args.dry_run)
            cognito_success = cognito_cleaner.clear_test_users()
            
            if not cognito_success:
                overall_success = False
                print("❌ Cognito cleanup had errors")
            else:
                print("✅ Cognito cleanup completed successfully")
    
    # Final summary
    print(f"\n🎯 FINAL SUMMARY")
    print("=" * 50)
    
    if args.dry_run:
        print("🧪 DRY RUN MODE - No actual deletions performed")
        print("✨ Run without --dry-run to perform actual cleanup")
    else:
        if overall_success:
            print("🎉 ALL CLEANUP COMPLETED SUCCESSFULLY!")
            print("✨ Your test environment is now clean")
        else:
            print("⚠️  CLEANUP COMPLETED WITH ERRORS")
            print("💡 Check the output above for details")
    
    sys.exit(0 if overall_success else 1)


if __name__ == '__main__':
    main()
