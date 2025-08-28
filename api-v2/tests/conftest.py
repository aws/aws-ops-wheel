#  Enhanced Test Fixtures for AWS Ops Wheel v2 Multi-Tenant Testing
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
import boto3
from moto import mock_aws
from decimal import Decimal
from unittest.mock import Mock, patch

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils_v2 import (
    WheelGroupsTable, UsersTable, WheelsTable, ParticipantsTable,
    add_extended_table_functions, get_uuid, get_utc_timestamp
)

# Test environment variables
TEST_ENVIRONMENT = 'test'
TEST_TABLE_NAMES = {
    'WHEEL_GROUPS_TABLE': f'OpsWheelV2-WheelGroups-{TEST_ENVIRONMENT}',
    'USERS_TABLE': f'OpsWheelV2-Users-{TEST_ENVIRONMENT}',
    'WHEELS_TABLE': f'OpsWheelV2-Wheels-{TEST_ENVIRONMENT}',
    'PARTICIPANTS_TABLE': f'OpsWheelV2-Participants-{TEST_ENVIRONMENT}'
}

# Set test environment variables
for key, value in TEST_TABLE_NAMES.items():
    os.environ[key] = value

os.environ['ENVIRONMENT'] = TEST_ENVIRONMENT
os.environ['COGNITO_USER_POOL_ID'] = 'us-west-2_TEST123456'
os.environ['COGNITO_CLIENT_ID'] = 'test-client-id'
os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'


@pytest.fixture(scope='session')
def mock_dynamodb():
    """Session-scoped DynamoDB mock with all v2 tables"""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        
        # Create WheelGroups table
        wheel_groups_table = dynamodb.create_table(
            TableName=TEST_TABLE_NAMES['WHEEL_GROUPS_TABLE'],
            KeySchema=[
                {'AttributeName': 'wheel_group_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'wheel_group_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Users table with GSI
        users_table = dynamodb.create_table(
            TableName=TEST_TABLE_NAMES['USERS_TABLE'],
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'wheel_group_id', 'AttributeType': 'S'},
                {'AttributeName': 'email', 'AttributeType': 'S'},
                {'AttributeName': 'role', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'wheel-group-role-index',
                    'KeySchema': [
                        {'AttributeName': 'wheel_group_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'role', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'email-index',
                    'KeySchema': [
                        {'AttributeName': 'email', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Wheels table
        wheels_table = dynamodb.create_table(
            TableName=TEST_TABLE_NAMES['WHEELS_TABLE'],
            KeySchema=[
                {'AttributeName': 'wheel_group_id', 'KeyType': 'HASH'},
                {'AttributeName': 'wheel_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'wheel_group_id', 'AttributeType': 'S'},
                {'AttributeName': 'wheel_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Participants table with GSI for last_selected_at
        participants_table = dynamodb.create_table(
            TableName=TEST_TABLE_NAMES['PARTICIPANTS_TABLE'],
            KeySchema=[
                {'AttributeName': 'wheel_group_wheel_id', 'KeyType': 'HASH'},
                {'AttributeName': 'participant_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'wheel_group_wheel_id', 'AttributeType': 'S'},
                {'AttributeName': 'participant_id', 'AttributeType': 'S'},
                {'AttributeName': 'last_selected_at', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'last-selected-index',
                    'KeySchema': [
                        {'AttributeName': 'wheel_group_wheel_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'last_selected_at', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for tables to be created
        wheel_groups_table.wait_until_exists()
        users_table.wait_until_exists()
        wheels_table.wait_until_exists()
        participants_table.wait_until_exists()
        
        # Apply extended functions to tables
        add_extended_table_functions(wheel_groups_table)
        add_extended_table_functions(users_table)
        add_extended_table_functions(wheels_table)
        add_extended_table_functions(participants_table)
        
        yield dynamodb


@pytest.fixture
def mock_wheel_groups_table(mock_dynamodb):
    """Clean WheelGroups table fixture"""
    table = mock_dynamodb.Table(TEST_TABLE_NAMES['WHEEL_GROUPS_TABLE'])
    add_extended_table_functions(table)  # Add extended functions
    yield table
    # Cleanup after test with pagination
    scan_response = table.scan()
    items = scan_response.get('Items', [])
    
    # Handle pagination if more items exist
    while 'LastEvaluatedKey' in scan_response:
        scan_response = table.scan(ExclusiveStartKey=scan_response['LastEvaluatedKey'])
        items.extend(scan_response.get('Items', []))
    
    # Delete all items in batches
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={'wheel_group_id': item['wheel_group_id']})


@pytest.fixture
def mock_users_table(mock_dynamodb):
    """Clean Users table fixture"""
    table = mock_dynamodb.Table(TEST_TABLE_NAMES['USERS_TABLE'])
    add_extended_table_functions(table)  # Add extended functions
    yield table
    # Cleanup after test
    scan_response = table.scan()
    with table.batch_writer() as batch:
        for item in scan_response.get('Items', []):
            batch.delete_item(Key={'user_id': item['user_id']})


@pytest.fixture
def mock_wheels_table(mock_dynamodb):
    """Clean Wheels table fixture"""
    table = mock_dynamodb.Table(TEST_TABLE_NAMES['WHEELS_TABLE'])
    add_extended_table_functions(table)  # Add extended functions
    yield table
    # Cleanup after test
    scan_response = table.scan()
    with table.batch_writer() as batch:
        for item in scan_response.get('Items', []):
            batch.delete_item(Key={
                'wheel_group_id': item['wheel_group_id'],
                'wheel_id': item['wheel_id']
            })


@pytest.fixture
def mock_participants_table(mock_dynamodb):
    """Clean Participants table fixture"""
    table = mock_dynamodb.Table(TEST_TABLE_NAMES['PARTICIPANTS_TABLE'])
    add_extended_table_functions(table)  # Add extended functions
    yield table
    # Cleanup after test
    scan_response = table.scan()
    with table.batch_writer() as batch:
        for item in scan_response.get('Items', []):
            batch.delete_item(Key={
                'wheel_group_wheel_id': item['wheel_group_wheel_id'],
                'participant_id': item['participant_id']
            })


@pytest.fixture
def sample_wheel_group_data():
    """Sample wheel group data for testing"""
    return {
        'wheel_group_id': get_uuid(),
        'wheel_group_name': 'Test Company',
        'created_at': get_utc_timestamp(),
        'quotas': {
            'max_wheels': 1000,
            'max_participants_per_wheel': 1000,
            'max_multi_select': 30
        },
        'settings': {
            'allow_rigging': True,
            'default_participant_weight': Decimal('1.0'),
            'theme': 'default',
            'timezone': 'UTC'
        }
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        'user_id': get_uuid(),
        'email': 'test@example.com',
        'name': 'Test User',
        'role': 'USER',
        'created_at': get_utc_timestamp(),
        'updated_at': get_utc_timestamp()
    }


@pytest.fixture
def sample_wheel_data():
    """Sample wheel data for testing"""
    return {
        'wheel_id': get_uuid(),
        'wheel_name': 'Test Wheel',
        'description': 'A test wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp(),
        'updated_at': get_utc_timestamp(),
        'settings': {
            'allow_rigging': True,
            'multi_select_enabled': True,
            'default_multi_select_count': 1,
            'require_reason_for_rigging': False,
            'show_weights': False,
            'auto_reset_weights': False
        },
        'participant_count': 0,
        'total_spins': 0
    }


@pytest.fixture
def sample_participant_data():
    """Sample participant data for testing"""
    return {
        'participant_id': get_uuid(),
        'participant_name': 'Test Participant',
        'participant_url': 'https://example.com',
        'weight': Decimal('1.0'),
        'original_weight': Decimal('1.0'),
        'created_at': get_utc_timestamp(),
        'updated_at': get_utc_timestamp(),
        'selection_count': 0,
        'last_selected_at': '1970-01-01T00:00:00Z'  # Epoch timestamp for GSI compatibility
    }


@pytest.fixture
def mock_cognito_client():
    """Mock Cognito client for testing"""
    with patch('boto3.client') as mock_client:
        mock_cognito = Mock()
        mock_client.return_value = mock_cognito
        
        # Mock successful user creation
        mock_cognito.admin_create_user.return_value = {
            'User': {
                'Attributes': [
                    {'Name': 'sub', 'Value': get_uuid()},
                    {'Name': 'email', 'Value': 'test@example.com'},
                    {'Name': 'name', 'Value': 'Test User'}
                ]
            }
        }
        
        # Mock successful user deletion
        mock_cognito.admin_delete_user.return_value = {}
        
        # Mock successful password set
        mock_cognito.admin_set_user_password.return_value = {}
        
        # Mock successful attribute update
        mock_cognito.admin_update_user_attributes.return_value = {}
        
        yield mock_cognito


@pytest.fixture(params=['ADMIN', 'WHEEL_ADMIN', 'USER'])
def user_roles(request):
    """Parameterized fixture for testing different user roles"""
    return request.param


@pytest.fixture
def wheel_group_context(sample_wheel_group_data, sample_user_data):
    """Wheel group context for middleware testing"""
    wheel_group_data = sample_wheel_group_data.copy()
    user_data = sample_user_data.copy()
    user_data['wheel_group_id'] = wheel_group_data['wheel_group_id']
    
    return {
        'user_id': user_data['user_id'],
        'email': user_data['email'],
        'name': user_data['name'],
        'role': user_data['role'],
        'wheel_group_id': wheel_group_data['wheel_group_id'],
        'wheel_group_name': wheel_group_data['wheel_group_name'],
        'permissions': ['view_wheels', 'create_wheel', 'manage_participants'],
        'deployment_admin': False
    }


@pytest.fixture
def deployment_admin_context():
    """Deployment admin context for testing"""
    return {
        'user_id': get_uuid(),
        'email': 'admin@deployment.com',
        'name': 'Deployment Admin',
        'role': 'DEPLOYMENT_ADMIN',
        'wheel_group_id': None,
        'wheel_group_name': None,
        'permissions': ['*'],  # All permissions
        'deployment_admin': True
    }


@pytest.fixture
def api_gateway_event():
    """Mock API Gateway event for testing"""
    return {
        'requestContext': {
            'authorizer': {
                'user_id': get_uuid(),
                'email': 'test@example.com',
                'wheel_group_id': get_uuid(),
                'role': 'USER',
                'deployment_admin': False  # Use boolean instead of string
            }
        },
        'pathParameters': {},
        'queryStringParameters': {},
        'headers': {
            'Authorization': 'Bearer mock-jwt-token',
            'Content-Type': 'application/json'
        },
        'body': '{}',
        'httpMethod': 'GET'
    }


@pytest.fixture
def isolated_wheel_group_setup(mock_wheel_groups_table, mock_users_table, 
                              mock_wheels_table, mock_participants_table):
    """Set up isolated wheel group with users, wheels, and participants"""
    
    # Create wheel group
    timestamp = get_utc_timestamp()
    wheel_group = {
        'wheel_group_id': get_uuid(),
        'wheel_group_name': 'Test Wheel Group',
        'created_at': timestamp,
        'updated_at': timestamp,  # Add updated_at field
        'quotas': {
            'max_wheels': 100,
            'max_participants_per_wheel': 50,
            'max_multi_select': 10
        },
        'settings': {
            'allow_rigging': True,
            'default_participant_weight': Decimal('1.0'),
            'theme': 'default',
            'timezone': 'UTC'
        }
    }
    mock_wheel_groups_table.put_item(Item=wheel_group)
    
    # Create users
    users = []
    for i, role in enumerate(['ADMIN', 'WHEEL_ADMIN', 'USER']):
        user = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group['wheel_group_id'],
            'email': f'user{i}@test.com',
            'name': f'Test User {i}',
            'role': role,
            'created_at': get_utc_timestamp(),
            'updated_at': get_utc_timestamp()
        }
        mock_users_table.put_item(Item=user)
        users.append(user)
    
    # Create wheels
    wheels = []
    for i in range(2):
        wheel = {
            'wheel_group_id': wheel_group['wheel_group_id'],
            'wheel_id': get_uuid(),
            'wheel_name': f'Test Wheel {i}',
            'description': f'Test wheel {i} description',
            'created_by': users[0]['user_id'],  # Created by admin
            'created_at': get_utc_timestamp(),
            'updated_at': get_utc_timestamp(),
            'settings': {
                'allow_rigging': True,
                'multi_select_enabled': True,
                'default_multi_select_count': 1
            },
            'participant_count': 0,
            'total_spins': 0
        }
        mock_wheels_table.put_item(Item=wheel)
        wheels.append(wheel)
    
    # Create participants for first wheel
    participants = []
    for i in range(3):
        participant = {
            'wheel_group_wheel_id': f"{wheel_group['wheel_group_id']}#{wheels[0]['wheel_id']}",
            'participant_id': get_uuid(),
            'participant_name': f'Participant {i}',
            'participant_url': f'https://example.com/user{i}',
            'weight': Decimal('1.0'),
            'original_weight': Decimal('1.0'),
            'created_at': get_utc_timestamp(),
            'updated_at': get_utc_timestamp(),
            'selection_count': 0,
            'last_selected_at': '1970-01-01T00:00:00Z'  # Epoch timestamp for GSI compatibility
        }
        mock_participants_table.put_item(Item=participant)
        participants.append(participant)
    
    # Update wheel participant count
    mock_wheels_table.update_item(
        Key={'wheel_group_id': wheels[0]['wheel_group_id'], 'wheel_id': wheels[0]['wheel_id']},
        UpdateExpression='SET participant_count = :count',
        ExpressionAttributeValues={':count': len(participants)}
    )
    
    return {
        'wheel_group': wheel_group,
        'users': users,
        'wheels': wheels,
        'participants': participants
    }


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for testing"""
    return {
        'sub': get_uuid(),
        'email': 'test@example.com',
        'name': 'Test User',
        'custom:wheel_group_id': get_uuid(),
        'custom:deployment_admin': 'false',
        'iss': 'https://cognito-idp.us-west-2.amazonaws.com/us-west-2_TEST123456',
        'exp': 9999999999,  # Far future expiration
        'iat': 1000000000   # Past issued time
    }


# Patch the repository tables to use test tables during testing
@pytest.fixture(autouse=True)
def patch_repository_tables(mock_dynamodb):
    """Automatically patch repository tables to use test tables"""
    # Get the actual test table instances
    wheel_groups_table = mock_dynamodb.Table(TEST_TABLE_NAMES['WHEEL_GROUPS_TABLE'])
    users_table = mock_dynamodb.Table(TEST_TABLE_NAMES['USERS_TABLE'])
    wheels_table = mock_dynamodb.Table(TEST_TABLE_NAMES['WHEELS_TABLE'])
    participants_table = mock_dynamodb.Table(TEST_TABLE_NAMES['PARTICIPANTS_TABLE'])
    
    # Apply extended functions to test tables
    add_extended_table_functions(wheel_groups_table)
    add_extended_table_functions(users_table)
    add_extended_table_functions(wheels_table)
    add_extended_table_functions(participants_table)
    
    # Patch the imports in utils_v2 and other modules
    with patch('utils_v2.WheelGroupsTable', wheel_groups_table), \
         patch('utils_v2.UsersTable', users_table), \
         patch('utils_v2.WheelsTable', wheels_table), \
         patch('utils_v2.ParticipantsTable', participants_table), \
         patch('selection_algorithms.WheelRepository.get_wheel', lambda wg_id, w_id: wheels_table.get_existing_item(Key={'wheel_group_id': wg_id, 'wheel_id': w_id})), \
         patch('selection_algorithms.ParticipantRepository.list_wheel_participants', lambda wg_id, w_id: _get_wheel_participants(participants_table, wg_id, w_id)), \
         patch('selection_algorithms.ParticipantRepository.batch_update_participants', lambda wg_id, w_id, updates: _batch_update_participants(participants_table, wg_id, w_id, updates)), \
         patch('selection_algorithms.WheelRepository.update_wheel', lambda wg_id, w_id, updates: _update_wheel(wheels_table, wg_id, w_id, updates)):
        yield


def _get_wheel_participants(participants_table, wheel_group_id, wheel_id):
    """Helper function for mocked participant retrieval"""
    from utils_v2 import create_wheel_group_wheel_id, decimal_to_float
    import boto3.dynamodb.conditions
    
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    response = participants_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('wheel_group_wheel_id').eq(wheel_group_wheel_id)
    )
    return [decimal_to_float(item) for item in response.get('Items', [])]


def _batch_update_participants(participants_table, wheel_group_id, wheel_id, participant_updates):
    """Helper function for mocked batch participant updates"""
    from utils_v2 import create_wheel_group_wheel_id, to_update_kwargs, get_utc_timestamp
    from decimal import Decimal
    
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    for update in participant_updates:
        participant_id = update['participant_id']
        
        # Prepare the update data
        update_data = {}
        for key, value in update.items():
            if key != 'participant_id':  # Skip the key field
                if key == 'weight':
                    update_data[key] = Decimal(str(value))
                elif key == 'selection_count':
                    update_data[key] = Decimal(str(value)) if not isinstance(value, Decimal) else value
                else:
                    update_data[key] = value
        
        update_data['updated_at'] = get_utc_timestamp()
        
        # Use update_item for each participant
        participants_table.update_item(
            Key={'wheel_group_wheel_id': wheel_group_wheel_id, 'participant_id': participant_id},
            **to_update_kwargs(update_data)
        )


def _update_wheel(wheels_table, wheel_group_id, wheel_id, updates):
    """Helper function for mocked wheel updates"""
    from utils_v2 import to_update_kwargs, get_utc_timestamp
    
    updates['updated_at'] = get_utc_timestamp()
    wheels_table.update_item(
        Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id},
        **to_update_kwargs(updates)
    )
    return wheels_table.get_existing_item(Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id})
