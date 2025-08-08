#!/usr/bin/env python3
"""
Test script to verify user lookup in DynamoDB for AWS Ops Wheel v2
This will help debug the AuthorizerConfigurationException
"""

import boto3
import json
from boto3.dynamodb.conditions import Key

def test_user_lookup():
    """Test user lookup in DynamoDB Users table"""
    
    # Configuration - update these values based on your deployment
    REGION = 'us-west-2'
    ENVIRONMENT = 'dev'
    USER_EMAIL = 'user1@tenant-alpha.com'
    
    # Table names based on your CloudFormation naming convention
    USERS_TABLE = f'OpsWheelV2-Users-{ENVIRONMENT}'
    TENANTS_TABLE = f'OpsWheelV2-Tenants-{ENVIRONMENT}'
    
    print("=== AWS Ops Wheel v2 - User Lookup Test ===")
    print(f"Region: {REGION}")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Testing user: {USER_EMAIL}")
    print(f"Users table: {USERS_TABLE}")
    print(f"Tenants table: {TENANTS_TABLE}")
    print()
    
    try:
        # Initialize DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        users_table = dynamodb.Table(USERS_TABLE)
        tenants_table = dynamodb.Table(TENANTS_TABLE)
        
        # Test 1: Check if tables exist
        print("1. Checking if tables exist...")
        try:
            users_response = users_table.table_status
            tenants_response = tenants_table.table_status
            print(f"   ✓ Users table exists: {USERS_TABLE} (Status: {users_response})")
            print(f"   ✓ Tenants table exists: {TENANTS_TABLE} (Status: {tenants_response})")
        except Exception as e:
            print(f"   ✗ Error checking tables: {e}")
            return False
        
        # Test 2: Check if email-index GSI exists
        print("\n2. Checking Global Secondary Indexes...")
        try:
            table_description = users_table.meta.client.describe_table(TableName=USERS_TABLE)
            gsis = table_description.get('Table', {}).get('GlobalSecondaryIndexes', [])
            email_index_exists = any(gsi['IndexName'] == 'email-index' for gsi in gsis)
            
            if email_index_exists:
                print("   ✓ email-index GSI exists")
            else:
                print("   ✗ email-index GSI does not exist!")
                print("   Available GSIs:")
                for gsi in gsis:
                    print(f"     - {gsi['IndexName']}")
                return False
        except Exception as e:
            print(f"   ✗ Error checking GSIs: {e}")
            return False
            
        # Test 3: Try to lookup the user
        print(f"\n3. Looking up user: {USER_EMAIL}")
        try:
            response = users_table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(USER_EMAIL)
            )
            
            users = response.get('Items', [])
            if users:
                user = users[0]
                print(f"   ✓ User found!")
                print(f"   User ID: {user.get('user_id')}")
                print(f"   Email: {user.get('email')}")
                print(f"   Tenant ID: {user.get('tenant_id')}")
                print(f"   Role: {user.get('role')}")
                print(f"   Created: {user.get('created_at')}")
                
                # Test 4: Lookup tenant information
                tenant_id = user.get('tenant_id')
                if tenant_id:
                    print(f"\n4. Looking up tenant: {tenant_id}")
                    tenant_response = tenants_table.get_item(Key={'tenant_id': tenant_id})
                    if 'Item' in tenant_response:
                        tenant = tenant_response['Item']
                        print(f"   ✓ Tenant found!")
                        print(f"   Tenant Name: {tenant.get('tenant_name')}")
                        print(f"   Domain: {tenant.get('domain')}")
                        print(f"   Status: {tenant.get('status')}")
                    else:
                        print(f"   ✗ Tenant not found: {tenant_id}")
                        return False
                else:
                    print("   ✗ User has no tenant_id")
                    return False
                
                print(f"\n✅ SUCCESS: User lookup should work correctly!")
                return True
            else:
                print(f"   ✗ User not found: {USER_EMAIL}")
                print(f"\n4. Checking all users in the table...")
                
                # Scan for all users to see what's in the table
                scan_response = users_table.scan(Limit=10)
                all_users = scan_response.get('Items', [])
                
                if all_users:
                    print(f"   Found {len(all_users)} users in table:")
                    for u in all_users[:5]:  # Show first 5 users
                        print(f"     - {u.get('email', 'no-email')} (ID: {u.get('user_id', 'no-id')})")
                else:
                    print("   No users found in the table")
                
                return False
                
        except Exception as e:
            print(f"   ✗ Error querying user: {e}")
            return False
            
    except Exception as e:
        print(f"✗ General error: {e}")
        return False

def create_test_user():
    """Create test user data for testing"""
    
    REGION = 'us-west-2'
    ENVIRONMENT = 'dev'
    
    # Test data
    tenant_data = {
        'tenant_id': 'tenant-alpha',
        'tenant_name': 'Alpha Tenant',
        'domain': 'tenant-alpha.com',
        'status': 'active',
        'created_at': '2025-01-01T00:00:00Z',
        'subscription_plan': 'basic'
    }
    
    user_data = {
        'user_id': '4871f340-a071-70fd-f64e-67b3af08f459',  # From JWT
        'email': 'user1@tenant-alpha.com',
        'tenant_id': 'tenant-alpha', 
        'role': 'USER',
        'created_at': '2025-01-01T00:00:00Z',
        'name': 'User One Alpha',
        'status': 'active'
    }
    
    USERS_TABLE = f'OpsWheelV2-Users-{ENVIRONMENT}'
    TENANTS_TABLE = f'OpsWheelV2-Tenants-{ENVIRONMENT}'
    
    try:
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        users_table = dynamodb.Table(USERS_TABLE)
        tenants_table = dynamodb.Table(TENANTS_TABLE)
        
        print("=== Creating Test Data ===")
        
        # Create tenant
        print(f"Creating tenant: {tenant_data['tenant_id']}")
        tenants_table.put_item(Item=tenant_data)
        print("   ✓ Tenant created")
        
        # Create user
        print(f"Creating user: {user_data['email']}")
        users_table.put_item(Item=user_data)
        print("   ✓ User created")
        
        print("\n✅ Test data created successfully!")
        print("Now try accessing the API again.")
        
    except Exception as e:
        print(f"✗ Error creating test data: {e}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--create-test-data':
        create_test_user()
    else:
        print("Testing user lookup...")
        success = test_user_lookup()
        
        if not success:
            print("\n" + "="*50)
            print("❌ User lookup failed!")
            print("This explains the AuthorizerConfigurationException.")
            print()
            print("To fix this, you can:")
            print("1. Create test data: python3 test_user_lookup.py --create-test-data")
            print("2. Or manually add the user to your DynamoDB Users table")
            print("="*50)
