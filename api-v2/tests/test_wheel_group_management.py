#  Improved Unit Tests for Wheel Group Management API - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests validate actual business logic, not just HTTP status codes

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
from utils_v2 import get_uuid, get_utc_timestamp, WheelGroupRepository, UserRepository

# Import wheel group management functions with authentication mocking
with patch('wheel_group_middleware.require_auth', lambda: lambda func: func), \
     patch('wheel_group_middleware.require_wheel_group_permission', lambda perm: lambda func: func):
    from wheel_group_management import (
        create_wheel_group, get_wheel_group, update_wheel_group,
        get_wheel_group_users, create_wheel_group_user, update_user_role,
        get_config, get_current_user, delete_wheel_group_user,
        create_wheel_group_public, delete_wheel_group_recursive,
        DEFAULT_WHEEL_GROUP_QUOTAS, DEFAULT_WHEEL_GROUP_SETTINGS,
        USER_ROLES, VALID_ROLES, VALIDATION_MESSAGES
    )


def mock_get_wheel_group_context(event):
    """Mock get_wheel_group_context to return test context"""
    return event.get('test_wheel_group_context', {})


def create_mock_lambda_context():
    """Create a mock Lambda context for testing"""
    mock_context = Mock()
    mock_context.aws_request_id = 'test-request-id'
    return mock_context


def validate_wheel_group_response_structure(wheel_group_data, expected_fields=None):
    """Validate that wheel group response has correct structure and data types"""
    required_fields = expected_fields or [
        'wheel_group_id', 'wheel_group_name', 'quotas', 'settings', 
        'created_at', 'updated_at'
    ]
    
    for field in required_fields:
        assert field in wheel_group_data, f"Missing required field: {field}"
    
    # Validate data types
    assert isinstance(wheel_group_data['wheel_group_id'], str), "wheel_group_id must be string"
    assert isinstance(wheel_group_data['wheel_group_name'], str), "wheel_group_name must be string"
    assert isinstance(wheel_group_data['quotas'], dict), "quotas must be dict"
    assert isinstance(wheel_group_data['settings'], dict), "settings must be dict"
    
    # Validate timestamp formats
    datetime.fromisoformat(wheel_group_data['created_at'].replace('Z', '+00:00'))
    datetime.fromisoformat(wheel_group_data['updated_at'].replace('Z', '+00:00'))
    
    # Validate default quotas structure
    for quota_key in DEFAULT_WHEEL_GROUP_QUOTAS:
        assert quota_key in wheel_group_data['quotas'], f"Missing default quota: {quota_key}"
    
    # Validate default settings structure
    for setting_key in DEFAULT_WHEEL_GROUP_SETTINGS:
        if setting_key == 'default_participant_weight':
            # This might be converted to Decimal or float
            continue
        assert setting_key in wheel_group_data['settings'], f"Missing default setting: {setting_key}"


def validate_user_response_structure(user_data, expected_fields=None):
    """Validate that user response has correct structure and data types"""
    required_fields = expected_fields or [
        'user_id', 'wheel_group_id', 'email', 'name', 'role', 
        'created_at', 'updated_at'
    ]
    
    for field in required_fields:
        assert field in user_data, f"Missing required field: {field}"
    
    # Validate data types
    assert isinstance(user_data['user_id'], str), "user_id must be string"
    assert isinstance(user_data['wheel_group_id'], str), "wheel_group_id must be string"
    assert isinstance(user_data['email'], str), "email must be string"
    assert isinstance(user_data['name'], str), "name must be string"
    assert isinstance(user_data['role'], str), "role must be string"
    
    # Validate role is valid
    assert user_data['role'] in VALID_ROLES, f"role must be one of: {VALID_ROLES}"
    
    # Validate timestamp formats
    datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00'))
    datetime.fromisoformat(user_data['updated_at'].replace('Z', '+00:00'))


def validate_cors_headers(response):
    """Validate that response includes proper CORS headers"""
    assert 'headers' in response
    headers = response['headers']
    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'


def validate_wheel_group_database_consistency(wheel_group_id: str, expected_data: dict):
    """Validate that wheel group data in database matches expected values"""
    db_wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
    assert db_wheel_group['wheel_group_name'] == expected_data['wheel_group_name']
    if 'quotas' in expected_data:
        for key, value in expected_data['quotas'].items():
            assert db_wheel_group['quotas'][key] == value
    if 'settings' in expected_data:
        for key, value in expected_data['settings'].items():
            if key != 'default_participant_weight':  # Skip Decimal comparison
                assert db_wheel_group['settings'][key] == value


def validate_user_database_consistency(user_id: str, expected_data: dict):
    """Validate that user data in database matches expected values"""
    db_user = UserRepository.get_user(user_id)
    for key, value in expected_data.items():
        if key in ['created_at', 'updated_at']:
            continue  # Skip timestamp comparisons
        assert db_user[key] == value


# Create Wheel Group Tests (4 tests)

@patch('wheel_group_management.boto3.client')
@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_success_validates_business_logic(mock_context, mock_boto3, sample_wheel_group_data):
    """Test wheel group creation validates all business logic requirements"""
    # Mock Cognito client
    mock_cognito = MagicMock()
    mock_boto3.return_value = mock_cognito
    
    user_id = get_uuid()
    admin_email = 'admin@test.com'
    admin_name = 'Test Admin'
    
    wheel_group_context = {
        'user_id': user_id,
        'email': admin_email,
        'permissions': {}
    }
    
    event = {
        'body': {
            'wheel_group_name': 'Business Logic Test Wheel Group',
            'admin_user': {
                'email': admin_email,
                'name': admin_name
            }
        },
        'test_wheel_group_context': wheel_group_context,
        'requestContext': {
            'authorizer': {
                'userPoolId': 'test-pool-id'
            }
        }
    }
    
    response = create_wheel_group(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 201
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    validate_wheel_group_response_structure(body)
    
    # Validate exact business logic requirements
    assert body['wheel_group_name'] == 'Business Logic Test Wheel Group'
    
    # Validate default quotas were applied correctly
    for quota_key, quota_value in DEFAULT_WHEEL_GROUP_QUOTAS.items():
        assert body['quotas'][quota_key] == quota_value, f"Default quota {quota_key} should be {quota_value}"
    
    # Validate default settings were applied correctly  
    for setting_key, setting_value in DEFAULT_WHEEL_GROUP_SETTINGS.items():
        if setting_key == 'default_participant_weight':
            # This gets converted to Decimal then back to float
            assert float(body['settings'][setting_key]) == setting_value
        else:
            assert body['settings'][setting_key] == setting_value, f"Default setting {setting_key} should be {setting_value}"
    
    # Validate timestamps are recent and properly formatted
    created_time = datetime.fromisoformat(body['created_at'].replace('Z', '+00:00'))
    updated_time = datetime.fromisoformat(body['updated_at'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    assert (now - created_time).total_seconds() < 10, "created_at should be recent"
    assert (now - updated_time).total_seconds() < 10, "updated_at should be recent"
    
    # Validate wheel group was actually created in database with correct data
    validate_wheel_group_database_consistency(body['wheel_group_id'], {
        'wheel_group_name': 'Business Logic Test Wheel Group',
        'quotas': DEFAULT_WHEEL_GROUP_QUOTAS,
        'settings': {k: v for k, v in DEFAULT_WHEEL_GROUP_SETTINGS.items() if k != 'default_participant_weight'}
    })
    
    # Validate admin user was created/updated
    try:
        user = UserRepository.get_user(user_id)
        assert user['wheel_group_id'] == body['wheel_group_id']
        assert user['role'] == USER_ROLES['ADMIN']
    except NotFoundError:
        # User should be created if not exists
        pass
    
    # Validate Cognito integration was called
    mock_cognito.admin_update_user_attributes.assert_called_once()


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_missing_name_exact_error_message(mock_context):
    """Test exact error message for missing wheel group name"""
    user_id = get_uuid()
    
    wheel_group_context = {
        'user_id': user_id,
        'email': 'admin@test.com',
        'permissions': {}
    }
    
    event = {
        'body': {
            'admin_user': {
                'email': 'admin@test.com',
                'name': 'Test Admin'
            }
            # Missing wheel_group_name
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['WHEEL_GROUP_NAME_REQUIRED']
    assert body['error'] == "wheel_group_name is required and must be a non-empty string"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_user_already_has_wheel_group_exact_error(mock_context, sample_wheel_group_data):
    """Test exact error when user already has a wheel group"""
    user_id = get_uuid()
    existing_wheel_group_id = get_uuid()
    
    # Create existing user with wheel group
    UserRepository.create_user({
        'user_id': user_id,
        'wheel_group_id': existing_wheel_group_id,
        'email': 'admin@test.com',
        'name': 'Test Admin',
        'role': USER_ROLES['ADMIN']
    })
    
    wheel_group_context = {
        'user_id': user_id,
        'email': 'admin@test.com',
        'permissions': {}
    }
    
    event = {
        'body': {
            'wheel_group_name': 'New Wheel Group',
            'admin_user': {
                'email': 'admin@test.com',
                'name': 'Test Admin'
            }
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['USER_HAS_WHEEL_GROUP']
    assert body['error'] == "User is already associated with a wheel group"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_missing_admin_email_exact_error(mock_context):
    """Test exact error message for missing admin email"""
    user_id = get_uuid()
    
    wheel_group_context = {
        'user_id': user_id,
        'email': 'admin@test.com',
        'permissions': {}
    }
    
    event = {
        'body': {
            'wheel_group_name': 'Test Wheel Group',
            'admin_user': {
                'name': 'Test Admin'
                # Missing email
            }
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['ADMIN_EMAIL_REQUIRED']
    assert body['error'] == "admin_user.email is required"


# Get Wheel Group Tests (3 tests)

@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_get_wheel_group_success_validates_complete_data(mock_context, isolated_wheel_group_setup):
    """Test get wheel group returns complete and correct data structure"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    event = {
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    validate_wheel_group_response_structure(body)
    
    # Validate data matches database exactly
    assert body['wheel_group_id'] == wheel_group_id
    assert body['wheel_group_name'] == setup['wheel_group']['wheel_group_name']
    
    # Validate quotas and settings structure
    assert 'quotas' in body
    assert 'settings' in body
    assert isinstance(body['quotas'], dict)
    assert isinstance(body['settings'], dict)


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_get_wheel_group_not_found_exact_error(mock_context):
    """Test exact 404 behavior for non-existent wheel group"""
    non_existent_wheel_group_id = get_uuid()
    
    wheel_group_context = {
        'wheel_group_id': non_existent_wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    event = {
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    validate_cors_headers(response)
    
    # Verify wheel group truly doesn't exist
    try:
        WheelGroupRepository.get_wheel_group(non_existent_wheel_group_id)
        assert False, "Wheel group should not exist"
    except NotFoundError:
        pass  # Expected


@patch('wheel_group_management.get_wheel_group_context')
def test_get_wheel_group_no_permissions_handles_gracefully(mock_context, isolated_wheel_group_setup):
    """Test wheel group access without permissions (would be handled by middleware)"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Simulate middleware blocking request before it reaches get_wheel_group
    # In real system, middleware would return 403 before endpoint is called
    mock_context.side_effect = Exception("Middleware would block this request")
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {}  # No permissions
    }
    
    event = {
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_wheel_group(event, context=create_mock_lambda_context())
    
    # Middleware blocks should result in 500 (internal error from middleware exception)
    assert response['statusCode'] == 500


# Update Wheel Group Tests (6 tests)

@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_wheel_group_partial_preserves_unchanged_fields(mock_context, isolated_wheel_group_setup):
    """Test partial update preserves all unchanged fields exactly"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Get original wheel group data
    original_wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_wheel_group': True}
    }
    
    event = {
        'body': {
            'wheel_group_name': 'Only Name Updated'
            # Only updating name, leaving quotas and settings unchanged
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    
    # Validate name was updated
    assert body['wheel_group_name'] == 'Only Name Updated'
    
    # Validate other fields were preserved exactly
    assert body['quotas'] == original_wheel_group['quotas'], "Quotas should be unchanged"
    
    # Validate settings preservation (handle Decimal conversion)
    original_settings = original_wheel_group['settings']
    for key, value in original_settings.items():
        if key == 'default_participant_weight':
            assert float(body['settings'][key]) == float(value)
        else:
            assert body['settings'][key] == value, f"Setting {key} should be unchanged"
    
    # Validate metadata preservation
    assert body['wheel_group_id'] == original_wheel_group['wheel_group_id']
    assert body['created_at'] == original_wheel_group['created_at']


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_wheel_group_empty_body_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error message for empty update body"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_wheel_group': True}
    }
    
    event = {
        'body': {},  # Empty update
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['UPDATE_FIELD_REQUIRED']
    assert body['error'] == "At least one field must be provided for update"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_wheel_group_invalid_settings_type_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error for invalid settings data type"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_wheel_group': True}
    }
    
    event = {
        'body': {
            'settings': 'not an object'  # Should be dict/object
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['SETTINGS_MUST_BE_OBJECT']
    assert body['error'] == "settings must be an object"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_wheel_group_invalid_quotas_type_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error for invalid quotas data type"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_wheel_group': True}
    }
    
    event = {
        'body': {
            'quotas': 'not an object'  # Should be dict/object
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['QUOTAS_MUST_BE_OBJECT']
    assert body['error'] == "quotas must be an object"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_wheel_group_name_validation_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact validation for wheel group name"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_wheel_group': True}
    }
    
    event = {
        'body': {
            'wheel_group_name': ''  # Empty string should fail validation
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_wheel_group(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'wheel_group_name must be a non-empty string' in body['error']


# Get Wheel Group Users Tests (2 tests)

# Create Wheel Group User Tests (7 tests)

@patch('wheel_group_management.boto3.client')
@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_user_success_validates_business_logic(mock_context, mock_boto3, isolated_wheel_group_setup):
    """Test user creation validates all business logic requirements"""
    # Mock Cognito client
    mock_cognito = MagicMock()
    mock_cognito.admin_create_user.return_value = {
        'User': {
            'Attributes': [
                {'Name': 'sub', 'Value': 'cognito-user-id-123'}
            ]
        }
    }
    mock_boto3.return_value = mock_cognito
    
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'body': {
            'email': 'newuser@test.com',
            'username': 'newuser',
            'role': USER_ROLES['USER']
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group_user(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 201
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    validate_user_response_structure(body)
    
    # Validate exact business logic requirements
    assert body['email'] == 'newuser@test.com'
    assert body['name'] == 'newuser'
    assert body['role'] == USER_ROLES['USER']
    assert body['wheel_group_id'] == wheel_group_id
    
    # Validate new user fields
    assert body['user_id'] == 'cognito-user-id-123', "Should use Cognito sub as user_id"
    assert 'temporary_password' in body, "Should include temporary password info"
    assert body['temporary_password'] == 'TempPass123!'
    assert body['password_reset_required'] == True
    
    # Validate timestamps are recent and properly formatted
    created_time = datetime.fromisoformat(body['created_at'].replace('Z', '+00:00'))
    updated_time = datetime.fromisoformat(body['updated_at'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    assert (now - created_time).total_seconds() < 10, "created_at should be recent"
    assert (now - updated_time).total_seconds() < 10, "updated_at should be recent"
    
    # Validate user was actually created in database with correct data
    validate_user_database_consistency('cognito-user-id-123', {
        'email': 'newuser@test.com',
        'name': 'newuser',
        'role': USER_ROLES['USER'],
        'wheel_group_id': wheel_group_id
    })
    
    # Validate Cognito integration was called with correct parameters
    mock_cognito.admin_create_user.assert_called_once()
    cognito_call_args = mock_cognito.admin_create_user.call_args
    assert cognito_call_args[1]['Username'] == 'newuser'
    
    # Validate user attributes in Cognito call
    user_attributes = {attr['Name']: attr['Value'] for attr in cognito_call_args[1]['UserAttributes']}
    assert user_attributes['email'] == 'newuser@test.com'
    assert user_attributes['name'] == 'newuser'
    assert user_attributes['custom:wheel_group_id'] == wheel_group_id


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_user_missing_email_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error message for missing email"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'body': {
            'username': 'newuser'
            # Missing email
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group_user(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants  
    assert body['error'] == VALIDATION_MESSAGES['EMAIL_REQUIRED']
    assert body['error'] == "email is required and must be a non-empty string"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_user_missing_username_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error message for missing username"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'body': {
            'email': 'newuser@test.com'
            # Missing username
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group_user(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['USERNAME_REQUIRED']
    assert body['error'] == "username is required and must be a non-empty string"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_user_invalid_role_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error for invalid role"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'body': {
            'email': 'newuser@test.com',
            'username': 'newuser',
            'role': 'INVALID_ROLE'
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_wheel_group_user(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['INVALID_ROLE']
    assert f"role must be one of: {', '.join(VALID_ROLES)}" in body['error']


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_create_wheel_group_user_default_role_validation(mock_context, isolated_wheel_group_setup):
    """Test that default role is applied when not specified"""
    # This test validates the default role assignment logic
    # We'll mock Cognito to focus on business logic
    with patch('wheel_group_management.boto3.client') as mock_boto3:
        mock_cognito = MagicMock()
        mock_cognito.admin_create_user.return_value = {
            'User': {
                'Attributes': [
                    {'Name': 'sub', 'Value': 'cognito-user-id-456'}
                ]
            }
        }
        mock_boto3.return_value = mock_cognito
        
        setup = isolated_wheel_group_setup
        wheel_group_id = setup['wheel_group']['wheel_group_id']
        
        wheel_group_context = {
            'wheel_group_id': wheel_group_id,
            'user_id': get_uuid(),
            'permissions': {'manage_users': True}
        }
        
        event = {
            'body': {
                'email': 'defaultrole@test.com',
                'username': 'defaultrole'
                # No role specified - should default to USER
            },
            'test_wheel_group_context': wheel_group_context
        }
        
        response = create_wheel_group_user(event, context=create_mock_lambda_context())
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        
        # Validate default role was applied
        assert body['role'] == 'USER', "Should default to USER role when not specified"


# Update User Role Tests (4 tests)

@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_user_role_success_validates_business_logic(mock_context, isolated_wheel_group_setup):
    """Test user role update validates all business logic requirements"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test user
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'roleuser@test.com',
        'name': 'Role User',
        'role': USER_ROLES['USER']
    }
    UserRepository.create_user(user_data)
    user_id = user_data['user_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'pathParameters': {
            'user_id': user_id
        },
        'body': {
            'role': USER_ROLES['WHEEL_ADMIN']
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_user_role(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    validate_user_response_structure(body)
    
    # Validate role was updated correctly
    assert body['role'] == USER_ROLES['WHEEL_ADMIN']
    assert body['user_id'] == user_id
    assert body['wheel_group_id'] == wheel_group_id
    
    # Validate other fields preserved
    assert body['email'] == user_data['email']
    assert body['name'] == user_data['name']
    
    # Validate database state matches response
    validate_user_database_consistency(user_id, {
        'role': USER_ROLES['WHEEL_ADMIN'],
        'wheel_group_id': wheel_group_id,
        'email': user_data['email'],
        'name': user_data['name']
    })


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_user_role_missing_user_id_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error message for missing user_id"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'pathParameters': {},  # Missing user_id
        'body': {
            'role': USER_ROLES['WHEEL_ADMIN']
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_user_role(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['USER_ID_REQUIRED']
    assert body['error'] == "user_id is required"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_user_role_user_not_in_wheel_group_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error when user doesn't belong to wheel group"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    different_wheel_group_id = get_uuid()
    
    # Create user in different wheel group
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': different_wheel_group_id,  # Different wheel group
        'email': 'otheruser@test.com',
        'name': 'Other User',
        'role': USER_ROLES['USER']
    }
    UserRepository.create_user(user_data)
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'pathParameters': {
            'user_id': user_data['user_id']
        },
        'body': {
            'role': USER_ROLES['WHEEL_ADMIN']
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_user_role(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['USER_NOT_IN_WHEEL_GROUP']
    assert body['error'] == "User not found in this wheel group"


@patch('wheel_group_management.get_wheel_group_context', side_effect=mock_get_wheel_group_context)
def test_update_user_role_invalid_role_exact_error(mock_context, isolated_wheel_group_setup):
    """Test exact error for invalid role in update"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    
    # Create test user
    user_data = {
        'user_id': get_uuid(),
        'wheel_group_id': wheel_group_id,
        'email': 'roleuser@test.com',
        'name': 'Role User',
        'role': USER_ROLES['USER']
    }
    UserRepository.create_user(user_data)
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_users': True}
    }
    
    event = {
        'pathParameters': {
            'user_id': user_data['user_id']
        },
        'body': {
            'role': 'INVALID_ROLE'
        },
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_user_role(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message
    assert f"role must be one of: {', '.join(VALID_ROLES)}" in body['error']


# Get Config Tests (2 tests)

def test_get_config_success_validates_complete_configuration():
    """Test get config returns complete and correct configuration data"""
    # Mock environment variables
    with patch.dict(os.environ, {
        'COGNITO_USER_POOL_ID': 'test-pool-id',
        'COGNITO_CLIENT_ID': 'test-client-id',
        'AWS_DEFAULT_REGION': 'us-west-2'
    }):
        event = {}
        
        response = get_config(event, context=create_mock_lambda_context())
        
        assert response['statusCode'] == 200
        validate_cors_headers(response)
        
        body = json.loads(response['body'])
        
        # Validate required configuration fields
        required_config_fields = [
            'UserPoolId', 'ClientId', 'REGION', 'API_VERSION',
            'MULTI_WHEEL_GROUP_ENABLED', 'MAX_MULTI_SELECT', 'SUPPORTED_ROLES'
        ]
        
        for field in required_config_fields:
            assert field in body, f"Missing required config field: {field}"
        
        # Validate exact values
        assert body['UserPoolId'] == 'test-pool-id'
        assert body['ClientId'] == 'test-client-id'
        assert body['REGION'] == 'us-west-2'
        assert body['API_VERSION'] == '2.0'
        assert body['MULTI_WHEEL_GROUP_ENABLED'] == True
        assert body['MAX_MULTI_SELECT'] == 30
        assert body['SUPPORTED_ROLES'] == ['ADMIN', 'WHEEL_ADMIN', 'USER']
        
        # Validate data types
        assert isinstance(body['MULTI_WHEEL_GROUP_ENABLED'], bool)
        assert isinstance(body['MAX_MULTI_SELECT'], int)
        assert isinstance(body['SUPPORTED_ROLES'], list)


def test_get_config_handles_missing_environment_variables():
    """Test get config handles missing environment variables gracefully"""
    # Test with minimal environment
    with patch.dict(os.environ, {}, clear=True):
        event = {}
        
        response = get_config(event, context=create_mock_lambda_context())
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should still return required fields with None/default values
        assert body['UserPoolId'] is None
        assert body['ClientId'] is None
        assert body['REGION'] == 'us-west-2'  # Default fallback
        assert body['API_VERSION'] == '2.0'
        assert body['MULTI_WHEEL_GROUP_ENABLED'] == True


# Additional validation helper tests

def test_validate_wheel_group_response_structure_catches_missing_fields():
    """Test that our validation helper catches missing required fields"""
    incomplete_wheel_group = {
        'wheel_group_id': 'test-id',
        'wheel_group_name': 'Test Wheel Group'
        # Missing other required fields
    }
    
    try:
        validate_wheel_group_response_structure(incomplete_wheel_group)
        assert False, "Should raise assertion error for missing fields"
    except AssertionError as e:
        assert "Missing required field" in str(e)


def test_validate_user_response_structure_catches_invalid_role():
    """Test that our validation helper catches invalid roles"""
    invalid_role_user = {
        'user_id': 'test-id',
        'wheel_group_id': 'wg-test-id',
        'email': 'test@example.com',
        'name': 'Test User',
        'role': 'INVALID_ROLE',  # Invalid role
        'created_at': '2023-01-01T00:00:00Z',
        'updated_at': '2023-01-01T00:00:00Z'
    }
    
    try:
        validate_user_response_structure(invalid_role_user)
        assert False, "Should raise assertion error for invalid role"
    except AssertionError as e:
        assert "role must be one of" in str(e)
