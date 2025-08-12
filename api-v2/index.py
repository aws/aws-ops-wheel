"""
AWS Ops Wheel v2 - Lambda Function Handler
This is the main entry point for all Lambda functions
"""

import json
import os
import sys
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/api-v2')

from tenant_middleware import tenant_middleware
from tenant_management import lambda_handlers as tenant_handlers
from wheel_operations import lambda_handlers as wheel_handlers
from participant_operations import lambda_handlers as participant_handlers
from selection_algorithms import lambda_handlers as selection_handlers

# Constants
HTTP_METHODS = {
    'GET': 'GET',
    'POST': 'POST',
    'PUT': 'PUT',
    'DELETE': 'DELETE',
    'OPTIONS': 'OPTIONS'
}

CORS_HEADERS = {
    'CONTENT_TYPE': 'Content-Type',
    'ACCESS_CONTROL_ALLOW_ORIGIN': 'Access-Control-Allow-Origin',
    'ACCESS_CONTROL_ALLOW_METHODS': 'Access-Control-Allow-Methods',
    'ACCESS_CONTROL_ALLOW_HEADERS': 'Access-Control-Allow-Headers',
    'ACCESS_CONTROL_MAX_AGE': 'Access-Control-Max-Age'
}

DEFAULT_CORS_HEADERS = {
    CORS_HEADERS['CONTENT_TYPE']: 'application/json',
    CORS_HEADERS['ACCESS_CONTROL_ALLOW_ORIGIN']: '*',
    CORS_HEADERS['ACCESS_CONTROL_ALLOW_METHODS']: 'GET,POST,PUT,DELETE,OPTIONS',
    CORS_HEADERS['ACCESS_CONTROL_ALLOW_HEADERS']: 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
}

OPTIONS_CORS_HEADERS = {
    **DEFAULT_CORS_HEADERS,
    CORS_HEADERS['ACCESS_CONTROL_MAX_AGE']: '86400'
}

PUBLIC_ENDPOINTS = ['/v2/config', '/app/api/v2/config']

STATUS_CODES = {
    'OK': 200,
    'NOT_FOUND': 404,
    'INTERNAL_ERROR': 500
}

# Route definitions for better organization
ROUTE_PATTERNS = {
    'TENANT_BASE': '/tenant',
    'TENANT_USERS': ['/app/api/v2/tenant/users', '/v2/tenant/users'],
    'TENANT_USER_BY_ID': ['/app/api/v2/tenant/users/{user_id}', '/v2/tenant/users/{user_id}'],
    'TENANT_USER_ROLE': ['/app/api/v2/tenant/users/{user_id}/role', '/v2/tenant/users/{user_id}/role'],
    'CONFIG': '/config',
    'AUTH_ME': '/auth/me',
    'WHEELS': ['/v2/wheels', '/app/api/v2/wheels'],
    'WHEEL_BY_ID': ['/v2/wheels/{wheel_id}', '/app/api/v2/wheels/{wheel_id}'],
    'WHEEL_RESET': ['/v2/wheels/{wheel_id}/reset', '/app/api/v2/wheels/{wheel_id}/reset'],
    'WHEEL_PARTICIPANTS': ['/v2/wheels/{wheel_id}/participants', '/app/api/v2/wheels/{wheel_id}/participants'],
    'WHEEL_PARTICIPANT_BY_ID': ['/v2/wheels/{wheel_id}/participants/{participant_id}', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}'],
    'PARTICIPANT_RIG': ['/v2/wheels/{wheel_id}/participants/{participant_id}/rig', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}/rig'],
    'PARTICIPANT_SELECT': ['/v2/wheels/{wheel_id}/participants/{participant_id}/select', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}/select'],
    'WHEEL_UNRIG': ['/v2/wheels/{wheel_id}/unrig', '/app/api/v2/wheels/{wheel_id}/unrig'],
    'WHEEL_SUGGEST': ['/v2/wheels/{wheel_id}/suggest', '/app/api/v2/wheels/{wheel_id}/suggest'],
    'WHEEL_PROBABILITIES': ['/v2/wheels/{wheel_id}/probabilities', '/app/api/v2/wheels/{wheel_id}/probabilities']
}


def parse_body(event):
    """Parse request body, handling both string and dict formats"""
    if 'body' not in event:
        event['body'] = {}
        return
    
    body = event['body']
    if isinstance(body, str):
        try:
            event['body'] = json.loads(body) if body.strip() else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            event['body'] = {}


def create_cors_response(status_code, body, additional_headers=None):
    """Create standardized CORS response"""
    headers = DEFAULT_CORS_HEADERS.copy()
    if additional_headers:
        headers.update(additional_headers)
    
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(body) if isinstance(body, (dict, list)) else body
    }


def create_options_response():
    """Create standardized OPTIONS response for CORS preflight"""
    return {
        'statusCode': STATUS_CODES['OK'],
        'headers': OPTIONS_CORS_HEADERS,
        'body': ''
    }


def get_request_info(event):
    """Extract and normalize request information from event"""
    http_method = event.get('httpMethod', HTTP_METHODS['GET'])
    resource_path = event.get('resource', '')
    path_info = event.get('path', '')
    request_path = path_info if path_info else resource_path
    
    return http_method, resource_path, request_path


def is_public_endpoint(request_path):
    """Check if the endpoint is public and doesn't require authentication"""
    return any(endpoint in request_path for endpoint in PUBLIC_ENDPOINTS)


def authenticate_request(event, context, request_path):
    """Apply authentication middleware for protected endpoints"""
    if is_public_endpoint(request_path):
        return event  # Skip authentication for public endpoints
    
    auth_result = tenant_middleware(event, context)
    if isinstance(auth_result, dict) and 'statusCode' in auth_result:
        return auth_result  # Authentication failed
    
    return auth_result  # Authentication succeeded


def route_tenant_requests(http_method, resource_path, request_path, event, context):
    """Handle tenant-related requests"""
    # Tenant base endpoints (not users)
    if ROUTE_PATTERNS['TENANT_BASE'] in request_path and '/users' not in request_path:
        if http_method == HTTP_METHODS['GET']:
            return tenant_handlers['get_tenant'](event, context)
        elif http_method == HTTP_METHODS['POST']:
            return tenant_handlers['create_tenant'](event, context)
        elif http_method == HTTP_METHODS['PUT']:
            return tenant_handlers['update_tenant'](event, context)
    
    # Tenant users endpoints
    elif resource_path in ROUTE_PATTERNS['TENANT_USERS']:
        print(f"[DEBUG] Matched tenant users endpoint - Method: {http_method}")
        if http_method == HTTP_METHODS['GET']:
            return tenant_handlers['get_tenant_users'](event, context)
        elif http_method == HTTP_METHODS['POST']:
            return tenant_handlers['create_tenant_user'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    # Tenant user by ID endpoints
    elif (resource_path in ROUTE_PATTERNS['TENANT_USER_BY_ID'] or 
          (request_path.startswith('/app/api/v2/tenant/users/') and len(request_path.split('/')) == 7) or
          (request_path.startswith('/v2/tenant/users/') and len(request_path.split('/')) == 5)):
        if http_method == HTTP_METHODS['DELETE']:
            return tenant_handlers['delete_tenant_user'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    # Tenant user role endpoints
    elif resource_path in ROUTE_PATTERNS['TENANT_USER_ROLE']:
        if http_method == HTTP_METHODS['PUT']:
            return tenant_handlers['update_user_role'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    return None


def route_config_and_auth_requests(http_method, request_path, event, context):
    """Handle config and authentication requests"""
    if ROUTE_PATTERNS['CONFIG'] in request_path:
        if http_method == HTTP_METHODS['GET']:
            return tenant_handlers['get_config'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    elif ROUTE_PATTERNS['AUTH_ME'] in request_path:
        if http_method == HTTP_METHODS['GET']:
            return tenant_handlers['get_current_user'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    return None


def route_wheel_requests(http_method, resource_path, event, context):
    """Handle wheel-related requests"""
    if resource_path in ROUTE_PATTERNS['WHEELS']:
        if http_method == HTTP_METHODS['GET']:
            return wheel_handlers['list_tenant_wheels'](event, context)
        elif http_method == HTTP_METHODS['POST']:
            return wheel_handlers['create_wheel'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['WHEEL_BY_ID']:
        if http_method == HTTP_METHODS['GET']:
            return wheel_handlers['get_wheel'](event, context)
        elif http_method == HTTP_METHODS['PUT']:
            return wheel_handlers['update_wheel'](event, context)
        elif http_method == HTTP_METHODS['DELETE']:
            return wheel_handlers['delete_wheel'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['WHEEL_RESET']:
        if http_method == HTTP_METHODS['POST']:
            return wheel_handlers['reset_wheel_weights'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    return None


def route_participant_requests(http_method, resource_path, event, context):
    """Handle participant-related requests"""
    if resource_path in ROUTE_PATTERNS['WHEEL_PARTICIPANTS']:
        if http_method == HTTP_METHODS['GET']:
            return participant_handlers['list_wheel_participants'](event, context)
        elif http_method == HTTP_METHODS['POST']:
            return participant_handlers['create_participant'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['WHEEL_PARTICIPANT_BY_ID']:
        if http_method == HTTP_METHODS['GET']:
            return participant_handlers['get_participant'](event, context)
        elif http_method == HTTP_METHODS['PUT']:
            return participant_handlers['update_participant'](event, context)
        elif http_method == HTTP_METHODS['DELETE']:
            return participant_handlers['delete_participant'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['PARTICIPANT_RIG']:
        if http_method == HTTP_METHODS['POST']:
            return participant_handlers['rig_participant'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['PARTICIPANT_SELECT']:
        if http_method == HTTP_METHODS['POST']:
            return participant_handlers['select_participant'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['WHEEL_UNRIG']:
        if http_method == HTTP_METHODS['DELETE']:
            return participant_handlers['remove_rigging'](event, context)
        elif http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
    
    return None


def route_selection_requests(http_method, resource_path, event, context):
    """Handle selection algorithm requests"""
    if resource_path in ROUTE_PATTERNS['WHEEL_SUGGEST']:
        if http_method == HTTP_METHODS['POST']:
            return selection_handlers['suggest_participant'](event, context)
    
    elif resource_path in ROUTE_PATTERNS['WHEEL_PROBABILITIES']:
        if http_method == HTTP_METHODS['GET']:
            return selection_handlers['get_selection_probabilities'](event, context)
    
    return None


def lambda_handler(event, context):
    """
    Main Lambda handler that routes requests to appropriate modules based on resource path
    """
    print(f"[ENTRY] Lambda handler started")
    try:
        print(f"[DEBUG] Received event: {json.dumps(event)}")
        
        # Parse request body
        parse_body(event)
        
        # Extract request information
        http_method, resource_path, request_path = get_request_info(event)
        print(f"[DEBUG] Method: {http_method}, Resource: {resource_path}, Path: {request_path}")
        
        # Authenticate request if needed
        auth_result = authenticate_request(event, context, request_path)
        if isinstance(auth_result, dict) and 'statusCode' in auth_result:
            return auth_result  # Authentication failed
        event = auth_result  # Use authenticated event
        
        # Route to appropriate handler
        # Try tenant requests first
        result = route_tenant_requests(http_method, resource_path, request_path, event, context)
        if result:
            return result
        
        # Try config and auth requests
        result = route_config_and_auth_requests(http_method, request_path, event, context)
        if result:
            return result
        
        # Try wheel requests
        result = route_wheel_requests(http_method, resource_path, event, context)
        if result:
            return result
        
        # Try participant requests
        result = route_participant_requests(http_method, resource_path, event, context)
        if result:
            return result
        
        # Try selection requests
        result = route_selection_requests(http_method, resource_path, event, context)
        if result:
            return result
        
        # Handle OPTIONS requests for CORS preflight
        if http_method == HTTP_METHODS['OPTIONS']:
            return create_options_response()
        
        # No route found
        return create_cors_response(STATUS_CODES['NOT_FOUND'], 
                                  {'error': f'Route not found: {http_method} {request_path}'})
            
    except Exception as e:
        print(f"[ERROR] Lambda handler error: {str(e)}")
        return create_cors_response(STATUS_CODES['INTERNAL_ERROR'], 
                                  {'error': f'Internal server error: {str(e)}'})
