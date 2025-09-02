"""
AWS SDK Core Cleanup Utilities for AWS Ops Wheel v2 Integration Tests

This module provides direct AWS SDK operations for reliable test data cleanup,
bypassing API dependencies and authentication issues.
"""
import boto3
import time
from typing import List, Dict, Any, Optional, Tuple
from botocore.exceptions import ClientError
import json


class AWSCleanupConfig:
    """Configuration for AWS SDK cleanup operations"""
    
    def __init__(self, aws_region: str = 'us-west-2'):
        """Initialize configuration with default table names and settings"""
        self.aws_region = aws_region
        self.table_names = {
            'users': 'OpsWheelV2-Users-test',
            'wheel_groups': 'OpsWheelV2-WheelGroups-test',
            'wheels': 'OpsWheelV2-Wheels-test',
            'participants': 'OpsWheelV2-Participants-test'
        }
        self.batch_size = 25  # DynamoDB batch write limit
        self.retry_attempts = 3
        self.retry_delay = 1.0
        self.cognito_user_pool_id = None  # Auto-detected


class DynamoDBResourceCleaner:
    """Direct DynamoDB cleanup for registered resources"""
    
    def __init__(self, config: AWSCleanupConfig, dry_run: bool = False, debug: bool = False):
        """
        Initialize DynamoDB resource cleaner
        
        Args:
            config: Cleanup configuration
            dry_run: If True, only show what would be deleted
            debug: Enable debug logging
        """
        self.config = config
        self.dry_run = dry_run
        self.debug = debug
        
        # Create boto3 session using default credential chain
        session = boto3.Session(region_name=config.aws_region)
        self.dynamodb = session.client('dynamodb', region_name=config.aws_region)
        self.deleted_count = 0
        self.error_count = 0
    
    def _log(self, message: str):
        """Log debug message if debug is enabled"""
        if self.debug:
            print(f"[DYNAMODB-CLEANUP] {message}")
    
    def get_table_key_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get table key schema for proper deletions
        
        Args:
            table_name: DynamoDB table name
            
        Returns:
            Key schema information or None if error
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
            self._log(f"Error describing table {table_name}: {e}")
            return None
    
    def delete_items_by_keys(self, table_name: str, item_keys: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Delete specific items by their keys
        
        Args:
            table_name: DynamoDB table name
            item_keys: List of key dictionaries for items to delete
            
        Returns:
            Tuple of (successful_deletes, failed_deletes)
        """
        if not item_keys:
            return 0, 0
        
        self._log(f"Deleting {len(item_keys)} items from {table_name}")
        
        successful = 0
        failed = 0
        
        # Process items in batches of 25 (DynamoDB limit)
        for i in range(0, len(item_keys), self.config.batch_size):
            batch_keys = item_keys[i:i + self.config.batch_size]
            batch_num = (i // self.config.batch_size) + 1
            total_batches = (len(item_keys) + self.config.batch_size - 1) // self.config.batch_size
            
            if self.dry_run:
                self._log(f"DRY RUN - Would delete batch {batch_num}/{total_batches} ({len(batch_keys)} items)")
                successful += len(batch_keys)
                continue
            
            # Build delete requests
            delete_requests = []
            for key_dict in batch_keys:
                delete_requests.append({
                    'DeleteRequest': {
                        'Key': key_dict
                    }
                })
            
            # Execute batch delete with retry logic
            for attempt in range(self.config.retry_attempts):
                try:
                    response = self.dynamodb.batch_write_item(
                        RequestItems={
                            table_name: delete_requests
                        }
                    )
                    
                    # Handle unprocessed items
                    unprocessed = response.get('UnprocessedItems', {})
                    if unprocessed:
                        self._log(f"Batch {batch_num}: {len(unprocessed.get(table_name, []))} unprocessed items")
                        # For simplicity, count unprocessed as failed
                        processed_count = len(batch_keys) - len(unprocessed.get(table_name, []))
                    else:
                        processed_count = len(batch_keys)
                    
                    successful += processed_count
                    failed += len(batch_keys) - processed_count
                    
                    self._log(f"Batch {batch_num}/{total_batches} completed: {processed_count} deleted")
                    break
                    
                except ClientError as e:
                    if attempt < self.config.retry_attempts - 1:
                        self._log(f"Batch {batch_num} attempt {attempt + 1} failed, retrying: {e}")
                        time.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        self._log(f"Batch {batch_num} failed after {self.config.retry_attempts} attempts: {e}")
                        failed += len(batch_keys)
            
            # Small delay to avoid throttling
            if not self.dry_run:
                time.sleep(0.1)
        
        self.deleted_count += successful
        self.error_count += failed
        return successful, failed
    
    def delete_participants_by_ids(self, participant_ids: List[str]) -> Tuple[int, int]:
        """Delete participants by their IDs"""
        if not participant_ids:
            return 0, 0
        
        table_name = self.config.table_names['participants']
        
        # Get table key schema
        key_schema = self.get_table_key_schema(table_name)
        if not key_schema:
            return 0, len(participant_ids)
        
        # For participants: wheel_group_wheel_id (hash), participant_id (range)
        # We need to scan for participant_ids since we don't have wheel_group_wheel_id
        self._log(f"Looking up participants by IDs to get full keys")
        
        item_keys = []
        try:
            # Scan table for matching participant_ids
            paginator = self.dynamodb.get_paginator('scan')
            for page in paginator.paginate(TableName=table_name):
                for item in page.get('Items', []):
                    participant_id = item.get('participant_id', {}).get('S', '')
                    if participant_id in participant_ids:
                        # Extract full key for deletion
                        wheel_group_wheel_id = item.get('wheel_group_wheel_id', {}).get('S', '')
                        if wheel_group_wheel_id:
                            item_keys.append({
                                'wheel_group_wheel_id': {'S': wheel_group_wheel_id},
                                'participant_id': {'S': participant_id}
                            })
        
        except ClientError as e:
            self._log(f"Error scanning for participants: {e}")
            return 0, len(participant_ids)
        
        return self.delete_items_by_keys(table_name, item_keys)
    
    def delete_wheels_by_ids(self, wheel_ids: List[str]) -> Tuple[int, int]:
        """Delete wheels by their IDs"""
        if not wheel_ids:
            return 0, 0
        
        table_name = self.config.table_names['wheels']
        
        # Get table key schema
        key_schema = self.get_table_key_schema(table_name)
        if not key_schema:
            return 0, len(wheel_ids)
        
        # For wheels: wheel_group_id (hash), wheel_id (range)
        # We need to scan for wheel_ids since we don't have wheel_group_id
        self._log(f"Looking up wheels by IDs to get full keys")
        
        item_keys = []
        try:
            # Scan table for matching wheel_ids
            paginator = self.dynamodb.get_paginator('scan')
            for page in paginator.paginate(TableName=table_name):
                for item in page.get('Items', []):
                    wheel_id = item.get('wheel_id', {}).get('S', '')
                    if wheel_id in wheel_ids:
                        # Extract full key for deletion
                        wheel_group_id = item.get('wheel_group_id', {}).get('S', '')
                        if wheel_group_id:
                            item_keys.append({
                                'wheel_group_id': {'S': wheel_group_id},
                                'wheel_id': {'S': wheel_id}
                            })
        
        except ClientError as e:
            self._log(f"Error scanning for wheels: {e}")
            return 0, len(wheel_ids)
        
        return self.delete_items_by_keys(table_name, item_keys)
    
    def delete_wheel_groups_by_ids(self, wheel_group_ids: List[str]) -> Tuple[int, int]:
        """Delete wheel groups by their IDs"""
        if not wheel_group_ids:
            return 0, 0
        
        table_name = self.config.table_names['wheel_groups']
        
        # For wheel groups: wheel_group_id (hash key only)
        item_keys = [
            {'wheel_group_id': {'S': wg_id}} 
            for wg_id in wheel_group_ids
        ]
        
        return self.delete_items_by_keys(table_name, item_keys)
    
    def delete_users_by_ids(self, user_ids: List[str]) -> Tuple[int, int]:
        """Delete users by their IDs"""
        if not user_ids:
            return 0, 0
        
        table_name = self.config.table_names['users']
        
        # For users: user_id (hash key only)
        item_keys = [
            {'user_id': {'S': user_id}} 
            for user_id in user_ids
        ]
        
        return self.delete_items_by_keys(table_name, item_keys)


class CognitoResourceCleaner:
    """Direct Cognito cleanup for registered resources"""
    
    def __init__(self, config: AWSCleanupConfig, dry_run: bool = False, debug: bool = False):
        """
        Initialize Cognito resource cleaner
        
        Args:
            config: Cleanup configuration
            dry_run: If True, only show what would be deleted
            debug: Enable debug logging
        """
        self.config = config
        self.dry_run = dry_run
        self.debug = debug
        
        # Create boto3 session using default credential chain
        session = boto3.Session(region_name=config.aws_region)
        self.cognito = session.client('cognito-idp', region_name=config.aws_region)
        self.deleted_count = 0
        self.error_count = 0
    
    def _log(self, message: str):
        """Log debug message if debug is enabled"""
        if self.debug:
            print(f"[COGNITO-CLEANUP] {message}")
    
    def _get_user_pool_id(self) -> Optional[str]:
        """
        Get Cognito User Pool ID (cached after first call)
        
        Returns:
            Cognito User Pool ID or None if not found
        """
        if self.config.cognito_user_pool_id:
            return self.config.cognito_user_pool_id
        
        try:
            # Try to read from test config first
            config_path = '../config/config.json'
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                test_config = config.get('test', {})
                user_pool_id = test_config.get('cognito_user_pool_id')
                if user_pool_id:
                    self.config.cognito_user_pool_id = user_pool_id
                    return user_pool_id
            except Exception:
                pass
            
            # Auto-detect via AWS API
            response = self.cognito.list_user_pools(MaxResults=50)
            for pool in response.get('UserPools', []):
                pool_name = pool.get('Name', '')
                if 'test' in pool_name.lower() or 'ops-wheel' in pool_name.lower():
                    self.config.cognito_user_pool_id = pool['Id']
                    return pool['Id']
            
        except Exception as e:
            self._log(f"Could not auto-detect Cognito User Pool: {e}")
        
        return None
    
    def delete_users_by_usernames(self, usernames: List[str]) -> Tuple[int, int]:
        """
        Delete Cognito users by their usernames
        
        Args:
            usernames: List of usernames to delete
            
        Returns:
            Tuple of (successful_deletes, failed_deletes)
        """
        if not usernames:
            return 0, 0
        
        user_pool_id = self._get_user_pool_id()
        if not user_pool_id:
            self._log("No Cognito User Pool ID available - skipping Cognito cleanup")
            return 0, len(usernames)
        
        self._log(f"Deleting {len(usernames)} Cognito users from pool {user_pool_id}")
        
        successful = 0
        failed = 0
        
        for i, username in enumerate(usernames):
            if self.dry_run:
                self._log(f"DRY RUN - Would delete user {i+1}/{len(usernames)}: {username}")
                successful += 1
                continue
            
            # Delete user with retry logic
            for attempt in range(self.config.retry_attempts):
                try:
                    self.cognito.admin_delete_user(
                        UserPoolId=user_pool_id,
                        Username=username
                    )
                    
                    self._log(f"Deleted user {i+1}/{len(usernames)}: {username}")
                    successful += 1
                    break
                    
                except ClientError as e:
                    if attempt < self.config.retry_attempts - 1:
                        self._log(f"User {username} attempt {attempt + 1} failed, retrying: {e}")
                        time.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        self._log(f"User {username} failed after {self.config.retry_attempts} attempts: {e}")
                        failed += 1
            
            # Small delay to avoid throttling
            if not self.dry_run:
                time.sleep(0.1)
        
        self.deleted_count += successful
        self.error_count += failed
        return successful, failed


class AWSResourceCleanupOrchestrator:
    """Orchestrates cleanup of all AWS resources"""
    
    def __init__(self, aws_region: str = 'us-west-2', dry_run: bool = False, debug: bool = False):
        """
        Initialize cleanup orchestrator
        
        Args:
            aws_region: AWS region for boto3 clients
            dry_run: If True, only show what would be deleted
            debug: Enable debug logging
        """
        self.config = AWSCleanupConfig(aws_region=aws_region)
        self.dry_run = dry_run
        self.debug = debug
        
        # Initialize specialized cleaners
        self.dynamodb_cleaner = DynamoDBResourceCleaner(self.config, dry_run, debug)
        self.cognito_cleaner = CognitoResourceCleaner(self.config, dry_run, debug)
    
    def cleanup_registered_resources(self, 
                                   participant_ids: List[str] = None,
                                   wheel_ids: List[str] = None, 
                                   wheel_group_ids: List[str] = None,
                                   user_ids: List[str] = None,
                                   cognito_usernames: List[str] = None) -> Dict[str, Any]:
        """
        Clean up all registered resources in proper dependency order
        
        Args:
            participant_ids: List of participant IDs to delete
            wheel_ids: List of wheel IDs to delete
            wheel_group_ids: List of wheel group IDs to delete  
            user_ids: List of user IDs to delete
            cognito_usernames: List of Cognito usernames to delete
            
        Returns:
            Dictionary with cleanup results
        """
        results = {
            'total_successful': 0,
            'total_failed': 0,
            'details': {}
        }
        
        # Clean up in reverse dependency order
        
        # 1. Participants (no dependencies)
        if participant_ids:
            successful, failed = self.dynamodb_cleaner.delete_participants_by_ids(participant_ids)
            results['details']['participants'] = {'successful': successful, 'failed': failed}
            results['total_successful'] += successful
            results['total_failed'] += failed
        
        # 2. Wheels (depend on participants being cleaned up)
        if wheel_ids:
            successful, failed = self.dynamodb_cleaner.delete_wheels_by_ids(wheel_ids)
            results['details']['wheels'] = {'successful': successful, 'failed': failed}
            results['total_successful'] += successful
            results['total_failed'] += failed
        
        # 3. Wheel groups (depend on wheels being cleaned up)
        if wheel_group_ids:
            successful, failed = self.dynamodb_cleaner.delete_wheel_groups_by_ids(wheel_group_ids)
            results['details']['wheel_groups'] = {'successful': successful, 'failed': failed}
            results['total_successful'] += successful
            results['total_failed'] += failed
        
        # 4. Users (can be cleaned up independently)
        if user_ids:
            successful, failed = self.dynamodb_cleaner.delete_users_by_ids(user_ids)
            results['details']['users'] = {'successful': successful, 'failed': failed}
            results['total_successful'] += successful
            results['total_failed'] += failed
        
        # 5. Cognito users (independent cleanup)
        if cognito_usernames:
            successful, failed = self.cognito_cleaner.delete_users_by_usernames(cognito_usernames)
            results['details']['cognito_users'] = {'successful': successful, 'failed': failed}
            results['total_successful'] += successful
            results['total_failed'] += failed
        
        return results
