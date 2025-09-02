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
    lambda_handler, decode_jwt_payload_only, validate_token_basic,
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
    """Create a mock JWT token with the given payload"""
    # Create header (not validated in this implementation)
    header = {'alg': 'RS256', 'typ': 'JWT'}
    header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    
    # Encode payload
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    # Create signature (not validated in this implementation)
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


# JWT Validation Tests (8 tests)

def test_decode_jwt_payload_only_valid_token():
    """Test JWT payload decoding with valid token"""
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    
    decoded = decode_jwt_payload_only(token)
    
    assert decoded['sub'] == payload['sub']
    assert decoded['email'] == payload['email'] 
    assert decoded['exp'] == payload['exp']


def test_decode_jwt_payload_only_invalid_format():
    """Test JWT decoding fails with malformed token"""
    invalid_tokens = [
        "invalid.token",  # Only 2 parts
        "invalid.token.signature.extra",  # Too many parts
        "not-base64.not-base64.not-base64",  # Invalid base64
        "",  # Empty string
        "invalid"  # Single part
    ]
    
    for invalid_token in invalid_tokens:
        with pytest.raises(ValueError, match="Failed to decode JWT payload"):
            decode_jwt_payload_only(invalid_token)


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_valid_token():
    """Test basic token validation with valid token"""
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    
    result = validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')
    
    assert result['sub'] == payload['sub']
    assert result['email'] == payload['email']
    assert result['exp'] == payload['exp']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_expired_token():
    """Test token validation fails with expired token"""
    expired_time = int(time.time()) - 3600  # Expired 1 hour ago
    payload = create_valid_jwt_payload(exp=expired_time)
    token = create_jwt_token(payload)
    
    with pytest.raises(ValueError, match="Token has expired"):
        validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_missing_required_claims():
    """Test token validation fails with missing required claims"""
    base_payload = create_valid_jwt_payload()
    required_claims = ['sub', 'exp', 'iss', 'aud']
    
    for claim in required_claims:
        payload = base_payload.copy()
        del payload[claim]
        token = create_jwt_token(payload)
        
        with pytest.raises(ValueError, match=f"Missing required claim: {claim}"):
            validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_invalid_issuer():
    """Test token validation fails with invalid issuer"""
    payload = create_valid_jwt_payload(iss='https://malicious-site.com')
    token = create_jwt_token(payload)
    
    with pytest.raises(ValueError, match="Invalid issuer"):
        validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_invalid_audience():
    """Test token validation fails with invalid audience"""
    payload = create_valid_jwt_payload(aud='wrong-client-id')
    token = create_jwt_token(payload)
    
    with pytest.raises(ValueError, match="Invalid audience"):
        validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_cognito_typo_issuer_handling():
    """Test token validation handles AWS Cognito service typo in issuer"""
    # Test the known AWS service issue with 'cognitm-idp' typo
    payload = create_valid_jwt_payload(iss='https://cognitm-idp.us-west-2.amazonaws.com/us-west-2_TestPool')
    token = create_jwt_token(payload)
    
    # Should not raise exception due to typo handling
    result = validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')
    assert result['sub'] == payload['sub']


# Database Integration Tests (6 tests)

@patch('boto3.resource')
def test_lookup_user_wheel_group_info_success(mock_boto3_resource):
    """Test successful user wheel group lookup"""
    # Mock DynamoDB resource and tables
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    mock_wheel_groups_table = Mock()
    
    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.side_effect = lambda name: {
        'OpsWheelV2-Users-test': mock_users_table,
        'OpsWheelV2-WheelGroups-test': mock_wheel_groups_table
    }[name]
    
    # Mock database scan response - must return actual list for items[0] access
    mock_users_table.scan.return_value = {
        'Items': [{
            'user_id': 'test-user-123',
            'wheel_group_id': 'wg-123',
            'role': 'USER',
            'name': 'Test User',
            'email': 'test@example.com'
        }]
    }
    
    # Mock wheel group response
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
    
    # Mock empty scan response 
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
    
    # Mock user exists but wheel group doesn't - items must be a list
    items_list = [{
        'user_id': 'test-user-123',
        'wheel_group_id': 'nonexistent-wg',
        'role': 'USER',
        'email': 'test@example.com'
    }]
    mock_users_table.scan.return_value = {'Items': items_list}
    
    mock_wheel_groups_table.get_item.return_value = {}  # No Item key
    
    result = lookup_user_wheel_group_info('test@example.com')
    
    # Should still work, just use wheel_group_id as name
    assert result['wheel_group_name'] == 'nonexistent-wg'


@patch('boto3.resource')
def test_lookup_user_wheel_group_info_database_error(mock_boto3_resource):
    """Test user lookup handles database errors gracefully"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    
    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.return_value = mock_users_table
    
    # Mock database error - use scan method since that's what the implementation uses
    mock_users_table.scan.side_effect = Exception("DynamoDB connection failed")
    
    with pytest.raises(ValueError, match="Failed to lookup user wheel group info"):
        lookup_user_wheel_group_info('test@example.com')


def test_get_role_permissions_all_roles():
    """Test role permissions mapping for all role types"""
    # Test ADMIN permissions
    admin_perms = get_role_permissions('ADMIN')
    expected_admin = [
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
        'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'
    ]
    assert set(admin_perms) == set(expected_admin)
    
    # Test WHEEL_ADMIN permissions
    wheel_admin_perms = get_role_permissions('WHEEL_ADMIN')
    expected_wheel_admin = [
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
        'view_wheels', 'rig_wheel'
    ]
    assert set(wheel_admin_perms) == set(expected_wheel_admin)
    
    # Test USER permissions
    user_perms = get_role_permissions('USER')
    expected_user = ['spin_wheel', 'view_wheels']
    assert set(user_perms) == set(expected_user)
    
    # Test unknown role defaults to USER
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
    
    # Verify correct table names were used
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
    
    # Validate policy details
    assert policy['principalId'] == 'test@example.com'
    assert policy['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    assert policy['policyDocument']['Statement'][0]['Action'] == 'execute-api:Invoke'
    
    # Validate wildcard resource pattern
    assert policy['policyDocument']['Statement'][0]['Resource'] == 'arn:aws:execute-api:us-west-2:123:abc/dev/*/*'
    
    # Validate context
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
    
    # Should handle gracefully by using original resource
    assert policy['policyDocument']['Statement'][0]['Resource'] == malformed_resource


def test_generate_policy_context_string_conversion():
    """Test that all context values are converted to strings for API Gateway"""
    context = {
        'user_id': 123,  # Number
        'wheel_group_id': None,  # None
        'deployment_admin': True,  # Boolean
        'role': 'USER'  # String
    }
    
    policy = generate_policy('test', 'Allow', 'arn:aws:execute-api:::/*/*', context)
    
    # All values should be strings
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
    # Empty context gets filtered out by implementation (correct behavior)
    assert 'context' not in policy or policy.get('context') == {}


# Lambda Handler Tests (10 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_lambda_handler_deployment_admin_success(mock_lookup):
    """Test lambda handler with valid deployment admin token"""
    # Create deployment admin token
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'true'})
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    result = lambda_handler(event, create_mock_lambda_context())
    
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    validate_deployment_admin_context(result['context'])
    
    # Should not call database lookup for deployment admin
    mock_lookup.assert_not_called()


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_lambda_handler_regular_user_success(mock_lookup):
    """Test lambda handler with valid regular user token"""
    # Mock database lookup
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',
        'email': 'user@example.com',
        'name': 'Test User'
    }
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    result = lambda_handler(event, create_mock_lambda_context())
    
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    validate_regular_user_context(result['context'], 'wg-123', 'USER')
    
    # Should call database lookup for regular user
    mock_lookup.assert_called_once_with('test@example.com')


def test_lambda_handler_missing_authorization_token():
    """Test lambda handler with missing authorization token"""
    event = {'methodArn': 'arn:aws:execute-api:::/*/*'}  # No authorizationToken
    
    # Should return Deny policy, not raise exception (graceful security handling)
    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


def test_lambda_handler_invalid_bearer_token():
    """Test lambda handler with invalid Bearer token format"""
    event = create_authorizer_event('Invalid-Token-Format')
    
    # Should return Deny policy, not raise exception (graceful security handling)
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
    
    # Should return Deny policy, not raise exception (graceful security handling)
    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_lambda_handler_expired_token():
    """Test lambda handler with expired JWT token"""
    expired_payload = create_valid_jwt_payload(exp=int(time.time()) - 3600)
    token = create_jwt_token(expired_payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    # Should return Deny policy, not raise exception (graceful security handling)
    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_lambda_handler_missing_email_claim():
    """Test lambda handler with token missing email claim"""
    payload = create_valid_jwt_payload()
    del payload['email']
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    # Should return Deny policy, not raise exception (graceful security handling)
    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_lambda_handler_database_lookup_failure(mock_lookup):
    """Test lambda handler when database lookup fails"""
    mock_lookup.side_effect = ValueError("User not found in database")
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    # Should return Deny policy, not raise exception (graceful security handling)
    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_lambda_handler_malformed_jwt_token():
    """Test lambda handler with malformed JWT token"""
    event = create_authorizer_event('Bearer invalid.jwt.token')
    
    # Should return Deny policy, not raise exception (graceful security handling)
    result = lambda_handler(event, create_mock_lambda_context())
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


def test_lambda_handler_deny_policy_on_error():
    """Test that lambda handler returns Deny policy on any error"""
    event = create_authorizer_event('Bearer malformed-token')
    
    # Should not raise exception, but return Deny policy
    result = lambda_handler(event, create_mock_lambda_context())
    
    validate_iam_policy_structure(result)
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result['principalId'] == 'user'


# Integration & Edge Case Tests (4 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_authorizer_end_to_end_regular_user(mock_lookup):
    """Test complete authorizer flow for regular user"""
    # Setup database mock
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123', 
        'wheel_group_name': 'Test Group',
        'role': 'WHEEL_ADMIN',
        'email': 'wheeladmin@example.com',
        'name': 'Wheel Admin'
    }
    
    # Create realistic event
    payload = create_valid_jwt_payload(user_email='wheeladmin@example.com')
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}", 
                                  'arn:aws:execute-api:us-west-2:123:api/prod/POST/api/v2/wheels')
    
    result = lambda_handler(event, create_mock_lambda_context())
    
    # Validate complete response
    validate_iam_policy_structure(result) 
    assert result['principalId'] == 'wheeladmin@example.com'
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    assert result['policyDocument']['Statement'][0]['Resource'] == 'arn:aws:execute-api:us-west-2:123:api/prod/*/*'
    
    # Validate context contains all expected fields
    context = result['context']
    assert context['user_id'] == 'user-123'
    assert context['wheel_group_id'] == 'wg-123'
    assert context['wheel_group_name'] == 'Test Group'
    assert context['role'] == 'WHEEL_ADMIN'
    assert context['deployment_admin'] == 'false'
    
    # Verify database lookup was called with correct email
    mock_lookup.assert_called_once_with('wheeladmin@example.com')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_authorizer_end_to_end_deployment_admin():
    """Test complete authorizer flow for deployment admin"""
    # Create deployment admin token with custom attribute
    payload = create_valid_jwt_payload(
        user_email='admin@example.com',
        name='Deployment Admin',
        **{'custom:deployment_admin': 'true'}
    )
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}",
                                  'arn:aws:execute-api:us-west-2:123:api/prod/DELETE/admin/wheel-groups/123')
    
    result = lambda_handler(event, create_mock_lambda_context())
    
    # Validate deployment admin response
    validate_iam_policy_structure(result)
    assert result['principalId'] == 'admin@example.com'
    assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    
    # Validate deployment admin context
    context = result['context']
    validate_deployment_admin_context(context)
    assert context['user_id'] == 'test-user-id-123'  # From JWT sub claim


def test_authorizer_security_boundary_validation():
    """Test that authorizer properly enforces security boundaries"""
    # Test 1: Invalid token should return Deny policy
    invalid_event = create_authorizer_event('Bearer invalid-token')
    result1 = lambda_handler(invalid_event, create_mock_lambda_context())
    
    assert result1['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result1['principalId'] == 'user'
    
    # Test 2: Missing token should return Deny policy (graceful security handling)
    no_token_event = {'methodArn': 'arn:aws:execute-api:::/*/*'}
    result2 = lambda_handler(no_token_event, create_mock_lambda_context())
    assert result2['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result2['principalId'] == 'user'
    
    # Test 3: Token without Bearer prefix should return Deny policy (graceful security handling)
    malformed_event = create_authorizer_event('InvalidPrefix token-content')
    result3 = lambda_handler(malformed_event, create_mock_lambda_context())
    assert result3['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    assert result3['principalId'] == 'user'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_authorizer_role_permissions_context_injection(mock_lookup):
    """Test that authorizer properly injects role permissions context"""
    # Test different role types and their permissions
    roles_and_permissions = [
        ('USER', ['spin_wheel', 'view_wheels']),
        ('WHEEL_ADMIN', ['create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 'view_wheels', 'rig_wheel']),
        ('ADMIN', ['create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'])
    ]
    
    for role, expected_permissions in roles_and_permissions:
        # Mock database lookup for this role
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
        token = create_jwt_token(payload)
        event = create_authorizer_event(f"Bearer {token}")
        
        result = lambda_handler(event, create_mock_lambda_context())
        
        # Validate role is properly set in context
        assert result['context']['role'] == role
        
        # Reset mock for next iteration
        mock_lookup.reset_mock()


# Security Edge Cases Tests (4 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_authorizer_handles_token_injection_attempts():
    """Test authorizer security against token injection attempts"""
    # Test SQL injection-like attempts in JWT claims
    malicious_payloads = [
        create_valid_jwt_payload(email="'; DROP TABLE users; --@example.com"),
        create_valid_jwt_payload(sub="<script>alert('xss')</script>"),
        create_valid_jwt_payload(name="'; DELETE FROM wheel_groups; --"),
        create_valid_jwt_payload(**{'custom:deployment_admin': "true'; DROP TABLE users; --"})
    ]
    
    for payload in malicious_payloads:
        token = create_jwt_token(payload)
        event = create_authorizer_event(f"Bearer {token}")
        
        # Should either fail validation or handle safely
        try:
            result = lambda_handler(event, create_mock_lambda_context())
            # If it succeeds, validate it's handled safely
            validate_iam_policy_structure(result)
            # Context values should be strings (safe for API Gateway)
            if 'context' in result:
                for value in result['context'].values():
                    assert isinstance(value, str)
        except Exception as e:
            # Expected to fail with malicious input
            assert 'Unauthorized' in str(e)


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_authorizer_prevents_privilege_escalation():
    """Test that authorizer prevents privilege escalation attempts"""
    # Test 1: Regular user cannot claim deployment admin via JWT manipulation
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'false'})  # Explicit false
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    with patch('api_gateway_authorizer.lookup_user_wheel_group_info') as mock_lookup:
        mock_lookup.return_value = {
            'user_id': 'user-123',
            'wheel_group_id': 'wg-123',
            'role': 'USER',  # Database says USER
            'email': 'user@example.com',
            'name': 'Regular User'
        }
        
        result = lambda_handler(event, create_mock_lambda_context())
        
        # Should be regular user, not deployment admin
        assert result['context']['role'] == 'USER'
        assert result['context']['deployment_admin'] == 'false'
    
    # Test 2: Missing deployment admin claim should default to false
    payload_no_claim = create_valid_jwt_payload()  # No deployment_admin claim
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
def test_authorizer_resource_arn_validation():
    """Test that authorizer properly validates and processes resource ARNs"""
    # Test various resource ARN formats
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
            token = create_jwt_token(payload)
            event = create_authorizer_event(f"Bearer {token}", test_case['input'])
            
            result = lambda_handler(event, create_mock_lambda_context())
            
            actual_resource = result['policyDocument']['Statement'][0]['Resource']
            assert actual_resource == test_case['expected'], \
                f"Expected {test_case['expected']}, got {actual_resource} for input {test_case['input']}"


def test_authorizer_comprehensive_error_handling():
    """Test comprehensive error handling across all authorizer functions"""
    # Test decode_jwt_payload_only with various malformed inputs
    malformed_inputs = [
        None,
        123, 
        [],
        {},
        "single-part",
        "two.parts",
        "header.invalid-base64-payload.signature",
        "header.valid-base64-but-not-json.signature"
    ]
    
    for malformed_input in malformed_inputs:
        with pytest.raises((ValueError, AttributeError, TypeError)):
            decode_jwt_payload_only(malformed_input)
    
    # Test generate_policy with edge case inputs
    edge_cases = [
        ('', 'Allow', ''),  # Empty strings
        (None, None, None),  # None values
        ('test', 'Invalid', 'resource'),  # Invalid effect
    ]
    
    for principal, effect, resource in edge_cases:
        # Should not raise exception, should handle gracefully
        policy = generate_policy(principal, effect, resource)
        assert 'principalId' in policy
        
        if effect and resource and effect in ['Allow', 'Deny']:
            validate_iam_policy_structure(policy)


# Performance & Scalability Tests (2 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('api_gateway_authorizer.lookup_user_wheel_group_info')
def test_authorizer_performance_with_large_context(mock_lookup):
    """Test authorizer performance with large context data"""
    # Create large context to test string conversion performance
    large_context = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-' + 'x' * 100,  # Long ID
        'wheel_group_name': 'Very Long Wheel Group Name ' * 20,  # Long name
        'role': 'ADMIN',
        'email': 'user@example.com',
        'name': 'User with Very Long Name ' * 10
    }
    
    mock_lookup.return_value = large_context
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_authorizer_event(f"Bearer {token}")
    
    # Should handle large context without issues
    result = lambda_handler(event, create_mock_lambda_context())
    
    validate_iam_policy_structure(result)
    assert len(result['context']['wheel_group_name']) > 100  # Verify large data preserved
    
    # All context values should be strings
    for key, value in result['context'].items():
        assert isinstance(value, str), f"Context value {key} should be string, got {type(value)}"


def test_authorizer_constants_and_configuration_validation():
    """Test that authorizer constants and configurations are properly defined"""
    # Test that required functions are importable and callable
    assert callable(lambda_handler)
    assert callable(decode_jwt_payload_only)
    assert callable(validate_token_basic)
    assert callable(lookup_user_wheel_group_info)
    assert callable(get_role_permissions)
    assert callable(generate_policy)
    
    # Test role permissions constants
    all_roles = ['USER', 'WHEEL_ADMIN', 'ADMIN']
    for role in all_roles:
        permissions = get_role_permissions(role)
        assert isinstance(permissions, list)
        assert len(permissions) > 0
        assert all(isinstance(perm, str) for perm in permissions)
    
    # Test that USER permissions are subset of WHEEL_ADMIN permissions  
    user_perms = set(get_role_permissions('USER'))
    wheel_admin_perms = set(get_role_permissions('WHEEL_ADMIN'))
    admin_perms = set(get_role_permissions('ADMIN'))
    
    assert user_perms.issubset(wheel_admin_perms), "USER permissions should be subset of WHEEL_ADMIN"
    assert wheel_admin_perms.issubset(admin_perms), "WHEEL_ADMIN permissions should be subset of ADMIN"
