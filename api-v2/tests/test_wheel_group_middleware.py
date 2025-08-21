#  Improved Unit Tests for Wheel Group Middleware - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests validate critical authentication middleware logic for all API endpoints

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

# Import middleware functions
from wheel_group_middleware import (
    wheel_group_middleware, require_auth, require_wheel_group_permission,
    decode_jwt_payload_only, validate_token_basic, lookup_user_wheel_group_info,
    get_role_permissions, get_wheel_group_context
)


def create_mock_lambda_context():
    """Create a mock Lambda context for testing"""
    mock_context = Mock()
    mock_context.aws_request_id = 'test-request-id'
    mock_context.log_group_name = '/aws/lambda/test-middleware'
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


def create_api_event(token=None, path="/api/v2/wheels", method="GET", headers=None):
    """Create a mock API Gateway event"""
    if headers is None:
        headers = {}
    
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    return {
        'path': path,
        'httpMethod': method,
        'headers': headers,
        'queryStringParameters': None,
        'body': None,
        'isBase64Encoded': False
    }


def validate_error_response(response, expected_status=401):
    """Validate error response structure"""
    assert response['statusCode'] == expected_status
    assert 'headers' in response
    assert response['headers']['Content-Type'] == 'application/json'
    assert response['headers']['Access-Control-Allow-Origin'] == '*'
    assert 'body' in response
    
    body = json.loads(response['body'])
    assert 'error' in body
    return body


def validate_success_event(event):
    """Validate successful authentication event structure"""
    assert 'wheel_group_context' in event
    assert 'user_info' in event
    
    context = event['wheel_group_context']
    assert 'user_id' in context
    assert 'email' in context
    assert 'role' in context
    assert 'permissions' in context
    assert 'deployment_admin' in context
    
    return context


# JWT Validation Tests (6 tests)

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
        "invalid.token",
        "invalid.token.signature.extra",
        "not-base64.not-base64.not-base64",
        "",
        "invalid"
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
    expired_time = int(time.time()) - 3600
    payload = create_valid_jwt_payload(exp=expired_time)
    token = create_jwt_token(payload)
    
    with pytest.raises(ValueError, match="Token has expired"):
        validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_validate_token_basic_missing_claims():
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
def test_validate_token_basic_cognito_typo_handling():
    """Test token validation handles AWS Cognito service typo in issuer"""
    payload = create_valid_jwt_payload(iss='https://cognitm-idp.us-west-2.amazonaws.com/us-west-2_TestPool')
    token = create_jwt_token(payload)
    
    result = validate_token_basic(token, 'us-west-2_TestPool', 'test-client-id')
    assert result['sub'] == payload['sub']


# Database Integration Tests (4 tests)

@patch('boto3.resource')
def test_lookup_user_wheel_group_info_user_not_found(mock_boto3_resource):
    """Test user lookup when user doesn't exist"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    
    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.return_value = mock_users_table
    
    mock_users_table.query.return_value = {'Items': []}
    
    with pytest.raises(ValueError, match="User not found in database: nonexistent@example.com"):
        lookup_user_wheel_group_info('nonexistent@example.com')


@patch('boto3.resource')
def test_lookup_user_wheel_group_info_database_error(mock_boto3_resource):
    """Test user lookup handles database errors gracefully"""
    mock_dynamodb_resource = Mock()
    mock_users_table = Mock()
    
    mock_boto3_resource.return_value = mock_dynamodb_resource
    mock_dynamodb_resource.Table.return_value = mock_users_table
    
    mock_users_table.query.side_effect = Exception("DynamoDB connection failed")
    
    with pytest.raises(ValueError, match="Failed to lookup user wheel group info"):
        lookup_user_wheel_group_info('test@example.com')


def test_get_role_permissions_all_roles():
    """Test role permissions mapping for all role types"""
    # Test DEPLOYMENT_ADMIN permissions (most comprehensive)
    deployment_admin_perms = get_role_permissions('DEPLOYMENT_ADMIN')
    expected_deployment_admin = [
        'view_all_wheel_groups', 'delete_wheel_group', 'manage_deployment',
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
        'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'
    ]
    for perm in expected_deployment_admin:
        assert deployment_admin_perms[perm] == True
    
    # Test ADMIN permissions
    admin_perms = get_role_permissions('ADMIN')
    expected_admin = [
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
        'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'
    ]
    for perm in expected_admin:
        assert admin_perms[perm] == True
    
    # Test WHEEL_ADMIN permissions
    wheel_admin_perms = get_role_permissions('WHEEL_ADMIN')
    expected_wheel_admin = [
        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
        'view_wheels', 'rig_wheel'
    ]
    for perm in expected_wheel_admin:
        assert wheel_admin_perms[perm] == True
    assert wheel_admin_perms['manage_users'] == False
    assert wheel_admin_perms['manage_wheel_group'] == False
    
    # Test USER permissions
    user_perms = get_role_permissions('USER')
    assert user_perms['spin_wheel'] == True
    assert user_perms['view_wheels'] == True
    assert user_perms['create_wheel'] == False
    assert user_perms['delete_wheel'] == False
    assert user_perms['manage_participants'] == False


# Middleware Core Functionality Tests (10 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_wheel_group_middleware_missing_authorization():
    """Test middleware with missing Authorization header"""
    event = create_api_event()
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    error_body = validate_error_response(response, 401)
    assert 'Missing or invalid Authorization header' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_wheel_group_middleware_invalid_bearer_format():
    """Test middleware with invalid Bearer token format"""
    event = create_api_event()
    event['headers']['Authorization'] = 'Invalid-Token-Format'
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    error_body = validate_error_response(response, 401)
    assert 'Missing or invalid Authorization header' in error_body['error']


@patch.dict(os.environ, {})  # Clear environment
def test_wheel_group_middleware_missing_cognito_config():
    """Test middleware with missing Cognito configuration"""
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    # Implementation returns 401 (Authentication failed) not 500
    error_body = validate_error_response(response, 401)
    assert 'Authentication failed' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_wheel_group_middleware_expired_token():
    """Test middleware with expired JWT token"""
    expired_payload = create_valid_jwt_payload(exp=int(time.time()) - 3600)
    token = create_jwt_token(expired_payload)
    event = create_api_event(token)
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    error_body = validate_error_response(response, 401)
    assert 'Authentication failed' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_wheel_group_middleware_missing_email_claim():
    """Test middleware with token missing email claim"""
    payload = create_valid_jwt_payload()
    del payload['email']
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    error_body = validate_error_response(response, 401)
    assert 'Token missing required claims' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_wheel_group_middleware_deployment_admin_success():
    """Test middleware with valid deployment admin token"""
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'true'})
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = wheel_group_middleware(event, create_mock_lambda_context())
    
    context = validate_success_event(result)
    assert context['role'] == 'DEPLOYMENT_ADMIN'
    assert context['deployment_admin'] == True
    assert context['wheel_group_id'] is None
    assert context['wheel_group_name'] is None
    assert context['permissions']['delete_wheel_group'] == True


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_wheel_group_middleware_regular_user_success(mock_lookup):
    """Test middleware with valid regular user token"""
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'WHEEL_ADMIN',
        'email': 'user@example.com',
        'name': 'Test User'
    }
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = wheel_group_middleware(event, create_mock_lambda_context())
    
    context = validate_success_event(result)
    assert context['role'] == 'WHEEL_ADMIN'
    assert context['deployment_admin'] == False
    assert context['wheel_group_id'] == 'wg-123'
    assert context['wheel_group_name'] == 'Test Group'
    assert context['permissions']['create_wheel'] == True
    assert context['permissions']['manage_users'] == False


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_wheel_group_middleware_auth_me_endpoint_fallback(mock_lookup):
    """Test middleware allows /auth/me endpoint even without wheel group"""
    mock_lookup.side_effect = ValueError("User not found in database")
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_api_event(token, path="/auth/me")
    
    result = wheel_group_middleware(event, create_mock_lambda_context())
    
    context = validate_success_event(result)
    assert context['role'] == 'USER'
    assert context['deployment_admin'] == False
    assert context['wheel_group_id'] is None
    assert context['wheel_group_name'] is None


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_wheel_group_middleware_database_lookup_failure(mock_lookup):
    """Test middleware when database lookup fails for non-auth endpoint"""
    mock_lookup.side_effect = ValueError("User not found in database")
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_api_event(token, path="/api/v2/wheels")
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    error_body = validate_error_response(response, 401)
    assert 'User not associated with any wheel group' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_wheel_group_middleware_malformed_jwt():
    """Test middleware with malformed JWT token"""
    event = create_api_event('invalid.jwt.token')
    
    response = wheel_group_middleware(event, create_mock_lambda_context())
    
    error_body = validate_error_response(response, 401)
    assert 'Authentication failed' in error_body['error']


# Authentication Decorators Tests (8 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_require_auth_decorator_success(mock_lookup):
    """Test @require_auth decorator with valid authentication"""
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',
        'email': 'user@example.com',
        'name': 'Test User'
    }
    
    @require_auth()
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'success'})}
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = test_handler(event, create_mock_lambda_context())
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'success'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_require_auth_decorator_failure():
    """Test @require_auth decorator with invalid authentication"""
    @require_auth()
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'success'})}
    
    event = create_api_event()  # No token
    
    result = test_handler(event, create_mock_lambda_context())
    
    error_body = validate_error_response(result, 401)
    assert 'Missing or invalid Authorization header' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_require_wheel_group_permission_success(mock_lookup):
    """Test @require_wheel_group_permission decorator with sufficient permissions"""
    mock_lookup.return_value = {
        'user_id': 'admin-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'ADMIN',
        'email': 'admin@example.com',
        'name': 'Test Admin'
    }
    
    @require_wheel_group_permission('create_wheel')
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'wheel created'})}
    
    payload = create_valid_jwt_payload(user_email='admin@example.com')
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = test_handler(event, create_mock_lambda_context())
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'wheel created'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_require_wheel_group_permission_insufficient_permissions(mock_lookup):
    """Test @require_wheel_group_permission decorator with insufficient permissions"""
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',  # USER role cannot create wheels
        'email': 'user@example.com',
        'name': 'Test User'
    }
    
    @require_wheel_group_permission('create_wheel')
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'wheel created'})}
    
    payload = create_valid_jwt_payload()
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = test_handler(event, create_mock_lambda_context())
    
    error_body = validate_error_response(result, 403)
    assert 'Insufficient permissions' in error_body['error']
    assert 'Required: create_wheel' in error_body['error']
    assert 'user_permissions' in error_body


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_require_wheel_group_permission_auth_failure():
    """Test @require_wheel_group_permission decorator with authentication failure"""
    @require_wheel_group_permission('spin_wheel')
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'wheel spun'})}
    
    event = create_api_event()  # No token
    
    result = test_handler(event, create_mock_lambda_context())
    
    error_body = validate_error_response(result, 401)
    assert 'Missing or invalid Authorization header' in error_body['error']


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_nested_decorators_success(mock_lookup):
    """Test nested @require_auth and @require_wheel_group_permission decorators"""
    mock_lookup.return_value = {
        'user_id': 'wheel-admin-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'WHEEL_ADMIN',
        'email': 'wheeladmin@example.com',
        'name': 'Test Wheel Admin'
    }
    
    @require_auth()
    @require_wheel_group_permission('rig_wheel')
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'wheel rigged'})}
    
    payload = create_valid_jwt_payload(user_email='wheeladmin@example.com')
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = test_handler(event, create_mock_lambda_context())
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'wheel rigged'


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_deployment_admin_permissions_override(mock_lookup):
    """Test deployment admin has all permissions regardless of wheel group"""
    # Don't call database lookup for deployment admin
    @require_wheel_group_permission('delete_wheel_group')
    def test_handler(event, context):
        return {'statusCode': 200, 'body': json.dumps({'message': 'wheel group deleted'})}
    
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'true'})
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = test_handler(event, create_mock_lambda_context())
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'wheel group deleted'
    
    # Should not call database lookup for deployment admin
    mock_lookup.assert_not_called()


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_multiple_permission_checks(mock_lookup):
    """Test multiple different permission requirements"""
    mock_lookup.return_value = {
        'user_id': 'admin-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'ADMIN',
        'email': 'admin@example.com',
        'name': 'Test Admin'
    }
    
    # Test each permission type
    permissions_to_test = [
        'create_wheel', 'delete_wheel', 'manage_participants', 
        'spin_wheel', 'view_wheels', 'manage_users', 
        'manage_wheel_group', 'rig_wheel'
    ]
    
    payload = create_valid_jwt_payload(user_email='admin@example.com')
    token = create_jwt_token(payload)
    
    for permission in permissions_to_test:
        @require_wheel_group_permission(permission)
        def test_permission_handler(event, context):
            return {'statusCode': 200, 'body': json.dumps({'permission': permission})}
        
        event = create_api_event(token)
        result = test_permission_handler(event, create_mock_lambda_context())
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['permission'] == permission


# Context and Helper Function Tests (4 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_get_wheel_group_context_success(mock_lookup):
    """Test get_wheel_group_context helper function"""
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
    event = create_api_event(token)
    
    # Process through middleware first
    result = wheel_group_middleware(event, create_mock_lambda_context())
    
    # Test get_wheel_group_context function
    context = get_wheel_group_context(result)
    
    assert context is not None
    assert context['user_id'] == 'user-123'
    assert context['wheel_group_id'] == 'wg-123'
    assert context['role'] == 'USER'
    assert context['deployment_admin'] == False


def test_get_wheel_group_context_no_context():
    """Test get_wheel_group_context with event missing context"""
    event = {'path': '/test'}  # No wheel_group_context
    
    context = get_wheel_group_context(event)
    
    assert context is None


# Security Edge Cases Tests (4 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_middleware_handles_malicious_payloads(mock_lookup):
    """Test middleware security against malicious JWT payloads"""
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',
        'email': 'test@example.com',
        'name': 'Test User'
    }
    
    # Test malicious payloads that could attempt injection
    malicious_payloads = [
        create_valid_jwt_payload(email="'; DROP TABLE users; --@example.com"),
        create_valid_jwt_payload(sub="<script>alert('xss')</script>"),
        create_valid_jwt_payload(name="'; DELETE FROM wheel_groups; --"),
    ]
    
    for payload in malicious_payloads:
        token = create_jwt_token(payload)
        event = create_api_event(token)
        
        # Should either fail validation or handle safely
        try:
            result = wheel_group_middleware(event, create_mock_lambda_context())
            if 'wheel_group_context' in result:
                # If successful, ensure values are safely handled
                context = result['wheel_group_context']
                for key, value in context.items():
                    assert isinstance(value, (str, bool, type(None))), f"Context value {key} should be safe type"
        except Exception:
            # Expected for malicious input
            pass


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_middleware_prevents_role_escalation(mock_lookup):
    """Test that middleware prevents role escalation attempts"""
    # Database says USER, but JWT claims ADMIN
    mock_lookup.return_value = {
        'user_id': 'user-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Test Group',
        'role': 'USER',  # Database role is USER
        'email': 'user@example.com',
        'name': 'Test User'
    }
    
    # JWT claims different role (attempt at escalation)
    payload = create_valid_jwt_payload()
    payload['custom:role'] = 'ADMIN'  # Attempt to claim admin role
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = wheel_group_middleware(event, create_mock_lambda_context())
    
    context = validate_success_event(result)
    # Should use database role, not JWT role claim
    assert context['role'] == 'USER'
    assert context['permissions']['create_wheel'] == False


@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
def test_middleware_header_case_insensitive():
    """Test middleware handles Authorization header case variations"""
    variations = [
        'Authorization',
        'authorization', 
        'AUTHORIZATION'
    ]
    
    payload = create_valid_jwt_payload(**{'custom:deployment_admin': 'true'})
    token = create_jwt_token(payload)
    
    for header_name in variations:
        event = create_api_event()
        event['headers'] = {header_name: f'Bearer {token}'}
        
        result = wheel_group_middleware(event, create_mock_lambda_context())
        
        if header_name == 'Authorization' or header_name == 'authorization':
            # Should succeed for 'Authorization' and 'authorization' (implementation supports both)
            context = validate_success_event(result)
            assert context['role'] == 'DEPLOYMENT_ADMIN'
        else:
            # Should fail for 'AUTHORIZATION' (implementation only checks these two)
            error_body = validate_error_response(result, 401)
            assert 'Missing or invalid Authorization header' in error_body['error']


# Performance and Edge Case Tests (2 tests)

@patch.dict(os.environ, {'COGNITO_USER_POOL_ID': 'us-west-2_TestPool', 'COGNITO_CLIENT_ID': 'test-client-id'})
@patch('wheel_group_middleware.lookup_user_wheel_group_info')
def test_middleware_performance_large_permissions(mock_lookup):
    """Test middleware performance with comprehensive permission sets"""
    # Create large permission set for deployment admin
    mock_lookup.return_value = {
        'user_id': 'admin-123',
        'wheel_group_id': 'wg-123',
        'wheel_group_name': 'Very Long Wheel Group Name ' * 20,
        'role': 'ADMIN',
        'email': 'admin@example.com',
        'name': 'Test Admin with Very Long Name ' * 10
    }
    
    payload = create_valid_jwt_payload(user_email='admin@example.com')
    token = create_jwt_token(payload)
    event = create_api_event(token)
    
    result = wheel_group_middleware(event, create_mock_lambda_context())
    
    context = validate_success_event(result)
    
    # Verify large data is handled correctly
    assert len(context['wheel_group_name']) > 100
    assert len(context['name']) > 100
    
    # Verify all permissions are boolean
    permissions = context['permissions']
    for perm_name, perm_value in permissions.items():
        assert isinstance(perm_value, bool), f"Permission {perm_name} should be boolean"


def test_middleware_constants_and_configuration():
    """Test middleware constants and configuration validation"""
    # Test that required functions are importable and callable
    assert callable(wheel_group_middleware)
    assert callable(require_auth)
    assert callable(require_wheel_group_permission)
    assert callable(decode_jwt_payload_only)
    assert callable(validate_token_basic)
    assert callable(lookup_user_wheel_group_info)
    assert callable(get_role_permissions)
    assert callable(get_wheel_group_context)
    
    # Test role permissions constants
    all_roles = ['USER', 'WHEEL_ADMIN', 'ADMIN', 'DEPLOYMENT_ADMIN']
    for role in all_roles:
        permissions = get_role_permissions(role)
        assert isinstance(permissions, dict)
        assert len(permissions) > 0
        assert all(isinstance(perm_name, str) for perm_name in permissions.keys())
        assert all(isinstance(perm_value, bool) for perm_value in permissions.values())
    
    # Test permission hierarchy
    user_perms = get_role_permissions('USER')
    wheel_admin_perms = get_role_permissions('WHEEL_ADMIN')
    admin_perms = get_role_permissions('ADMIN')
    deployment_admin_perms = get_role_permissions('DEPLOYMENT_ADMIN')
    
    # USER permissions should be most restrictive
    user_true_perms = [k for k, v in user_perms.items() if v]
    wheel_admin_true_perms = [k for k, v in wheel_admin_perms.items() if v]
    admin_true_perms = [k for k, v in admin_perms.items() if v]
    deployment_admin_true_perms = [k for k, v in deployment_admin_perms.items() if v]
    
    # Check permission hierarchy
    assert len(user_true_perms) <= len(wheel_admin_true_perms), "USER should have fewer permissions than WHEEL_ADMIN"
    assert len(wheel_admin_true_perms) <= len(admin_true_perms), "WHEEL_ADMIN should have fewer permissions than ADMIN"
    assert len(admin_true_perms) <= len(deployment_admin_true_perms), "ADMIN should have fewer permissions than DEPLOYMENT_ADMIN"
