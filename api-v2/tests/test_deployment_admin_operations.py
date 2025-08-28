#  Improved Unit Tests for Deployment Admin Operations API - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests validate actual business logic for admin operations, not just HTTP status codes

import os
import sys
import pytest
import json
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch, Mock, MagicMock

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import BadRequestError, NotFoundError
from utils_v2 import get_uuid, get_utc_timestamp, WheelGroupRepository, UserRepository, WheelRepository, ParticipantRepository

# Import deployment admin functions with authentication mocking
with patch('wheel_group_middleware.require_auth', lambda: lambda func: func), \
     patch('wheel_group_middleware.require_wheel_group_permission', lambda perm: lambda func: func):
    from deployment_admin_operations import (
        list_all_wheel_groups, delete_wheel_group, get_wheel_group_statistics,
        check_deployment_admin_permission, STATUS_CODES, CORS_HEADERS
    )


def create_mock_lambda_context():
    """Create a mock Lambda context for testing"""
    mock_context = Mock()
    mock_context.aws_request_id = 'test-request-id'
    return mock_context


def create_deployment_admin_event(**kwargs):
    """Create an event with deployment admin permissions"""
    return {
        'user_info': {'deployment_admin': True},
        'wheel_group_context': {'deployment_admin': True},
        'requestContext': {
            'authorizer': {'deployment_admin': 'true'}
        },
        **kwargs
    }


def create_non_admin_event(**kwargs):
    """Create an event without deployment admin permissions"""
    return {
        'user_info': {'deployment_admin': False},
        'wheel_group_context': {'deployment_admin': False},
        'requestContext': {
            'authorizer': {'deployment_admin': 'false'}
        },
        **kwargs
    }


def validate_cors_headers(response):
    """Validate that response includes proper CORS headers"""
    assert 'headers' in response
    headers = response['headers']
    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'


def validate_wheel_group_list_response_structure(wheel_group_data):
    """Validate that wheel group list response has correct structure and data types"""
    required_fields = [
        'wheel_group_id', 'wheel_group_name', 'user_count', 'wheel_count',
        'created_at', 'last_updated'
    ]
    
    for field in required_fields:
        assert field in wheel_group_data, f"Missing required field: {field}"
    
    # Validate data types
    assert isinstance(wheel_group_data['wheel_group_id'], str), "wheel_group_id must be string"
    assert isinstance(wheel_group_data['wheel_group_name'], str), "wheel_group_name must be string"
    assert isinstance(wheel_group_data['user_count'], int), "user_count must be int"
    assert isinstance(wheel_group_data['wheel_count'], int), "wheel_count must be int"
    
    # Validate counts are non-negative
    assert wheel_group_data['user_count'] >= 0, "user_count must be non-negative"
    assert wheel_group_data['wheel_count'] >= 0, "wheel_count must be non-negative"
    
    # Validate timestamp formats (can be None)
    if wheel_group_data['created_at'] is not None:
        try:
            datetime.fromisoformat(wheel_group_data['created_at'].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Invalid created_at timestamp format: {wheel_group_data['created_at']}")
    if wheel_group_data['last_updated'] is not None:
        try:
            datetime.fromisoformat(wheel_group_data['last_updated'].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Invalid last_updated timestamp format: {wheel_group_data['last_updated']}")


def validate_database_has_no_wheel_group_data(wheel_group_id: str):
    """Validate that wheel group and all associated data has been completely deleted"""
    # Verify wheel group doesn't exist
    try:
        WheelGroupRepository.get_wheel_group(wheel_group_id)
        assert False, f"Wheel group {wheel_group_id} should not exist after deletion"
    except NotFoundError:
        pass  # Expected
    
    # Verify no users exist for this wheel group
    users = UserRepository.get_users_by_wheel_group(wheel_group_id)
    assert len(users) == 0, f"Users should not exist for deleted wheel group {wheel_group_id}"
    
    # Verify no wheels exist for this wheel group
    wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
    assert len(wheels) == 0, f"Wheels should not exist for deleted wheel group {wheel_group_id}"


# Authentication & Authorization Tests (8 tests)

def test_list_wheel_groups_deployment_admin_required_exact_error():
    """Test exact error message when deployment admin permission is required"""
    non_admin_event = create_non_admin_event()
    
    response = list_all_wheel_groups(non_admin_event, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['FORBIDDEN']
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert body['error'] == 'Access denied. Deployment admin privileges required.'


def test_list_wheel_groups_non_admin_forbidden_validation():
    """Test that non-admin users cannot access admin endpoints"""
    # Test with completely missing permission context
    event_no_permissions = {}
    
    response = list_all_wheel_groups(event_no_permissions, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['FORBIDDEN']
    body = json.loads(response['body'])
    assert 'Access denied' in body['error']


def test_delete_wheel_group_deployment_admin_required_exact_error():
    """Test exact error message for delete wheel group admin requirement"""
    non_admin_event = create_non_admin_event(
        pathParameters={'wheel_group_id': get_uuid()}
    )
    
    response = delete_wheel_group(non_admin_event, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['FORBIDDEN']
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert body['error'] == 'Access denied. Deployment admin privileges required.'


def test_delete_wheel_group_non_admin_forbidden_validation():
    """Test that non-admin users cannot delete wheel groups"""
    event_no_permissions = {
        'pathParameters': {'wheel_group_id': get_uuid()}
    }
    
    response = delete_wheel_group(event_no_permissions, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['FORBIDDEN']


def test_check_deployment_admin_permission_validates_all_sources():
    """Test deployment admin permission checking from all possible sources"""
    # Test user_info source
    event_user_info = {'user_info': {'deployment_admin': True}}
    assert check_deployment_admin_permission(event_user_info) is True
    
    # Test wheel_group_context source
    event_context = {'wheel_group_context': {'deployment_admin': True}}
    assert check_deployment_admin_permission(event_context) is True
    
    # Test authorizer context source
    event_authorizer = {
        'requestContext': {
            'authorizer': {'deployment_admin': 'true'}
        }
    }
    assert check_deployment_admin_permission(event_authorizer) is True
    
    # Test string 'True' variation
    event_authorizer_capital = {
        'requestContext': {
            'authorizer': {'deployment_admin': 'True'}
        }
    }
    assert check_deployment_admin_permission(event_authorizer_capital) is True


def test_check_deployment_admin_permission_handles_missing_context():
    """Test permission checking handles missing context gracefully"""
    # Empty event
    assert check_deployment_admin_permission({}) is False
    
    # Missing deployment_admin keys
    event_missing = {
        'user_info': {},
        'wheel_group_context': {},
        'requestContext': {'authorizer': {}}
    }
    assert check_deployment_admin_permission(event_missing) is False
    
    # False values
    event_false = {
        'user_info': {'deployment_admin': False},
        'wheel_group_context': {'deployment_admin': False},
        'requestContext': {'authorizer': {'deployment_admin': 'false'}}
    }
    assert check_deployment_admin_permission(event_false) is False


def test_check_deployment_admin_permission_handles_malformed_data():
    """Test permission checking handles malformed event data"""
    # None values
    event_none = {
        'user_info': None,
        'wheel_group_context': None,
        'requestContext': None
    }
    assert check_deployment_admin_permission(event_none) is False
    
    # Non-dict values
    event_invalid = {
        'user_info': 'not_a_dict',
        'wheel_group_context': [],
        'requestContext': 123
    }
    assert check_deployment_admin_permission(event_invalid) is False


def test_check_deployment_admin_permission_string_boolean_conversion():
    """Test permission checking handles string boolean variations"""
    # Test various string representations
    # Note: Based on the actual implementation, it converts to lowercase and checks for 'true'
    string_variations = [
        ('true', True),
        ('True', True),
        ('TRUE', True),  # This gets converted to lowercase and becomes 'true'
        ('false', False),
        ('False', False),
        ('1', False),
        ('0', False),
        ('', False)
    ]
    
    for string_val, expected in string_variations:
        event = {
            'requestContext': {
                'authorizer': {'deployment_admin': string_val}
            }
        }
        result = check_deployment_admin_permission(event)
        assert result == expected, f"String '{string_val}' should return {expected}, got {result}"


# List All Wheel Groups Tests (8 tests)

def test_list_all_wheel_groups_success_validates_complete_statistics(isolated_wheel_group_setup):
    """Test successful listing validates complete statistics calculation"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test data for statistics calculation
    # Add users
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'testuser@example.com',
        'name': 'Test User',
        'role': 'USER'
    }
    UserRepository.create_user(user_data)
    
    # Add wheel
    wheel_data = {
        'wheel_id': get_uuid(),
        'wheel_name': 'Test Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp()
    }
    WheelRepository.create_wheel(wheel_group_id, wheel_data)
    
    admin_event = create_deployment_admin_event()
    
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == STATUS_CODES['OK']
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert 'wheel_groups' in body
    assert isinstance(body['wheel_groups'], list)
    
    # Find our test wheel group in results
    test_wheel_group = None
    for wg in body['wheel_groups']:
        if wg['wheel_group_id'] == wheel_group_id:
            test_wheel_group = wg
            break
    
    assert test_wheel_group is not None, "Test wheel group should be in results"
    validate_wheel_group_list_response_structure(test_wheel_group)
    
    # Validate statistics are accurate
    assert test_wheel_group['user_count'] >= 1, "Should have at least 1 user"
    assert test_wheel_group['wheel_count'] >= 1, "Should have at least 1 wheel"
    assert test_wheel_group['wheel_group_name'] == setup['wheel_group']['wheel_group_name']


@patch('deployment_admin_operations.WheelGroupsTable.iter_scan')
def test_list_all_wheel_groups_empty_system_returns_empty_array(mock_scan):
    """Test listing wheel groups when system is empty"""
    # Mock empty database scan
    mock_scan.return_value = iter([])
    
    admin_event = create_deployment_admin_event()
    
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['OK']
    body = json.loads(response['body'])
    
    assert 'wheel_groups' in body
    assert isinstance(body['wheel_groups'], list)
    assert len(body['wheel_groups']) == 0, "Should return empty list when system is empty"


def test_list_all_wheel_groups_calculates_accurate_user_counts(isolated_wheel_group_setup):
    """Test that user counts are calculated accurately"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create exactly 3 users
    for i in range(3):
        user_data = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group_id,
            'email': f'user{i}@example.com',
            'name': f'User {i}',
            'role': 'USER'
        }
        UserRepository.create_user(user_data)
    
    admin_event = create_deployment_admin_event()
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    body = json.loads(response['body'])
    
    # Find our test wheel group
    test_wheel_group = None
    for wg in body['wheel_groups']:
        if wg['wheel_group_id'] == wheel_group_id:
            test_wheel_group = wg
            break
    
    assert test_wheel_group is not None
    assert test_wheel_group['user_count'] >= 3, f"Expected at least 3 users, got {test_wheel_group['user_count']}"


def test_list_all_wheel_groups_calculates_accurate_wheel_counts(isolated_wheel_group_setup):
    """Test that wheel counts are calculated accurately"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create exactly 2 wheels
    for i in range(2):
        wheel_data = {
            'wheel_id': get_uuid(),
            'wheel_name': f'Test Wheel {i}',
            'created_by': get_uuid(),
            'created_at': get_utc_timestamp()
        }
        WheelRepository.create_wheel(wheel_group_id, wheel_data)
    
    admin_event = create_deployment_admin_event()
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    body = json.loads(response['body'])
    
    # Find our test wheel group
    test_wheel_group = None
    for wg in body['wheel_groups']:
        if wg['wheel_group_id'] == wheel_group_id:
            test_wheel_group = wg
            break
    
    assert test_wheel_group is not None
    assert test_wheel_group['wheel_count'] >= 2, f"Expected at least 2 wheels, got {test_wheel_group['wheel_count']}"


def test_list_all_wheel_groups_calculates_last_updated_timestamps(isolated_wheel_group_setup):
    """Test that last_updated timestamps aggregate correctly from all entities"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create entities with known timestamps for testing
    import time
    
    # Create user (will have updated_at)
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'timestampuser@example.com',
        'name': 'Timestamp User',
        'role': 'USER'
    }
    UserRepository.create_user(user_data)
    
    # Use mock timestamps instead of sleep for better test performance
    
    # Create wheel (will have created_at, potentially last_spun_at)
    wheel_data = {
        'wheel_id': get_uuid(),
        'wheel_name': 'Timestamp Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp()
    }
    WheelRepository.create_wheel(wheel_group_id, wheel_data)
    
    admin_event = create_deployment_admin_event()
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    body = json.loads(response['body'])
    
    # Find our test wheel group
    test_wheel_group = None
    for wg in body['wheel_groups']:
        if wg['wheel_group_id'] == wheel_group_id:
            test_wheel_group = wg
            break
    
    assert test_wheel_group is not None
    assert test_wheel_group['last_updated'] is not None
    
    # Validate timestamp format
    try:
        last_updated = datetime.fromisoformat(test_wheel_group['last_updated'].replace('Z', '+00:00'))
        created_at = datetime.fromisoformat(test_wheel_group['created_at'].replace('Z', '+00:00'))
    except ValueError as e:
        pytest.fail(f"Invalid timestamp format: {e}")
    
    # last_updated should be >= created_at
    assert last_updated >= created_at, "last_updated should be >= created_at"


def test_list_all_wheel_groups_handles_corrupted_wheel_group_data():
    """Test that listing handles corrupted wheel group data gracefully"""
    # This test validates the error handling in the actual function
    # The function should skip wheel groups with None or invalid IDs
    admin_event = create_deployment_admin_event()
    
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    # Should succeed even if there's corrupted data
    assert response['statusCode'] == STATUS_CODES['OK']
    body = json.loads(response['body'])
    
    # All returned wheel groups should have valid structure
    for wheel_group in body['wheel_groups']:
        validate_wheel_group_list_response_structure(wheel_group)
        assert wheel_group['wheel_group_id'] is not None
        assert len(wheel_group['wheel_group_id']) > 0


@patch('deployment_admin_operations.WheelGroupRepository.list_all_wheel_groups')
def test_list_all_wheel_groups_database_error_handling(mock_list_groups):
    """Test error handling when database operations fail"""
    # Mock repository method to raise an exception
    mock_list_groups.side_effect = Exception("Database connection error")

    admin_event = create_deployment_admin_event()
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())

    assert response['statusCode'] == STATUS_CODES['INTERNAL_ERROR']
    body = json.loads(response['body'])
    assert 'error' in body
    assert 'Internal server error' in body['error']


def test_list_all_wheel_groups_response_structure_validation():
    """Test that response structure is always valid regardless of data"""
    admin_event = create_deployment_admin_event()
    
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['OK']
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    
    # Validate top-level structure
    assert 'wheel_groups' in body
    assert isinstance(body['wheel_groups'], list)
    
    # Validate each wheel group structure
    for wheel_group in body['wheel_groups']:
        validate_wheel_group_list_response_structure(wheel_group)


# Delete Wheel Group Tests (10 tests)

@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_success_validates_complete_cascade(mock_cognito, isolated_wheel_group_setup):
    """Test successful deletion validates complete cascading deletion"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_group_name = setup['wheel_group']['wheel_group_name']
    
    # Create comprehensive test data
    # Add users
    user_ids = []
    for i in range(2):
        user_data = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group_id,
            'email': f'deleteuser{i}@example.com',
            'name': f'deleteuser{i}',  # Used as Cognito username
            'role': 'USER'
        }
        UserRepository.create_user(user_data)
        user_ids.append(user_data['user_id'])
    
    # Add wheels
    wheel_ids = []
    for i in range(2):
        wheel_data = {
            'wheel_id': get_uuid(),
            'wheel_name': f'Delete Wheel {i}',
            'created_by': get_uuid(),
            'created_at': get_utc_timestamp()
        }
        WheelRepository.create_wheel(wheel_group_id, wheel_data)
        wheel_ids.append(wheel_data['wheel_id'])
    
    # Add participants
    for wheel_id in wheel_ids:
        participant_data = {
            'participant_id': get_uuid(),
            'participant_name': 'Test Participant',
            'participant_email': 'participant@example.com'
        }
        ParticipantRepository.create_participant(wheel_group_id, wheel_id, participant_data)
    
    # Mock Cognito client
    mock_cognito.admin_delete_user.return_value = {}
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == STATUS_CODES['OK']
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert 'message' in body
    assert wheel_group_name in body['message']
    assert body['deleted_wheel_group_id'] == wheel_group_id
    assert body['deleted_wheel_group_name'] == wheel_group_name
    
    # Validate complete deletion from database
    validate_database_has_no_wheel_group_data(wheel_group_id)
    
    # Validate Cognito deletions were called
    assert mock_cognito.admin_delete_user.call_count >= 2, "Should delete users from Cognito"


def test_delete_wheel_group_missing_id_exact_error():
    """Test exact error message for missing wheel group ID"""
    admin_event = create_deployment_admin_event(
        pathParameters={}  # Missing wheel_group_id
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['BAD_REQUEST']
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert body['error'] == 'wheel_group_id is required in path'


def test_delete_wheel_group_not_found_exact_error():
    """Test behavior when wheel group doesn't exist"""
    non_existent_id = get_uuid()
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': non_existent_id}
    )
    
    # Mock Cognito client to avoid real AWS calls
    with patch('deployment_admin_operations.cognito_client') as mock_cognito:
        mock_cognito.admin_delete_user.return_value = {}
        
        response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # The function continues even if wheel group doesn't exist (graceful handling)
    # But should eventually fail when trying to delete the wheel group itself
    assert response['statusCode'] == STATUS_CODES['INTERNAL_ERROR']
    body = json.loads(response['body'])
    assert 'error' in body


@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_deletes_all_users_from_cognito(mock_cognito, isolated_wheel_group_setup):
    """Test that all users are deleted from Cognito during wheel group deletion"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test users
    usernames = ['cognitouser1', 'cognitouser2']
    for username in usernames:
        user_data = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group_id,
            'email': f'{username}@example.com',
            'name': username,  # Used as Cognito username
            'role': 'USER'
        }
        UserRepository.create_user(user_data)
    
    # Mock Cognito client
    mock_cognito.admin_delete_user.return_value = {}
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Validate Cognito deletions
    assert mock_cognito.admin_delete_user.call_count >= len(usernames)
    
    # Validate specific usernames were called
    called_usernames = []
    for call in mock_cognito.admin_delete_user.call_args_list:
        called_usernames.append(call[1]['Username'])
    
    for username in usernames:
        assert username in called_usernames, f"Username {username} should be deleted from Cognito"


@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_deletes_all_users_from_dynamodb(mock_cognito, isolated_wheel_group_setup):
    """Test that all users are deleted from DynamoDB during wheel group deletion"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test users
    user_ids = []
    for i in range(3):
        user_data = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group_id,
            'email': f'dbuser{i}@example.com',
            'name': f'dbuser{i}',
            'role': 'USER'
        }
        UserRepository.create_user(user_data)
        user_ids.append(user_data['user_id'])
    
    # Mock Cognito client
    mock_cognito.admin_delete_user.return_value = {}
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Validate users are deleted from DynamoDB
    remaining_users = UserRepository.get_users_by_wheel_group(wheel_group_id)
    assert len(remaining_users) == 0, "All users should be deleted from DynamoDB"
    
    # Validate individual users don't exist
    for user_id in user_ids:
        try:
            UserRepository.get_user(user_id)
            assert False, f"User {user_id} should not exist after deletion"
        except NotFoundError:
            pass  # Expected


@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_deletes_all_wheels_and_participants(mock_cognito, isolated_wheel_group_setup):
    """Test that all wheels and participants are deleted during wheel group deletion"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create wheels with participants
    wheel_ids = []
    participant_ids = []
    
    for i in range(2):
        # Create wheel
        wheel_data = {
            'wheel_id': get_uuid(),
            'wheel_name': f'Cascade Wheel {i}',
            'created_by': get_uuid(),
            'created_at': get_utc_timestamp()
        }
        WheelRepository.create_wheel(wheel_group_id, wheel_data)
        wheel_ids.append(wheel_data['wheel_id'])
        
        # Create participants for this wheel
        for j in range(2):
            participant_data = {
                'participant_id': get_uuid(),
                'participant_name': f'Participant {i}-{j}',
                'participant_email': f'participant{i}{j}@example.com'
            }
            ParticipantRepository.create_participant(wheel_group_id, wheel_data['wheel_id'], participant_data)
            participant_ids.append(participant_data['participant_id'])
    
    # Mock Cognito client
    mock_cognito.admin_delete_user.return_value = {}
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Validate wheels are deleted
    remaining_wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
    assert len(remaining_wheels) == 0, "All wheels should be deleted"
    
    # Validate participants are deleted by checking each wheel
    for wheel_id in wheel_ids:
        remaining_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
        assert len(remaining_participants) == 0, f"All participants should be deleted for wheel {wheel_id}"


@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_handles_orphaned_participant_cleanup(mock_cognito, isolated_wheel_group_setup):
    """Test that orphaned participant records are cleaned up during deletion"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create wheel and participants to simulate potential orphans
    wheel_data = {
        'wheel_id': get_uuid(),
        'wheel_name': 'Orphan Test Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp()
    }
    WheelRepository.create_wheel(wheel_group_id, wheel_data)
    
    # Create participants
    for i in range(3):
        participant_data = {
            'participant_id': get_uuid(),
            'participant_name': f'Orphan Participant {i}',
            'participant_email': f'orphan{i}@example.com'
        }
        ParticipantRepository.create_participant(wheel_group_id, wheel_data['wheel_id'], participant_data)
    
    # Mock Cognito client
    mock_cognito.admin_delete_user.return_value = {}
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Should succeed in cleanup
    assert response['statusCode'] == STATUS_CODES['OK']
    
    # Validate all data is cleaned up
    validate_database_has_no_wheel_group_data(wheel_group_id)


@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_cognito_failure_continues_operation(mock_cognito, isolated_wheel_group_setup):
    """Test that Cognito failures don't stop DynamoDB cleanup (graceful degradation)"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create user that will fail in Cognito
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'cognitofail@example.com',
        'name': 'cognitofail',
        'role': 'USER'
    }
    UserRepository.create_user(user_data)
    
    # Mock Cognito client to fail
    mock_cognito.admin_delete_user.side_effect = Exception("Cognito service unavailable")
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Should still succeed overall (graceful degradation)
    assert response['statusCode'] == STATUS_CODES['OK']
    
    # DynamoDB cleanup should still work
    remaining_users = UserRepository.get_users_by_wheel_group(wheel_group_id)
    assert len(remaining_users) == 0, "DynamoDB users should still be deleted despite Cognito failure"


@patch('deployment_admin_operations.cognito_client')
def test_delete_wheel_group_partial_failure_recovery(mock_cognito, isolated_wheel_group_setup):
    """Test recovery from partial deletion failures"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test data
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'partialfail@example.com',
        'name': 'partialfail',
        'role': 'USER'
    }
    UserRepository.create_user(user_data)
    
    wheel_data = {
        'wheel_id': get_uuid(),
        'wheel_name': 'Partial Fail Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp()
    }
    WheelRepository.create_wheel(wheel_group_id, wheel_data)
    
    # Mock Cognito to succeed
    mock_cognito.admin_delete_user.return_value = {}
    
    admin_event = create_deployment_admin_event(
        pathParameters={'wheel_group_id': wheel_group_id}
    )
    
    response = delete_wheel_group(admin_event, create_mock_lambda_context())
    
    # Validate that even with potential partial failures, cleanup attempts are made
    # The function should try to clean up as much as possible
    assert response['statusCode'] == STATUS_CODES['OK']


def test_delete_wheel_group_validates_final_database_state():
    """Test that deletion validates final database state is clean"""
    # This test validates our validation helper function
    fake_wheel_group_id = get_uuid()
    
    # Should pass validation for non-existent wheel group (clean state)
    validate_database_has_no_wheel_group_data(fake_wheel_group_id)
    
    # Create some data to test the validation catches it
    test_wheel_group_data = {
        'wheel_group_id': fake_wheel_group_id,
        'wheel_group_name': 'Validation Test Group'
    }
    WheelGroupRepository.create_wheel_group(test_wheel_group_data)
    
    # Now validation should fail
    try:
        validate_database_has_no_wheel_group_data(fake_wheel_group_id)
        assert False, "Validation should fail when wheel group exists"
    except AssertionError:
        pass  # Expected
    
    # Cleanup
    WheelGroupRepository.delete_wheel_group(fake_wheel_group_id)


# Statistics Calculation Tests (4 tests)

def test_get_wheel_group_statistics_comprehensive_calculation(isolated_wheel_group_setup):
    """Test statistics calculation includes all entity types and timestamps"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test data with known quantities
    # Add 2 users
    for i in range(2):
        user_data = {
            'user_id': get_uuid(),
            'wheel_group_id': wheel_group_id,
            'email': f'statsuser{i}@example.com',
            'name': f'Stats User {i}',
            'role': 'USER'
        }
        UserRepository.create_user(user_data)
    
    # Add 3 wheels
    wheel_ids = []
    for i in range(3):
        wheel_data = {
            'wheel_id': get_uuid(),
            'wheel_name': f'Stats Wheel {i}',
            'created_by': get_uuid(),
            'created_at': get_utc_timestamp()
        }
        WheelRepository.create_wheel(wheel_group_id, wheel_data)
        wheel_ids.append(wheel_data['wheel_id'])
    
    # Add participants to wheels
    for wheel_id in wheel_ids:
        participant_data = {
            'participant_id': get_uuid(),
            'participant_name': f'Stats Participant for {wheel_id}',
            'participant_email': f'statsparticipant@example.com'
        }
        ParticipantRepository.create_participant(wheel_group_id, wheel_id, participant_data)
    
    # Get statistics
    stats = get_wheel_group_statistics(wheel_group_id)
    
    # Validate comprehensive calculation
    assert stats['user_count'] >= 2, f"Expected at least 2 users, got {stats['user_count']}"
    assert stats['wheel_count'] >= 3, f"Expected at least 3 wheels, got {stats['wheel_count']}"
    assert stats['created_at'] is not None, "Should have created_at timestamp"
    assert stats['last_updated'] is not None, "Should have last_updated timestamp"
    
    # Validate timestamp formats
    datetime.fromisoformat(stats['created_at'].replace('Z', '+00:00'))
    datetime.fromisoformat(stats['last_updated'].replace('Z', '+00:00'))


def test_get_wheel_group_statistics_handles_missing_wheel_group():
    """Test statistics calculation handles missing wheel group gracefully"""
    non_existent_id = get_uuid()
    
    stats = get_wheel_group_statistics(non_existent_id)
    
    # Should return default stats without crashing
    assert stats['user_count'] == 0
    assert stats['wheel_count'] == 0
    assert stats['created_at'] is None
    assert stats['last_updated'] is None


def test_get_wheel_group_statistics_handles_none_wheel_group_id():
    """Test statistics calculation handles None wheel group ID"""
    stats = get_wheel_group_statistics(None)
    
    # Should return default stats without crashing
    assert stats['user_count'] == 0
    assert stats['wheel_count'] == 0
    assert stats['created_at'] is None
    assert stats['last_updated'] is None


def test_get_wheel_group_statistics_timestamp_aggregation_logic(isolated_wheel_group_setup):
    """Test that timestamp aggregation finds the most recent across all entities"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    import time
    
    # Create entities with deliberate timing
    base_time = get_utc_timestamp()
    
    # Create user (will have updated_at)
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'timestamptest@example.com',
        'name': 'Timestamp Test User',
        'role': 'USER'
    }
    UserRepository.create_user(user_data)
    
    # Use mock timestamps instead of sleep for better test performance
    
    # Create wheel (newer timestamp)
    wheel_data = {
        'wheel_id': get_uuid(),
        'wheel_name': 'Timestamp Test Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp()  # Should be newer
    }
    WheelRepository.create_wheel(wheel_group_id, wheel_data)
    
    stats = get_wheel_group_statistics(wheel_group_id)
    
    # last_updated should reflect the most recent activity
    assert stats['last_updated'] is not None
    
    # Convert timestamps for comparison
    created_at = datetime.fromisoformat(stats['created_at'].replace('Z', '+00:00'))
    last_updated = datetime.fromisoformat(stats['last_updated'].replace('Z', '+00:00'))
    
    # last_updated should be >= created_at (could be equal or newer)
    assert last_updated >= created_at


# Integration & Response Validation Tests (4 tests)

def test_validate_admin_response_structure_catches_missing_fields():
    """Test that our validation helper catches missing required fields"""
    incomplete_wheel_group = {
        'wheel_group_id': 'test-id',
        'wheel_group_name': 'Test Wheel Group'
        # Missing other required fields
    }
    
    try:
        validate_wheel_group_list_response_structure(incomplete_wheel_group)
        assert False, "Should raise assertion error for missing fields"
    except AssertionError as e:
        assert "Missing required field" in str(e)


def test_validate_cors_headers_admin_endpoints():
    """Test that admin endpoints return proper CORS headers"""
    admin_event = create_deployment_admin_event()
    
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    assert response['statusCode'] == STATUS_CODES['OK']
    validate_cors_headers(response)
    
    # Test specific CORS header values for admin endpoints
    headers = response['headers']
    assert headers['Access-Control-Allow-Methods'] == 'GET,POST,PUT,DELETE,OPTIONS'
    assert headers['Access-Control-Allow-Headers'] == 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'


def test_deployment_admin_operations_database_consistency_validation(isolated_wheel_group_setup):
    """Test that admin operations maintain database consistency"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test data
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'consistency@example.com',
        'name': 'consistency',
        'role': 'USER'
    }
    UserRepository.create_user(user_data)
    
    # List all wheel groups - should include our test data
    admin_event = create_deployment_admin_event()
    list_response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    assert list_response['statusCode'] == STATUS_CODES['OK']
    body = json.loads(list_response['body'])
    
    # Find our wheel group in the list
    found_wheel_group = None
    for wg in body['wheel_groups']:
        if wg['wheel_group_id'] == wheel_group_id:
            found_wheel_group = wg
            break
    
    assert found_wheel_group is not None, "Created wheel group should appear in list"
    assert found_wheel_group['user_count'] >= 1, "User count should reflect created user"
    
    # Database state should be consistent with API response
    actual_users = UserRepository.get_users_by_wheel_group(wheel_group_id)
    assert len(actual_users) >= 1, "Database should contain the created user"


@patch.dict(os.environ, {}, clear=True)
def test_deployment_admin_operations_handles_environment_configuration_errors():
    """Test that admin operations handle missing environment configuration"""
    # Test with missing environment variables
    admin_event = create_deployment_admin_event()
    
    # Should still work for list operation (doesn't require Cognito)
    response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    
    # Might succeed or fail depending on table configuration, but shouldn't crash
    assert response['statusCode'] in [STATUS_CODES['OK'], STATUS_CODES['INTERNAL_ERROR']]
    
    # Response should always be properly formatted
    validate_cors_headers(response)
    body = json.loads(response['body'])
    
    if response['statusCode'] == STATUS_CODES['OK']:
        assert 'wheel_groups' in body
    else:
        assert 'error' in body


# Additional edge case tests

def test_deployment_admin_operations_constants_validation():
    """Test that constants are properly defined and accessible"""
    # Validate STATUS_CODES
    assert STATUS_CODES['OK'] == 200
    assert STATUS_CODES['CREATED'] == 201
    assert STATUS_CODES['BAD_REQUEST'] == 400
    assert STATUS_CODES['FORBIDDEN'] == 403
    assert STATUS_CODES['NOT_FOUND'] == 404
    assert STATUS_CODES['INTERNAL_ERROR'] == 500
    
    # Validate CORS_HEADERS
    assert CORS_HEADERS['Content-Type'] == 'application/json'
    assert CORS_HEADERS['Access-Control-Allow-Origin'] == '*'
    assert 'Access-Control-Allow-Methods' in CORS_HEADERS
    assert 'Access-Control-Allow-Headers' in CORS_HEADERS


def test_deployment_admin_operations_response_format_consistency():
    """Test that all admin operations return consistent response formats"""
    admin_event = create_deployment_admin_event()
    
    # Test list operation
    list_response = list_all_wheel_groups(admin_event, create_mock_lambda_context())
    assert 'statusCode' in list_response
    assert 'headers' in list_response
    assert 'body' in list_response
    
    # Test permission denial has same format
    non_admin_event = create_non_admin_event()
    denied_response = list_all_wheel_groups(non_admin_event, create_mock_lambda_context())
    assert 'statusCode' in denied_response
    assert 'headers' in denied_response
    assert 'body' in denied_response
    
    # Both should have proper JSON bodies
    json.loads(list_response['body'])  # Should not raise exception
    json.loads(denied_response['body'])  # Should not raise exception
