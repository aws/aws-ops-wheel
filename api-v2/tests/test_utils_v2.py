#  Unit Tests for Repository Layer and Utilities - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import NotFoundError
from utils_v2 import (
    WheelGroupRepository, UserRepository, WheelRepository, ParticipantRepository,
    check_string, get_uuid, get_utc_timestamp, to_update_kwargs, decimal_to_float,
    create_wheel_group_wheel_id, parse_wheel_group_wheel_id
)


# Utility Functions Tests (8 tests)

def test_check_string_valid():
    """Test check_string with valid strings"""
    assert check_string("valid string") is True
    assert check_string("a") is True
    assert check_string("123") is True


def test_check_string_invalid():
    """Test check_string with invalid inputs"""
    assert check_string("") is False
    assert check_string(None) is False
    assert check_string(123) is False
    assert check_string([]) is False
    assert check_string({}) is False


def test_get_uuid_format():
    """Test UUID generation and format"""
    test_uuid = get_uuid()
    assert isinstance(test_uuid, str)
    assert len(test_uuid) == 36
    # Verify it's a valid UUID format
    uuid.UUID(test_uuid)  # This will raise ValueError if invalid
    
    # Test uniqueness
    uuid1 = get_uuid()
    uuid2 = get_uuid()
    assert uuid1 != uuid2


def test_get_utc_timestamp_format():
    """Test UTC timestamp format"""
    timestamp = get_utc_timestamp()
    assert isinstance(timestamp, str)
    assert len(timestamp) == 20  # ISO format: YYYY-MM-DDTHH:MM:SSZ
    assert timestamp.endswith('Z')
    assert 'T' in timestamp
    
    # Test format parsing
    from datetime import datetime
    parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None


def test_to_update_kwargs():
    """Test DynamoDB update expression generation"""
    attributes = {
        'name': 'test',
        'count': 5,
        'active': True
    }
    
    result = to_update_kwargs(attributes)
    
    assert 'UpdateExpression' in result
    assert 'ExpressionAttributeValues' in result
    assert 'ExpressionAttributeNames' in result
    
    # Check update expression format
    assert result['UpdateExpression'].startswith('set ')
    assert '#name = :name' in result['UpdateExpression']
    assert '#count = :count' in result['UpdateExpression']
    assert '#active = :active' in result['UpdateExpression']
    
    # Check attribute values
    assert result['ExpressionAttributeValues'][':name'] == 'test'
    assert result['ExpressionAttributeValues'][':count'] == 5
    assert result['ExpressionAttributeValues'][':active'] is True
    
    # Check attribute names
    assert result['ExpressionAttributeNames']['#name'] == 'name'
    assert result['ExpressionAttributeNames']['#count'] == 'count'
    assert result['ExpressionAttributeNames']['#active'] == 'active'


def test_decimal_to_float_conversion():
    """Test recursive Decimal to float conversion"""
    # Test simple Decimal
    assert decimal_to_float(Decimal('1.5')) == 1.5
    
    # Test dict with Decimals
    data = {
        'weight': Decimal('2.5'),
        'count': Decimal('10'),
        'name': 'test'
    }
    result = decimal_to_float(data)
    assert result['weight'] == 2.5
    assert result['count'] == 10.0
    assert result['name'] == 'test'
    
    # Test list with Decimals
    data = [Decimal('1.1'), Decimal('2.2'), 'string']
    result = decimal_to_float(data)
    assert result == [1.1, 2.2, 'string']
    
    # Test nested structures
    data = {
        'nested': {
            'value': Decimal('3.14')
        },
        'list': [Decimal('1.0'), Decimal('2.0')]
    }
    result = decimal_to_float(data)
    assert result['nested']['value'] == 3.14
    assert result['list'] == [1.0, 2.0]
    
    # Test non-Decimal values
    assert decimal_to_float('string') == 'string'
    assert decimal_to_float(42) == 42


def test_create_wheel_group_wheel_id():
    """Test composite ID creation"""
    wheel_group_id = get_uuid()
    wheel_id = get_uuid()
    
    composite_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    assert isinstance(composite_id, str)
    assert '#' in composite_id
    assert composite_id == f"{wheel_group_id}#{wheel_id}"


def test_parse_wheel_group_wheel_id():
    """Test composite ID parsing"""
    wheel_group_id = get_uuid()
    wheel_id = get_uuid()
    composite_id = f"{wheel_group_id}#{wheel_id}"
    
    parsed_wheel_group_id, parsed_wheel_id = parse_wheel_group_wheel_id(composite_id)
    
    assert parsed_wheel_group_id == wheel_group_id
    assert parsed_wheel_id == wheel_id
    
    # Test invalid format - no # separator
    with pytest.raises(ValueError):
        parse_wheel_group_wheel_id("invalid-format")
    
    # Test empty string
    with pytest.raises(ValueError):
        parse_wheel_group_wheel_id("")


# WheelGroupRepository Tests (7 tests)

def test_create_wheel_group(mock_wheel_groups_table):
    """Test wheel group creation with defaults"""
    wheel_group_data = {
        'wheel_group_name': 'Test Company'
    }
    
    wheel_group = WheelGroupRepository.create_wheel_group(wheel_group_data)
    
    assert wheel_group['wheel_group_name'] == 'Test Company'
    assert 'wheel_group_id' in wheel_group
    assert 'created_at' in wheel_group
    assert 'quotas' in wheel_group
    assert 'settings' in wheel_group
    
    # Verify defaults
    assert wheel_group['quotas']['max_wheels'] == 1000
    assert wheel_group['settings']['allow_rigging'] is True
    
    # Verify in database
    retrieved = mock_wheel_groups_table.get_existing_item(
        Key={'wheel_group_id': wheel_group['wheel_group_id']}
    )
    assert retrieved['wheel_group_name'] == 'Test Company'


def test_create_wheel_group_with_custom_settings(mock_wheel_groups_table):
    """Test wheel group creation with custom quotas and settings"""
    wheel_group_data = {
        'wheel_group_name': 'Custom Company',
        'quotas': {
            'max_wheels': 100,
            'max_participants_per_wheel': 50
        },
        'settings': {
            'allow_rigging': False,
            'theme': 'dark'
        }
    }
    
    wheel_group = WheelGroupRepository.create_wheel_group(wheel_group_data)
    
    assert wheel_group['quotas']['max_wheels'] == 100
    assert wheel_group['quotas']['max_participants_per_wheel'] == 50
    assert wheel_group['settings']['allow_rigging'] is False
    assert wheel_group['settings']['theme'] == 'dark'


def test_get_wheel_group(mock_wheel_groups_table, sample_wheel_group_data):
    """Test wheel group retrieval"""
    # Create wheel group in database
    mock_wheel_groups_table.put_item(Item=sample_wheel_group_data)
    
    # Retrieve wheel group
    wheel_group = WheelGroupRepository.get_wheel_group(sample_wheel_group_data['wheel_group_id'])
    
    assert wheel_group['wheel_group_id'] == sample_wheel_group_data['wheel_group_id']
    assert wheel_group['wheel_group_name'] == sample_wheel_group_data['wheel_group_name']


def test_get_wheel_group_not_found(mock_wheel_groups_table):
    """Test wheel group retrieval with non-existent ID"""
    with pytest.raises(NotFoundError):
        WheelGroupRepository.get_wheel_group('non-existent-id')


def test_update_wheel_group(mock_wheel_groups_table, sample_wheel_group_data):
    """Test wheel group update"""
    # Create wheel group in database
    mock_wheel_groups_table.put_item(Item=sample_wheel_group_data)
    
    # Update wheel group
    updates = {
        'wheel_group_name': 'Updated Company',
        'settings': {'theme': 'dark'}
    }
    
    updated_wheel_group = WheelGroupRepository.update_wheel_group(
        sample_wheel_group_data['wheel_group_id'], 
        updates
    )
    
    assert updated_wheel_group['wheel_group_name'] == 'Updated Company'
    assert updated_wheel_group['settings']['theme'] == 'dark'
    assert 'updated_at' in updated_wheel_group


def test_update_wheel_group_timestamps(mock_wheel_groups_table, sample_wheel_group_data):
    """Test that update operations add updated_at timestamp"""
    # Create wheel group
    mock_wheel_groups_table.put_item(Item=sample_wheel_group_data)
    
    original_created_at = sample_wheel_group_data['created_at']
    
    # Add a small delay to ensure different timestamps
    import time
    # Use mock timestamps instead of sleep for better test performance
    
    # Update wheel group
    updated = WheelGroupRepository.update_wheel_group(
        sample_wheel_group_data['wheel_group_id'],
        {'wheel_group_name': 'New Name'}
    )
    
    assert 'updated_at' in updated
    assert updated['created_at'] == original_created_at  # Should remain unchanged
    assert updated['updated_at'] >= original_created_at  # Should be same or later
    assert updated['wheel_group_name'] == 'New Name'  # Verify update worked


def test_delete_wheel_group(mock_wheel_groups_table, sample_wheel_group_data):
    """Test wheel group deletion"""
    # Create wheel group in database
    mock_wheel_groups_table.put_item(Item=sample_wheel_group_data)
    
    # Verify it exists
    retrieved = mock_wheel_groups_table.get_existing_item(
        Key={'wheel_group_id': sample_wheel_group_data['wheel_group_id']}
    )
    assert retrieved is not None
    
    # Delete wheel group
    WheelGroupRepository.delete_wheel_group(sample_wheel_group_data['wheel_group_id'])
    
    # Verify it's deleted
    with pytest.raises(NotFoundError):
        mock_wheel_groups_table.get_existing_item(
            Key={'wheel_group_id': sample_wheel_group_data['wheel_group_id']}
        )


# UserRepository Tests (10 tests)

def test_create_user(mock_users_table, sample_user_data, sample_wheel_group_data):
    """Test user creation with required fields"""
    user_data = sample_user_data.copy()
    user_data['wheel_group_id'] = sample_wheel_group_data['wheel_group_id']
    
    user = UserRepository.create_user(user_data)
    
    assert user['user_id'] == user_data['user_id']
    assert user['email'] == user_data['email']
    assert user['wheel_group_id'] == user_data['wheel_group_id']
    assert 'created_at' in user
    assert 'updated_at' in user
    
    # Verify in database
    retrieved = mock_users_table.get_existing_item(Key={'user_id': user['user_id']})
    assert retrieved['email'] == user_data['email']


def test_create_user_with_defaults(mock_users_table):
    """Test user creation with default role assignment"""
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': get_uuid(),
        'email': 'test@example.com'
    }
    
    user = UserRepository.create_user(user_data)
    
    assert user['role'] == 'USER'  # Default role
    assert user['name'] == user_data['email']  # Default name from email


def test_get_user(mock_users_table, sample_user_data):
    """Test user retrieval by ID"""
    # Create user in database
    mock_users_table.put_item(Item=sample_user_data)
    
    # Retrieve user
    user = UserRepository.get_user(sample_user_data['user_id'])
    
    assert user['user_id'] == sample_user_data['user_id']
    assert user['email'] == sample_user_data['email']


def test_get_user_not_found(mock_users_table):
    """Test user retrieval with non-existent ID"""
    with pytest.raises(NotFoundError):
        UserRepository.get_user('non-existent-id')


def test_get_users_by_wheel_group(mock_users_table, sample_wheel_group_data):
    """Test retrieving all users in a wheel group"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    
    # Create multiple users in the wheel group
    users_data = []
    for i in range(3):
        user_data = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group_id,
            'email': f'user{i}@test.com',
            'name': f'User {i}',
            'role': 'USER',
            'created_at': get_utc_timestamp(),
            'updated_at': get_utc_timestamp()
        }
        mock_users_table.put_item(Item=user_data)
        users_data.append(user_data)
    
    # Create user in different wheel group (should not be returned)
    other_user = {
        'user_id': get_uuid(),
        'wheel_group_id': get_uuid(),
        'email': 'other@test.com',
        'name': 'Other User',
        'role': 'USER',
        'created_at': get_utc_timestamp(),
        'updated_at': get_utc_timestamp()
    }
    mock_users_table.put_item(Item=other_user)
    
    # Retrieve users by wheel group
    users = UserRepository.get_users_by_wheel_group(wheel_group_id)
    
    assert len(users) == 3
    user_emails = [user['email'] for user in users]
    assert 'user0@test.com' in user_emails
    assert 'user1@test.com' in user_emails
    assert 'user2@test.com' in user_emails
    assert 'other@test.com' not in user_emails


def test_get_user_by_email(mock_users_table, sample_user_data):
    """Test finding user by email"""
    # Create user in database
    mock_users_table.put_item(Item=sample_user_data)
    
    # Find user by email
    user = UserRepository.get_user_by_email(sample_user_data['email'])
    
    assert user is not None
    assert user['user_id'] == sample_user_data['user_id']
    assert user['email'] == sample_user_data['email']
    
    # Test non-existent email
    user = UserRepository.get_user_by_email('nonexistent@test.com')
    assert user is None


def test_update_user(mock_users_table, sample_user_data):
    """Test user information update"""
    # Create user in database
    mock_users_table.put_item(Item=sample_user_data)
    
    # Update user
    updates = {
        'name': 'Updated Name',
        'role': 'ADMIN'
    }
    
    updated_user = UserRepository.update_user(sample_user_data['user_id'], updates)
    
    assert updated_user['name'] == 'Updated Name'
    assert updated_user['role'] == 'ADMIN'
    assert 'updated_at' in updated_user
    assert updated_user['email'] == sample_user_data['email']  # Unchanged


def test_update_user_role(mock_users_table, sample_user_data):
    """Test user role change"""
    # Create user in database
    mock_users_table.put_item(Item=sample_user_data)
    
    # Update role
    updated_user = UserRepository.update_user_role(sample_user_data['user_id'], 'WHEEL_ADMIN')
    
    assert updated_user['role'] == 'WHEEL_ADMIN'
    assert 'updated_at' in updated_user


def test_update_last_login(mock_users_table, sample_user_data):
    """Test login timestamp tracking"""
    # Create user in database
    mock_users_table.put_item(Item=sample_user_data)
    
    # Update last login
    updated_user = UserRepository.update_last_login(sample_user_data['user_id'])
    
    assert 'last_login_at' in updated_user
    assert 'updated_at' in updated_user


def test_delete_user(mock_users_table, sample_user_data):
    """Test user deletion"""
    # Create user in database
    mock_users_table.put_item(Item=sample_user_data)
    
    # Verify user exists
    retrieved = mock_users_table.get_existing_item(Key={'user_id': sample_user_data['user_id']})
    assert retrieved is not None
    
    # Delete user
    UserRepository.delete_user(sample_user_data['user_id'])
    
    # Verify user is deleted
    with pytest.raises(NotFoundError):
        mock_users_table.get_existing_item(Key={'user_id': sample_user_data['user_id']})


# WheelRepository Tests (6 tests)

def test_create_wheel(mock_wheels_table, sample_wheel_group_data):
    """Test wheel creation in wheel group"""
    wheel_data = {
        'wheel_name': 'Test Wheel',
        'description': 'Test Description',
        'created_by': get_uuid()
    }
    
    wheel = WheelRepository.create_wheel(sample_wheel_group_data['wheel_group_id'], wheel_data)
    
    assert wheel['wheel_group_id'] == sample_wheel_group_data['wheel_group_id']
    assert wheel['wheel_name'] == 'Test Wheel'
    assert wheel['description'] == 'Test Description'
    assert 'wheel_id' in wheel
    assert 'created_at' in wheel
    assert 'settings' in wheel
    assert wheel['participant_count'] == 0
    assert wheel['total_spins'] == 0
    
    # Verify in database
    retrieved = mock_wheels_table.get_existing_item(Key={
        'wheel_group_id': wheel['wheel_group_id'],
        'wheel_id': wheel['wheel_id']
    })
    assert retrieved['wheel_name'] == 'Test Wheel'


def test_get_wheel(mock_wheels_table, sample_wheel_group_data, sample_wheel_data):
    """Test wheel retrieval by composite key"""
    wheel_data = sample_wheel_data.copy()
    wheel_data['wheel_group_id'] = sample_wheel_group_data['wheel_group_id']
    
    # Create wheel in database
    mock_wheels_table.put_item(Item=wheel_data)
    
    # Retrieve wheel
    wheel = WheelRepository.get_wheel(
        wheel_data['wheel_group_id'], 
        wheel_data['wheel_id']
    )
    
    assert wheel['wheel_id'] == wheel_data['wheel_id']
    assert wheel['wheel_name'] == wheel_data['wheel_name']


def test_list_wheel_group_wheels(mock_wheels_table, sample_wheel_group_data):
    """Test listing all wheels in a wheel group"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    
    # Create multiple wheels in the wheel group
    wheels_data = []
    for i in range(3):
        wheel_data = {
            'wheel_group_id': wheel_group_id,
            'wheel_id': get_uuid(),
            'wheel_name': f'Wheel {i}',
            'created_by': get_uuid(),
            'created_at': get_utc_timestamp(),
            'updated_at': get_utc_timestamp(),
            'settings': {},
            'participant_count': 0,
            'total_spins': 0
        }
        mock_wheels_table.put_item(Item=wheel_data)
        wheels_data.append(wheel_data)
    
    # Create wheel in different wheel group (should not be returned)
    other_wheel = {
        'wheel_group_id': get_uuid(),
        'wheel_id': get_uuid(),
        'wheel_name': 'Other Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp(),
        'updated_at': get_utc_timestamp(),
        'settings': {},
        'participant_count': 0,
        'total_spins': 0
    }
    mock_wheels_table.put_item(Item=other_wheel)
    
    # Retrieve wheels by wheel group
    wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
    
    assert len(wheels) == 3
    wheel_names = [wheel['wheel_name'] for wheel in wheels]
    assert 'Wheel 0' in wheel_names
    assert 'Wheel 1' in wheel_names
    assert 'Wheel 2' in wheel_names
    assert 'Other Wheel' not in wheel_names


def test_update_wheel(mock_wheels_table, sample_wheel_group_data, sample_wheel_data):
    """Test wheel information update"""
    wheel_data = sample_wheel_data.copy()
    wheel_data['wheel_group_id'] = sample_wheel_group_data['wheel_group_id']
    
    # Create wheel in database
    mock_wheels_table.put_item(Item=wheel_data)
    
    # Update wheel
    updates = {
        'wheel_name': 'Updated Wheel',
        'description': 'Updated Description'
    }
    
    updated_wheel = WheelRepository.update_wheel(
        wheel_data['wheel_group_id'],
        wheel_data['wheel_id'],
        updates
    )
    
    assert updated_wheel['wheel_name'] == 'Updated Wheel'
    assert updated_wheel['description'] == 'Updated Description'
    assert 'updated_at' in updated_wheel


def test_delete_wheel(mock_wheels_table, mock_participants_table, sample_wheel_group_data):
    """Test wheel deletion along with participants"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    wheel_id = get_uuid()
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    # Create wheel
    wheel_data = {
        'wheel_group_id': wheel_group_id,
        'wheel_id': wheel_id,
        'wheel_name': 'Test Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp(),
        'updated_at': get_utc_timestamp(),
        'settings': {},
        'participant_count': 0,
        'total_spins': 0
    }
    mock_wheels_table.put_item(Item=wheel_data)
    
    # Create participants for the wheel
    participants_data = []
    for i in range(2):
        participant_data = {
            'wheel_group_wheel_id': wheel_group_wheel_id,
            'participant_id': get_uuid(),
            'participant_name': f'Participant {i}',
            'weight': Decimal('1.0'),
            'created_at': get_utc_timestamp()
        }
        mock_participants_table.put_item(Item=participant_data)
        participants_data.append(participant_data)
    
    # Verify wheel and participants exist
    retrieved_wheel = mock_wheels_table.get_existing_item(Key={
        'wheel_group_id': wheel_group_id,
        'wheel_id': wheel_id
    })
    assert retrieved_wheel is not None
    
    # Delete wheel
    WheelRepository.delete_wheel(wheel_group_id, wheel_id)
    
    # Verify wheel is deleted
    with pytest.raises(NotFoundError):
        mock_wheels_table.get_existing_item(Key={
            'wheel_group_id': wheel_group_id,
            'wheel_id': wheel_id
        })
    
    # Verify participants are deleted
    participants_response = mock_participants_table.query(
        KeyConditionExpression='wheel_group_wheel_id = :wgwid',
        ExpressionAttributeValues={':wgwid': wheel_group_wheel_id}
    )
    assert len(participants_response.get('Items', [])) == 0


def test_wheel_isolation_between_groups(mock_wheels_table):
    """Test that wheels are properly isolated between wheel groups"""
    wheel_group_1 = get_uuid()
    wheel_group_2 = get_uuid()
    
    # Create wheels in different wheel groups with same wheel_id
    same_wheel_id = get_uuid()
    
    wheel_1 = {
        'wheel_group_id': wheel_group_1,
        'wheel_id': same_wheel_id,
        'wheel_name': 'Wheel in Group 1',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp(),
        'settings': {},
        'participant_count': 0
    }
    
    wheel_2 = {
        'wheel_group_id': wheel_group_2,
        'wheel_id': same_wheel_id,
        'wheel_name': 'Wheel in Group 2',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp(),
        'settings': {},
        'participant_count': 0
    }
    
    mock_wheels_table.put_item(Item=wheel_1)
    mock_wheels_table.put_item(Item=wheel_2)
    
    # Retrieve wheels separately
    retrieved_1 = WheelRepository.get_wheel(wheel_group_1, same_wheel_id)
    retrieved_2 = WheelRepository.get_wheel(wheel_group_2, same_wheel_id)
    
    assert retrieved_1['wheel_name'] == 'Wheel in Group 1'
    assert retrieved_2['wheel_name'] == 'Wheel in Group 2'
    
    # List wheels by group
    group_1_wheels = WheelRepository.list_wheel_group_wheels(wheel_group_1)
    group_2_wheels = WheelRepository.list_wheel_group_wheels(wheel_group_2)
    
    assert len(group_1_wheels) == 1
    assert len(group_2_wheels) == 1
    assert group_1_wheels[0]['wheel_name'] == 'Wheel in Group 1'
    assert group_2_wheels[0]['wheel_name'] == 'Wheel in Group 2'


# ParticipantRepository Tests (4 tests)

def test_create_participant(mock_participants_table, sample_wheel_group_data):
    """Test participant creation with composite key"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    wheel_id = get_uuid()
    
    participant_data = {
        'participant_name': 'Test Participant',
        'participant_url': 'https://example.com',
        'weight': 1.5
    }
    
    participant = ParticipantRepository.create_participant(
        wheel_group_id, 
        wheel_id, 
        participant_data
    )
    
    expected_wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    assert participant['wheel_group_wheel_id'] == expected_wheel_group_wheel_id
    assert participant['participant_name'] == 'Test Participant'
    assert participant['participant_url'] == 'https://example.com'
    assert participant['weight'] == Decimal('1.5')
    assert participant['original_weight'] == Decimal('1.5')
    assert 'participant_id' in participant
    assert 'created_at' in participant
    assert participant['selection_count'] == 0
    
    # Verify in database
    retrieved = mock_participants_table.get_existing_item(Key={
        'wheel_group_wheel_id': participant['wheel_group_wheel_id'],
        'participant_id': participant['participant_id']
    })
    assert retrieved['participant_name'] == 'Test Participant'


def test_get_participant(mock_participants_table, sample_wheel_group_data, sample_participant_data):
    """Test participant retrieval"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    wheel_id = get_uuid()
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    participant_data = sample_participant_data.copy()
    participant_data['wheel_group_wheel_id'] = wheel_group_wheel_id
    
    # Create participant in database
    mock_participants_table.put_item(Item=participant_data)
    
    # Retrieve participant
    participant = ParticipantRepository.get_participant(
        wheel_group_id, 
        wheel_id, 
        participant_data['participant_id']
    )
    
    assert participant['participant_id'] == participant_data['participant_id']
    assert participant['participant_name'] == participant_data['participant_name']


def test_list_wheel_participants(mock_participants_table, sample_wheel_group_data):
    """Test listing all participants for a wheel"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    wheel_id = get_uuid()
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    # Create multiple participants
    participants_data = []
    for i in range(3):
        participant_data = {
            'wheel_group_wheel_id': wheel_group_wheel_id,
            'participant_id': get_uuid(),
            'participant_name': f'Participant {i}',
            'participant_url': f'https://example.com/user{i}',
            'weight': Decimal('1.0'),
            'original_weight': Decimal('1.0'),
            'created_at': get_utc_timestamp(),
            'selection_count': 0,
            'last_selected_at': '1970-01-01T00:00:00Z'  # Epoch timestamp for GSI compatibility
        }
        mock_participants_table.put_item(Item=participant_data)
        participants_data.append(participant_data)
    
    # Create participant in different wheel (should not be returned)
    other_wheel_id = get_uuid()
    other_wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, other_wheel_id)
    other_participant = {
        'wheel_group_wheel_id': other_wheel_group_wheel_id,
        'participant_id': get_uuid(),
        'participant_name': 'Other Participant',
        'participant_url': 'https://example.com/other',
        'weight': Decimal('1.0'),
        'original_weight': Decimal('1.0'),
        'created_at': get_utc_timestamp(),
        'selection_count': 0
    }
    mock_participants_table.put_item(Item=other_participant)
    
    # Retrieve participants for the specific wheel
    participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    
    assert len(participants) == 3
    participant_names = [p['participant_name'] for p in participants]
    assert 'Participant 0' in participant_names
    assert 'Participant 1' in participant_names
    assert 'Participant 2' in participant_names
    assert 'Other Participant' not in participant_names


def test_batch_update_participants(mock_participants_table, sample_wheel_group_data):
    """Test batch participant updates for weight redistribution"""
    wheel_group_id = sample_wheel_group_data['wheel_group_id']
    wheel_id = get_uuid()
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    # Create participants
    participants_data = []
    for i in range(3):
        participant_data = {
            'wheel_group_wheel_id': wheel_group_wheel_id,
            'participant_id': get_uuid(),
            'participant_name': f'Participant {i}',
            'participant_url': f'https://example.com/user{i}',
            'weight': Decimal('1.0'),
            'original_weight': Decimal('1.0'),
            'created_at': get_utc_timestamp(),
            'selection_count': 0
        }
        mock_participants_table.put_item(Item=participant_data)
        participants_data.append(participant_data)
    
    # Prepare batch updates (simulate weight redistribution)
    updates = []
    for i, participant in enumerate(participants_data):
        update_data = {
            'participant_id': participant['participant_id'],
            'weight': Decimal('0.5') if i == 0 else Decimal('1.25'),  # First gets less, others get more
            'selection_count': 1 if i == 0 else 0,  # First was selected
            'updated_at': get_utc_timestamp()
        }
        if i == 0:  # Add last_selected_at for selected participant
            update_data['last_selected_at'] = get_utc_timestamp()
        updates.append(update_data)
    
    # Execute batch update
    ParticipantRepository.batch_update_participants(wheel_group_id, wheel_id, updates)
    
    # Verify updates
    updated_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    
    # Find the first participant (should be selected)
    selected_participant = None
    others = []
    for p in updated_participants:
        if p['participant_name'] == 'Participant 0':
            selected_participant = p
        else:
            others.append(p)
    
    assert selected_participant is not None
    assert selected_participant['weight'] == 0.5  # Reduced weight
    assert selected_participant['selection_count'] == 1  # Was selected
    assert 'last_selected_at' in selected_participant  # Has selection timestamp
    
    # Check other participants got increased weight
    for other in others:
        assert other['weight'] == 1.25  # Increased weight
        assert other['selection_count'] == 0  # Not selected
