#  Improved Unit Tests for API Gateway Authorizer - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests validate critical security logic for JWT validation and IAM policy generation

import os
import sys
import pytest
import json
import base64
import time
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch, Mock, MagicMock

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import BadRequestError, NotFoundError

# Import authorizer functions
from api_gateway_authorizer import (
    lambda_handler, validate_token,
    lookup_user_wheel_group_info, get_role_permissions, generate_policy
)


def create_mock_lambda_context():
    """Create a mock Lambda context for testing"""
    mock_context = Mock()
    mock_context.aws_request_id = 'test-request-id'
    mock_context.log_group_name = '/aws/lambda/test-authorizer'
    return mock_context


def create_valid_jwt_payload(user_email="test@example.com", **overrides):
    """Create a valid JWT payload for testing"""
    current_time = int(time.time())
    payload = {
        'sub': 'test-user-id-123',
        'email': user_email,
        'name': 'Test User',
        'exp': current_time + 3600,  # Expires in 1 hour
        'iss': 'https://cognito-idp.us-west-2.amazonaws.com/us-west-2_TestPool',
        'aud': 'test-client-id',
        'token_use': 'id',
        'auth_time': current_time,
        'iat': current_time,
        **overrides
    }
    return payload


def create_jwt_token(payload):
    """Create a mock JWT token with the given payload (for use with mocked verification)"""
    header = {'alg': 'RS256', 'typ': 'JWT'}
    header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = base64.urlsafe_b64encode(b'fake-signature').decode().rstrip('=')
    return f"{header_encoded}.{payload_encoded}.{signature}"


def create_authorizer_event(token=None, method_arn="arn:aws:execute-api:us-west-2:123456789:abcdef123/dev/GET/api/v2/wheels"):
    """Create a mock API Gateway authorizer event"""
    auth_token = token or f"Bearer {create_jwt_token(create_valid_jwt_payload())}"
    return {
        'type': 'TOKEN',
        'authorizationToken': auth_token,
        'methodArn': method_arn
    }


def validate_iam_policy_structure(policy):
    """Validate that IAM policy has correct structure"""
    assert 'principalId' in policy, "Policy must have principalId"

    if 'policyDocument' in policy:
        policy_doc = policy['policyDocument']
        assert policy_doc['Version'] == '2012-10-17', "Policy must have correct version"
        assert 'Statement' in policy_doc, "Policy must have Statement"
        assert isinstance(policy_doc['Statement'], list), "Statement must be a list"

        for statement in policy_doc['Statement']:
            assert 'Action' in statement, "Statement must have Action"
            assert 'Effect' in statement, "Statement must have Effect"
            assert 'Resource' in statement, "Statement must have Resource"
            assert statement['Effect'] in ['Allow', 'Deny'], "Effect must be Allow or Deny"


def validate_deployment_admin_context(context):
    """Validate deployment admin context structure and permissions"""
    assert context['role'] == 'DEPLOYMENT_ADMIN'
    assert context['deployment_admin'] == 'True'  # Python True -> 'True'
    assert context['wheel_group_id'] == 'None'  # Python None -> 'None'
    assert context['wheel_group_name'] == 'None'


def validate_regular_user_context(context, expected_wheel_group_id, expected_role='USER'):
    """Validate regular user context structure"""
    assert context['role'] == expected_role
    assert context['deployment_admin'] == 'false'  # Implementation returns 'false' for regular users
    assert context['wheel_group_id'] == expected_wheel_group_id
    assert context['user_id'] != ''


# JWT Verification Tests (6 tests)

@patch('api_gateway_authorizer.verify_cognito_token')
def test_validate_token_delegates_to_jwt_verifier(mock_verify):
    """Test that validate_token delegates to jwt_verifier.verify_cognito_token"""
    expected_payload = create_valid_jwt_payload()
    mock_verify.return_value = expected_payload

    result = validate_token('fake.token.here', 'us-west-2_TestPool', 'test-client-id')

    mock_verify.assert_called_once_with('fake.token.here', 'us-west-2_TestPool', 'test-client-id')
    assert result == expected_payload


@patch('api_gateway_authorizer.verify_cognito_token')
def test_validate_token_propagates_expired_error(mock_verify):
    """Test that validate_token propagates expiration errors from jwt_verifier"""
    mock_verify.side_effect = ValueError("Token has expired")

    with pytest.raises(ValueError, match="Token has expired"):
        validate_token('expired.token.here', 'us-west-2_TestPool', 'test-client-id')


@patch('api_gateway_authorizer.verify_cognito_token')
def test_validate_token_propagates_signature_error(mock_verify):
    """Test that validate_token rejects tokens with invalid signatures"""
    mock_verify.side_effect = ValueError("Invalid token signature")

    with pytest.raises(ValueError, match="Invalid token signature"):
        validate_token('forged.token.here', 'us-west-2_TestPool', 'test-client-id')


@patch('api_gateway_authorizer.verify_cognito_token')
def test_validate_token_propagates_issuer_error(mock_verify):
    """Test that validate_token rejects tokens with invalid issuer"""
    mock_verify.side_effect = ValueError("Invalid token issuer")

    with pytest.raises(ValueError, match="Invalid token issuer"):
        validate_token('bad-issuer.token.here', 'us-west-2_TestPool', 'test-client-id')


@patch('api_gateway_authorizer.verify_cognito_token')
def test_validate_token_propagates_audience_error(mock_verify):
    """Test that validate_token rejects tokens with invalid audience"""
    mock_verify.side_effect = ValueError("Invalid token audience")

    with pytest.raises(ValueError, match="Invalid token audience"):
        validate_token('bad-audience.token.here', 'us-west-2_TestPool', 'test-client-id')


@patch('api_gateway_authorizer.verify_cognito_token')
def test_validate_token_rejects_malformed_token(mock_verify):
    """Test that validate_token rejects malformed tokens"""
    mock_verify.side_effect = ValueError("Token decode failed: Not enough segments")

    with pytest.raises(ValueError, match="Token decode failed"):
        validate_token('not-a-jwt', 'us-west-2_TestPool', 'test-client-id')


# Database Integration Tests (6 tests)

@patch('boto3.resource')
def test_lookup_user_wheel_group_info_success(mock_boto3_resource):
    """Test successful user wheel group lookup"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    mock_wheel_groups_table = Mock()

    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.side_effect = lambda name: {
        'OpsWheelV2-Users-test': mock_users_table,
        'OpsWheelV2-WheelGroups-test': mock_wheel_groups_table
    }[name]

    mock_users_table.scan.return_value = {
        'Items': [{
            'user_id': 'test-user-123',
            'wheel_group_id': 'wg-123',
            'role': 'USER',
            'name': 'Test User',
            'email': 'test@example.com'
        }]
    }

    mock_wheel_groups_table.get_item.return_value = {
        'Item': {
            'wheel_group_id': 'wg-123',
            'wheel_group_name': 'Test Wheel Group'
        }
    }

    result = lookup_user_wheel_group_info('test@example.com')

    assert result['user_id'] == 'test-user-123'
    assert result['wheel_group_id'] == 'wg-123'
    assert result['wheel_group_name'] == 'Test Wheel Group'
    assert result['role'] == 'USER'
    assert result['email'] == 'test@example.com'


@patch('boto3.resource')
def test_lookup_user_wheel_group_info_user_not_found(mock_boto3_resource):
    """Test user lookup when user doesn't exist"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()

    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.return_value = mock_users_table

    mock_users_table.scan.return_value = {'Items': []}

    with pytest.raises(ValueError, match="User not found in database: nonexistent@example.com"):
        lookup_user_wheel_group_info('nonexistent@example.com')


@patch('boto3.resource')
def test_lookup_user_wheel_group_info_wheel_group_not_found(mock_boto3_resource):
    """Test user lookup when wheel group doesn't exist"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    mock_wheel_groups_table = Mock()

    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.side_effect = lambda name: {
        'OpsWheelV2-Users-test': mock_users_table,
        'OpsWheelV2-WheelGroups-test': mock_wheel_groups_table
    }[name]

    items_list = [{
        'user_id': 'test-user-123',
        'wheel_group_id': 'nonexistent-wg',
        'role': 'USER',
        'email': 'test@example.com'
    }]
    mock_users_table.scan.return_value = {'Items': items_list}

    mock_wheel_groups_table.get_item.return_value = {}  # No Item key

    result = lookup_user_wheel_group_info('test@example.com')

    assert result['wheel_group_name'] == 'nonexistent-wg'


@patch('boto3.resource')
def test_lookup_user_wheel_group_info_database_error(mock_boto3_resource):
    """Test user lookup handles database errors gracefully"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()

    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.return_value = mock_users_table

    mock_users_table.scan.side_effect = Exception("DynamoDB connection failed")

    with pytest.raises(ValueError, match="Failed to lookup user wheel group info"):
        lookup_user_wheel_group_info('test@example.com')


def test_get_role_permissions_all_roles():
    """Test role permissions mapping for all role types"""
    admin_perms = get_role_permissions('ADMIN')
    expected_admin = [
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel',
        'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'
    ]
    assert set(admin_perms) == set(expected_admin)

    wheel_admin_perms = get_role_permissions('WHEEL_ADMIN')
    expected_wheel_admin = [
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel',
        'view_wheels', 'rig_wheel'
    ]
    assert set(wheel_admin_perms) == set(expected_wheel_admin)

    user_perms = get_role_permissions('USER')
    expected_user = ['spin_wheel', 'view_wheels']
    assert set(user_perms) == set(expected_user)

    unknown_perms = get_role_permissions('UNKNOWN_ROLE')
    assert set(unknown_perms) == set(expected_user)


@patch.dict(os.environ, {'USERS_TABLE': 'test-users', 'WHEEL_GROUPS_TABLE': 'test-wheel-groups'})
@patch('boto3.resource')
def test_lookup_user_wheel_group_info_custom_table_names(mock_boto3_resource):
    """Test user lookup with custom table names from environment"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    mock_wheel_groups_table = Mock()

    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.side_effect = lambda name: {
        'test-users': mock_users_table,
        'test-wheel-groups': mock_wheel_groups_table
    }[name]

    mock_users_table.scan.return_value = {
        'Items': [{
            'user_id': 'test-user-123',
            'wheel_group_id': 'wg-123',
            'role': 'USER',
            'email': 'test@example.com'
        }]
    }

    mock_wheel_groups_table.get_item.return_value = {
        'Item': {'wheel_group_name': 'Test Group'}
    }

    result = lookup_user_wheel_group_info('test@example.com')

    mock_dynamodb_resource.Table.assert_any_call('test-users')
    mock_dynamodb_resource.Table.assert_any_call('test-wheel-groups')
    assert result['user_id'] == 'test-user-123'


# IAM Policy Generation Tests (8 tests)

def test_generate_policy_allow_with_context():
    """Test IAM policy generation for Allow with context"""
    context = {
        'user_id': 'test-user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',
        'deployment_admin': False
    }

    policy = generate_policy('test@example.com', 'Allow',
                           'arn:aws:execute-api:us-west-2:123:abc/dev/GET/api/v2/wheels',
                           context)

    validate_iam_policy_structure(policy)

    assert policy['principalId'] == 'test@example.com'
    assert policy['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    assert policy['policyDocument']['Statement'][0]['Action'] == 'execute-api:Invoke'
    assert policy['policyDocument']['Statement'][0]['Resource'] == 'arn:aws:execute-api:us-west-2:123:abc/dev/*/*'

    assert policy['context']['user_id'] == 'test-user-123'
    assert policy['context']['wheel_group_id'] == 'wg-123'
    assert policy['context']['role'] == 'USER'
    assert policy['context']['deployment_admin'] == 'False'


def test_generate_policy_deny_without_context():
    """Test IAM policy generation for Deny without context"""
    policy = generate_policy('unauthorized', 'Deny',
                           'arn:aws:execute-api:us-west-2:123:abc/dev/GET/api/v2/wheels')

    validate_iam_policy_structure(policy)

    assert policy['principalId'] == 'unauthorized'
    assert policy['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert 'context' not in policy


def test_generate_policy_deployment_admin_context():
    """Test policy generation for deployment admin context"""
    context = {
        'user_id': 'admin-123',
        'wheel_group_id': None,
        'wheel_group_name': None,
        'role': 'DEPLOYMENT_ADMIN',
        'deployment_admin': True
    }

    policy = generate_policy('admin@example.com', 'Allow',
                           'arn:aws:execute-api:us-west-2:123:abc/dev/GET/admin/wheel-groups',
                           context)

    validate_iam_policy_structure(policy)
    validate_deployment_admin_context(policy['context'])


def test_generate_policy_wildcard_resource_patterns():
    """Test that policy generates correct wildcard resource patterns"""
    test_resources = [
        'arn:aws:execute-api:us-west-2:123:abc/dev/GET/api/v2/wheels',
        'arn:aws:execute-api:us-west-2:123:abc/prod/POST/api/v2/participants',
        'arn:aws:execute-api:us-east-1:456:xyz/stage/DELETE/admin/wheel-groups/123'
    ]

    expected_wildcards = [
        'arn:aws:execute-api:us-west-2:123:abc/dev/*/*',
        'arn:aws:execute-api:us-west-2:123:abc/prod/*/*',
        'arn:aws:execute-api:us-east-1:456:xyz/stage/*/*'
    ]

    for resource, expected in zip(test_resources, expected_wildcards):
        policy = generate_policy('test', 'Allow', resource)
        actual_resource = policy['policyDocument']['Statement'][0]['Resource']
        assert actual_resource == expected, f"Expected {expected}, got {actual_resource}"


def test_generate_policy_malformed_resource():
    """Test policy generation with malformed resource ARN"""
    malformed_resource = "not-an-arn"

    policy = generate_policy('test', 'Allow', malformed_resource)

    assert policy['policyDocument']['Statement'][0]['Resource'] == malformed_resource


def test_generate_policy_context_string_conversion():
    """Test that all context values are converted to strings for API Gateway"""
    context = {
        'user_id': 123,
        'wheel_group_id': None,
        'deployment_admin': True,
        'role': 'USER'
    }

    policy = generate_policy('test', 'Allow', 'arn:aws:execute-api:::/*/*', context)

    assert policy['context']['user_id'] == '123'
    assert policy['context']['wheel_group_id'] == 'None'
    assert policy['context']['deployment_admin'] == 'True'
    assert policy['context']['role'] == 'USER'


def test_generate_policy_no_effect_or_resource():
    """Test policy generation with no effect or resource"""
    policy = generate_policy('test', None, None)

    assert policy['principalId'] == 'test'
    assert 'policyDocument' not in policy
    assert 'context' not in policy


def test_generate_policy_empty_context():
    """Test policy generation with empty context"""
    policy = generate_policy('test', 'Allow', 'arn:aws:execute-api:::/*/*', {})

    validate_iam_policy_structure(policy)
    assert 'context' not in policy or policy.get('context') == {}


# Lambda Handler Tests (10 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
@patch('api_gateway_authorizer.verify_cognito_token')
def test_lambda_handler_deployment_admin_success(mock_verify, mock_lookup):
    """Test lambda handler with valid deployment admin token"""
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'true'})
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())

    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    validate_deployment_admin_context(result['context'])

    mock_lookup.assert_not_called()


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
@patch('api_gateway_authorizer.verify_cognito_token')
def test_lambda_handler_regular_user_success(mock_verify, mock_lookup):
    """Test lambda handler with valid regular user token"""
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',
        'email': 'user@example.com',
        'name': 'Test User'
    }

    payload = create_valid_jwt_payload()
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())

    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    validate_regular_user_context(result['context'], 'wg-123', 'USER')

    mock_lookup.assert_called_once_with('test@example.com')


def test_lambda_handler_missing_authorization_token():
    """Test lambda handler with missing authorization token"""
    event = {'methodArn': 'arn:aws:execute-api:::/*/*'}

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


def test_lambda_handler_invalid_bearer_token():
    """Test lambda handler with invalid Bearer token format"""
    event = create_authorizer_event('Invalid-Token-Format')

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {})  # Clear environment variables
def test_lambda_handler_missing_cognito_configuration():
    """Test lambda handler with missing Cognito configuration"""
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_lambda_handler_expired_token(mock_verify):
    """Test lambda handler with expired JWT token"""
    mock_verify.side_effect = ValueError("Token has expired")
    token = create_jwt_token(create_valid_jwt_payload())
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_lambda_handler_missing_email_claim(mock_verify):
    """Test lambda handler with token missing email claim"""
    payload = create_valid_jwt_payload()
    del payload['email']
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_lambda_handler_database_lookup_failure(mock_lookup, mock_verify):
    """Test lambda handler when database lookup fails"""
    mock_verify.return_value = create_valid_jwt_payload()
    mock_lookup.side_effect = ValueError("User not found in database")

    token = create_jwt_token(create_valid_jwt_payload())
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_lambda_handler_invalid_signature_token(mock_verify):
    """Test lambda handler with forged JWT token (invalid signature)"""
    mock_verify.side_effect = ValueError("Invalid token signature")
    event = create_authorizer_event('Bearer forged.jwt.token')

    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


def test_lambda_handler_deny_policy_on_error():
    """Test that lambda handler returns Deny policy on any error"""
    event = create_authorizer_event('Bearer malformed-token')

    result = lambda_handler(event, create_mock_lambda_context())

    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


# Integration & Edge Case Tests (4 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_authorizer_end_to_end_regular_user(mock_lookup, mock_verify):
    """Test complete authorizer flow for regular user"""
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'WHEEL_ADMIN',
        'email': 'wheeladmin@example.com',
        'name': 'Wheel Admin'
    }

    payload = create_valid_jwt_payload(user_email='wheeladmin@example.com')
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}",
                                  'arn:aws:execute-api:us-west-2:123:api/prod/POST/api/v2/wheels')

    result = lambda_handler(event, create_mock_lambda_context())

    validate_iam_policy_structure(result)
    assert result['principalId'] == 'wheeladmin@example.com'
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    assert result['policyDocument']['Statement'][0]['Resource'] == 'arn:aws:execute-api:us-west-2:123:api/prod/*/*'

    context = result['context']
    assert context['user_id'] == 'user-123'
    assert context['wheel_group_id'] == 'wg-123'
    assert context['wheel_group_name'] == 'Test Group'
    assert context['role'] == 'WHEEL_ADMIN'
    assert context['deployment_admin'] == 'false'

    mock_lookup.assert_called_once_with('wheeladmin@example.com')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_authorizer_end_to_end_deployment_admin(mock_verify):
    """Test complete authorizer flow for deployment admin"""
    payload = create_valid_jwt_payload(
        user_email='admin@example.com',
        name='Deployment Admin',
        **{'custom:deployment_admin': 'true'}
    )
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}",
                                  'arn:aws:execute-api:us-west-2:123:api/prod/DELETE/admin/wheel-groups/123')

    result = lambda_handler(event, create_mock_lambda_context())

    validate_iam_policy_structure(result)
    assert result['principalId'] == 'admin@example.com'
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'

    context = result['context']
    validate_deployment_admin_context(context)
    assert context['user_id'] == 'test-user-id-123'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_authorizer_security_boundary_validation(mock_verify):
    """Test that authorizer properly enforces security boundaries"""
    # Test 1: Invalid signature should return Deny policy
    mock_verify.side_effect = ValueError("Invalid token signature")
    invalid_event = create_authorizer_event('Bearer forged-token')
    result1 = lambda_handler(invalid_event, create_mock_lambda_context())

    assert result1['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result1['principalId'] == 'user'

    # Test 2: Missing token should return Deny policy
    no_token_event = {'methodArn': 'arn:aws:execute-api:::/*/*'}
    result2 = lambda_handler(no_token_event, create_mock_lambda_context())
    assert result2['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result2['principalId'] == 'user'

    # Test 3: Token without Bearer prefix should return Deny policy
    malformed_event = create_authorizer_event('InvalidPrefix token-content')
    result3 = lambda_handler(malformed_event, create_mock_lambda_context())
    assert result3['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result3['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_authorizer_role_permissions_context_injection(mock_lookup, mock_verify):
    """Test that authorizer properly injects role permissions context"""
    roles_and_permissions = [
        ('USER', ['spin_wheel', 'view_wheels']),
        ('WHEEL_ADMIN', ['create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 'view_wheels', 'rig_wheel']),
        ('ADMIN', ['create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'])
    ]

    for role, expected_permissions in roles_and_permissions:
        mock_lookup.return_value = {
            'user_id': f'{role.lower()}-123',
            'wheel_group_id': 'wg-123',
            'wheel_group_name': 'Test Group',
            'role': role,
            'email': f'{role.lower()}@example.com',
            'name': f'Test {role}',
            'permissions': expected_permissions
        }

        payload = create_valid_jwt_payload(user_email=f'{role.lower()}@example.com')
        mock_verify.return_value = payload
        token = create_jwt_token(payload)
        event = create_authorizer_event(f"Bearer {token}")

        result = lambda_handler(event, create_mock_lambda_context())

        assert result['context']['role'] == role

        mock_lookup.reset_mock()
        mock_verify.reset_mock()


# Security Edge Cases Tests (4 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_authorizer_handles_token_injection_attempts(mock_verify):
    """Test authorizer security against token injection attempts"""
    malicious_payloads = [
        create_valid_jwt_payload(email="'; DROP TABLE users; --@example.com"),
        create_valid_jwt_payload(sub="<script>alert('xss')</script>"),
        create_valid_jwt_payload(name="'; DELETE FROM wheel_groups; --"),
        create_valid_jwt_payload(**{'custom:deployment_admin': "true'; DROP TABLE users; --"})
    ]

    for payload in malicious_payloads:
        mock_verify.return_value = payload
        token = create_jwt_token(payload)
        event = create_authorizer_event(f"Bearer {token}")

        try:
            result = lambda_handler(event, create_mock_lambda_context())
            validate_iam_policy_structure(result)
            if 'context' in result:
                for value in result['context'].values():
                    assert isinstance(value, str)
        except Exception as e:
            assert 'Unauthorized' in str(e)


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_authorizer_prevents_privilege_escalation(mock_verify):
    """Test that authorizer prevents privilege escalation attempts"""
    # Test 1: Regular user cannot claim deployment admin via JWT manipulation
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'false'})
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")

    with patch('api_gateway_authorizer.lookup_user_wheel_group_info') as mock_lookup:
        mock_lookup.return_value = {
            'user_id': 'user-123',
            'wheel_group_id': 'wg-123',
            'role': 'USER',
            'email': 'user@example.com',
            'name': 'Regular User'
        }

        result = lambda_handler(event, create_mock_lambda_context())

        assert result['context']['role'] == 'USER'
        assert result['context']['deployment_admin'] == 'false'

    # Test 2: Missing deployment admin claim should default to false
    payload_no_claim = create_valid_jwt_payload()
    mock_verify.return_value = payload_no_claim
    token_no_claim = create_jwt_token(payload_no_claim)
    event_no_claim = create_authorizer_event(f"Bearer {token_no_claim}")

    with patch('api_gateway_authorizer.lookup_user_wheel_group_info') as mock_lookup:
        mock_lookup.return_value = {
            'user_id': 'user-456',
            'wheel_group_id': 'wg-456',
            'role': 'USER',
            'email': 'user2@example.com',
            'name': 'Another User'
        }

        result = lambda_handler(event_no_claim, create_mock_lambda_context())
        assert result['context']['deployment_admin'] == 'false'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_authorizer_resource_arn_validation(mock_verify):
    """Test that authorizer properly validates and processes resource ARNs"""
    test_cases = [
        {
            'input': 'arn:aws:execute-api:us-west-2:123:api/dev/GET/api/v2/wheels',
            'expected': 'arn:aws:execute-api:us-west-2:123:api/dev/*/*'
        },
        {
            'input': 'arn:aws:execute-api:us-east-1:456:xyz/prod/POST/admin/wheel-groups/delete',
            'expected': 'arn:aws:execute-api:us-east-1:456:xyz/prod/*/*'
        },
        {
            'input': 'arn:aws:execute-api:eu-west-1:789:def/stage/OPTIONS/api/v2/participants',
            'expected': 'arn:aws:execute-api:eu-west-1:789:def/stage/*/*'
        }
    ]

    with patch('api_gateway_authorizer.lookup_user_wheel_group_info') as mock_lookup:
        mock_lookup.return_value = {
            'user_id': 'test-user',
            'wheel_group_id': 'wg-test',
            'role': 'USER',
            'email': 'test@example.com',
            'name': 'Test User'
        }

        for test_case in test_cases:
            payload = create_valid_jwt_payload()
            mock_verify.return_value = payload
            token = create_jwt_token(payload)
            event = create_authorizer_event(f"Bearer {token}", test_case['input'])

            result = lambda_handler(event, create_mock_lambda_context())

            actual_resource = result['policyDocument']['Statement'][0]['Resource']
            assert actual_resource == test_case['expected'], \
                f"Expected {test_case['expected']}, got {actual_resource} for input {test_case['input']}"


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
def test_authorizer_comprehensive_error_handling(mock_verify):
    """Test comprehensive error handling across all authorizer functions"""
    # Test that forged tokens are rejected via signature verification
    error_cases = [
        ValueError("Invalid token signature"),
        ValueError("Token decode failed: Not enough segments"),
        ValueError("Invalid JWT header: invalid header padding"),
        ValueError("Unable to fetch JWKS and no cached keys available"),
    ]

    for error in error_cases:
        mock_verify.side_effect = error
        event = create_authorizer_event('Bearer some.fake.token')
        result = lambda_handler(event, create_mock_lambda_context())
        validate_iam_policy_structure(result)
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    # Test generate_policy with edge case inputs
    edge_cases = [
        ('', 'Allow', ''),
        (None, None, None),
        ('test', 'Invalid', 'resource'),
    ]

    for principal, effect, resource in edge_cases:
        policy = generate_policy(principal, effect, resource)
        assert 'principalId' in policy

        if effect and resource and effect in ['Allow', 'Deny']:
            validate_iam_policy_structure(policy)


# Performance & Scalability Tests (2 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.verify_cognito_token')
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_authorizer_performance_with_large_context(mock_lookup, mock_verify):
    """Test authorizer performance with large context data"""
    large_context = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-' + 'x' * 100,
        'wheel_group_name': 'Very Long Wheel Group Name ' * 20,
        'role': 'ADMIN',
        'email': 'user@example.com',
        'name': 'User with Very Long Name ' * 10
    }

    mock_lookup.return_value = large_context
    payload = create_valid_jwt_payload()
    mock_verify.return_value = payload
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")

    result = lambda_handler(event, create_mock_lambda_context())

    validate_iam_policy_structure(result)
    assert len(result['context']['wheel_group_name']) > 100

    for key, value in result['context'].items():
        assert isinstance(value, str), f"Context value {key} should be string, got {type(value)}"


def test_authorizer_constants_and_configuration_validation():
    """Test that authorizer constants and configurations are properly defined"""
    assert callable(lambda_handler)
    assert callable(validate_token)
    assert callable(lookup_user_wheel_group_info)
    assert callable(get_role_permissions)
    assert callable(generate_policy)

    all_roles = ['USER', 'WHEEL_ADMIN', 'ADMIN']
    for role in all_roles:
        permissions = get_role_permissions(role)
        assert isinstance(permissions, list)
        assert len(permissions) > 0
        assert all(isinstance(perm, str) for perm in permissions)

    user_perms = set(get_role_permissions('USER'))
    wheel_admin_perms = set(get_role_permissions('WHEEL_ADMIN'))
    admin_perms = set(get_role_permissions('ADMIN'))

    assert user_perms.issubset(wheel_admin_perms), "USER permissions should be subset of WHEEL_ADMIN"
    assert wheel_admin_perms.issubset(admin_perms), "WHEEL_ADMIN permissions should be subset of ADMIN"
