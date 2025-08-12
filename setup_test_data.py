#!/usr/bin/env python3
"""
Setup Test Data for AWS Ops Wheel Multi-tenant System

This script creates:
1. Test users in Cognito with custom attributes
2. Corresponding records in DynamoDB tables
3. Sample tenant with wheels and participants

Prerequisites:
- AWS CLI configured with appropriate permissions
- DynamoDB tables deployed (run deploy-v2-modular.sh first)
- Cognito User Pool deployed
"""

import boto3
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import os
import sys

# Configuration
REGION = 'us-west-2'  # Change to your region
TENANT_ID = 'tenant-1'
TENANT_NAME = 'Test Company Inc'

# Test users to create
TEST_USERS = [
    {
        'email': 'user1@test.com',
        'password': 'TempPassword123!',
        'role': 'USER',
        'name': 'Regular User',
        'tenant_id': TENANT_ID
    },
    {
        'email': 'admin1@test.com', 
        'password': 'TempPassword123!',
        'role': 'WHEEL_ADMIN',
        'name': 'Wheel Administrator',
        'tenant_id': TENANT_ID
    },
    {
        'email': 'superadmin@test.com',
        'password': 'TempPassword123!', 
        'role': 'ADMIN',
        'name': 'Super Administrator',
        'tenant_id': TENANT_ID
    }
]

# Sample wheels and participants
SAMPLE_WHEELS = [
    {
        'wheel_name': 'Daily Standup Leader',
        'description': 'Who leads today\'s standup meeting?',
        'participants': [
            {'name': 'Alice Johnson', 'url': 'https://github.com/alice'},
            {'name': 'Bob Smith', 'url': 'https://github.com/bob'},
            {'name': 'Carol Davis', 'url': 'https://github.com/carol'},
            {'name': 'David Wilson', 'url': 'https://github.com/david'},
            {'name': 'Eve Brown', 'url': 'https://github.com/eve'}
        ]
    },
    {
        'wheel_name': 'Code Review Assignments',
        'description': 'Random assignment for code reviews',
        'participants': [
            {'name': 'Frontend Team', 'url': ''},
            {'name': 'Backend Team', 'url': ''},
            {'name': 'DevOps Team', 'url': ''},
            {'name': 'QA Team', 'url': ''}
        ]
    },
    {
        'wheel_name': 'Lunch Decision Maker',
        'description': 'Where should we order lunch from?',
        'participants': [
            {'name': 'Pizza Palace', 'url': 'https://pizzapalace.com'},
            {'name': 'Burger Barn', 'url': 'https://burgerbarn.com'},
            {'name': 'Sushi Station', 'url': 'https://sushistate.com'},
            {'name': 'Taco Town', 'url': 'https://tacotown.com'},
            {'name': 'Salad Supreme', 'url': 'https://saladsupreme.com'},
            {'name': 'Sandwich Shop', 'url': 'https://sandwichshop.com'}
        ]
    }
]

def get_aws_clients():
    """Initialize AWS clients"""
    return {
        'cognito': boto3.client('cognito-idp', region_name=REGION),
        'dynamodb': boto3.resource('dynamodb', region_name=REGION)
    }

def get_stack_outputs():
    """Get CloudFormation stack outputs for resource names"""
    cf_client = boto3.client('cloudformation', region_name=REGION)
    
    try:
        # Try to get outputs from the v2 stack
        response = cf_client.describe_stacks(StackName='aws-ops-wheel-v2-dev')
        outputs = response['Stacks'][0]['Outputs']
        
        result = {}
        for output in outputs:
            result[output['OutputKey']] = output['OutputValue']
        
        return result
    except Exception as e:
        print(f"Error getting stack outputs: {e}")
        print("Please ensure the awsopswheel-v2 stack is deployed")
        sys.exit(1)

def create_cognito_user(cognito_client, user_pool_id, user_data):
    """Create a user in Cognito with custom attributes"""
    print(f"Creating Cognito user: {user_data['email']}")
    
    try:
        # Create user using email as username (for login), Cognito will generate UUID as sub
        response = cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=user_data['email'],  # Use email as username for login
            UserAttributes=[
                {'Name': 'email', 'Value': user_data['email']},
                {'Name': 'name', 'Value': user_data['name']},
                {'Name': 'email_verified', 'Value': 'true'}
            ],
            TemporaryPassword=user_data['password'],
            MessageAction='SUPPRESS'  # Don't send welcome email
        )
        
        # Set permanent password
        cognito_client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=user_data['email'],
            Password=user_data['password'],
            Permanent=True
        )
        
        # Get the user details to extract the actual UUID (sub field)
        user_details = cognito_client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=user_data['email']
        )
        
        # Extract the UUID from the user attributes (this is the 'sub' field)
        user_id = None
        for attr in user_details['UserAttributes']:
            if attr['Name'] == 'sub':
                user_id = attr['Value']
                break
        
        if not user_id:
            # Fallback: generate UUID if sub not found
            user_id = str(uuid.uuid4())
        
        print(f"✅ Created Cognito user: {user_data['email']} (ID: {user_id})")
        return user_id
        
    except cognito_client.exceptions.UsernameExistsException:
        print(f"⚠️  User {user_data['email']} already exists in Cognito")
        # Get existing user details to extract UUID
        try:
            user_details = cognito_client.admin_get_user(
                UserPoolId=user_pool_id,
                Username=user_data['email']
            )
            
            # Extract the UUID from the user attributes
            for attr in user_details['UserAttributes']:
                if attr['Name'] == 'sub':
                    return attr['Value']
            
            # Fallback if sub not found
            return str(uuid.uuid4())
        except Exception as e:
            print(f"❌ Error getting existing user details: {e}")
            return str(uuid.uuid4())
    except Exception as e:
        print(f"❌ Error creating Cognito user {user_data['email']}: {e}")
        return None

def create_tenant_record(dynamodb, table_name, tenant_id, tenant_name):
    """Create tenant record in DynamoDB"""
    print(f"Creating tenant record: {tenant_id}")
    
    table = dynamodb.Table(table_name)
    
    try:
        table.put_item(
            Item={
                'tenant_id': tenant_id,
                'tenant_name': tenant_name,
                'status': 'ACTIVE',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'settings': {
                    'max_wheels': 50,
                    'max_participants_per_wheel': 100,
                    'allow_public_wheels': False
                }
            },
            ConditionExpression='attribute_not_exists(tenant_id)'
        )
        print(f"✅ Created tenant record: {tenant_id}")
    except Exception as e:
        if 'ConditionalCheckFailedException' in str(e):
            print(f"⚠️  Tenant {tenant_id} already exists")
        else:
            print(f"❌ Error creating tenant: {e}")

def create_user_record(dynamodb, table_name, user_data, user_id):
    """Create user record in DynamoDB"""
    print(f"Creating user record: {user_data['email']}")
    
    table = dynamodb.Table(table_name)
    
    try:
        table.put_item(
            Item={
                'user_id': user_id,
                'email': user_data['email'],
                'name': user_data['name'],
                'tenant_id': user_data['tenant_id'],
                'role': user_data['role'],
                'status': 'ACTIVE',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_login_at': None
            },
            ConditionExpression='attribute_not_exists(user_id)'
        )
        print(f"✅ Created user record: {user_data['email']}")
    except Exception as e:
        if 'ConditionalCheckFailedException' in str(e):
            print(f"⚠️  User record {user_data['email']} already exists")
        else:
            print(f"❌ Error creating user record: {e}")

def create_wheel_record(dynamodb, table_name, tenant_id, wheel_data, created_by_user_id):
    """Create wheel record in DynamoDB"""
    wheel_id = str(uuid.uuid4())
    
    print(f"Creating wheel: {wheel_data['wheel_name']}")
    
    table = dynamodb.Table(table_name)
    
    try:
        table.put_item(
            Item={
                'tenant_wheel_id': f"{tenant_id}#{wheel_id}",
                'tenant_id': tenant_id,
                'wheel_id': wheel_id,
                'wheel_name': wheel_data['wheel_name'],
                'description': wheel_data['description'],
                'created_by': created_by_user_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'total_spins': 0,
                'participant_count': len(wheel_data['participants']),
                'settings': {
                    'allow_rigging': True,
                    'multi_select_enabled': True,
                    'default_multi_select_count': 1,
                    'require_reason_for_rigging': False,
                    'show_weights': False,
                    'auto_reset_weights': False
                }
            }
        )
        print(f"✅ Created wheel: {wheel_data['wheel_name']} (ID: {wheel_id})")
        return wheel_id
    except Exception as e:
        print(f"❌ Error creating wheel: {e}")
        return None

def create_participant_record(dynamodb, table_name, tenant_id, wheel_id, participant_data):
    """Create participant record in DynamoDB"""
    participant_id = str(uuid.uuid4())
    
    table = dynamodb.Table(table_name)
    
    try:
        table.put_item(
            Item={
                'tenant_wheel_id': f"{tenant_id}#{wheel_id}",
                'participant_id': participant_id,
                'participant_name': participant_data['name'],
                'participant_url': participant_data['url'],
                'weight': Decimal('1.0'),
                'original_weight': Decimal('1.0'),
                'selection_count': Decimal('0'),
                'status': 'ACTIVE',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
        )
        print(f"  ✅ Created participant: {participant_data['name']}")
        return participant_id
    except Exception as e:
        print(f"  ❌ Error creating participant {participant_data['name']}: {e}")
        return None

def main():
    """Main setup function"""
    print("🚀 Setting up test data for AWS Ops Wheel Multi-tenant System")
    print("=" * 60)
    
    # Get AWS clients
    clients = get_aws_clients()
    
    # Get stack outputs
    print("📋 Getting stack outputs...")
    stack_outputs = get_stack_outputs()
    
    user_pool_id = stack_outputs.get('UserPoolId')
    users_table_name = stack_outputs.get('UsersTableName')
    tenants_table_name = stack_outputs.get('TenantsTableName') 
    wheels_table_name = stack_outputs.get('WheelsTableName')
    participants_table_name = stack_outputs.get('ParticipantsTableName')
    
    if not all([user_pool_id, users_table_name, tenants_table_name, wheels_table_name, participants_table_name]):
        print("❌ Missing required stack outputs. Please check your CloudFormation deployment.")
        print(f"Available outputs: {list(stack_outputs.keys())}")
        sys.exit(1)
    
    print(f"User Pool ID: {user_pool_id}")
    print(f"Tables: {users_table_name}, {tenants_table_name}, {wheels_table_name}, {participants_table_name}")
    print()
    
    # Step 1: Create tenant record
    print("1️⃣  Creating tenant record...")
    create_tenant_record(clients['dynamodb'], tenants_table_name, TENANT_ID, TENANT_NAME)
    print()
    
    # Step 2: Create Cognito users and DynamoDB user records
    print("2️⃣  Creating test users...")
    user_ids = {}
    
    for user_data in TEST_USERS:
        # Create Cognito user
        user_id = create_cognito_user(clients['cognito'], user_pool_id, user_data)
        if user_id:
            user_ids[user_data['email']] = user_id
            # Create DynamoDB user record
            create_user_record(clients['dynamodb'], users_table_name, user_data, user_id)
    
    print()
    
    # Step 3: Create sample wheels and participants
    print("3️⃣  Creating sample wheels and participants...")
    
    # Use the admin user as the creator
    admin_user_id = user_ids.get('admin1@test.com')
    if not admin_user_id:
        print("❌ Admin user not found, cannot create wheels")
        sys.exit(1)
    
    for wheel_data in SAMPLE_WHEELS:
        wheel_id = create_wheel_record(
            clients['dynamodb'], 
            wheels_table_name, 
            TENANT_ID, 
            wheel_data, 
            admin_user_id
        )
        
        if wheel_id:
            # Create participants for this wheel
            for participant_data in wheel_data['participants']:
                create_participant_record(
                    clients['dynamodb'],
                    participants_table_name,
                    TENANT_ID,
                    wheel_id,
                    participant_data
                )
        print()
    
    # Step 4: Summary
    print("🎉 Test data setup complete!")
    print("=" * 60)
    print("Test Users Created:")
    print("📧 user1@test.com (Role: USER) - Password: TempPassword123!")
    print("📧 admin1@test.com (Role: WHEEL_ADMIN) - Password: TempPassword123!")  
    print("📧 superadmin@test.com (Role: ADMIN) - Password: TempPassword123!")
    print()
    print("Sample Data Created:")
    print(f"🏢 Tenant: {TENANT_NAME} (ID: {TENANT_ID})")
    print(f"🎯 {len(SAMPLE_WHEELS)} sample wheels with participants:")
    for wheel in SAMPLE_WHEELS:
        print(f"   • {wheel['wheel_name']} ({len(wheel['participants'])} participants)")
    print()
    print("✅ You can now test the multi-tenant system with different user roles!")
    print("🌐 Access the ui-v2 application and login with any of the test accounts.")

if __name__ == '__main__':
    main()
