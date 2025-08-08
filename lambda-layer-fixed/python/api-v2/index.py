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
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }
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
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Max-Age': '86400'
        },
        'body': ''
    }


def lambda_handler(event, context):
    """
    Main Lambda handler that routes requests to appropriate modules based on resource path
    """
    try:
        # Parse request body
        parse_body(event)
        
        # Get the HTTP method and resource path
        http_method = event.get('httpMethod', 'GET')
        resource_path = event.get('resource', '')
        
        # Check if this is a public endpoint that doesn't need authentication
        public_endpoints = ['/v2/config', '/app/api/v2/config']
        is_public_endpoint = resource_path in public_endpoints
        
        # Apply tenant middleware only for authenticated endpoints
        if not is_public_endpoint:
            auth_result = tenant_middleware(event, context)
            if isinstance(auth_result, dict) and 'statusCode' in auth_result:
                # Authentication failed, return error response
                return auth_result
            
            # Authentication succeeded, use the authenticated event
            event = auth_result
        
        # Route to appropriate handler based on resource path and method
        # API Gateway sends paths like /app/api/v2/wheels, so handle both formats for compatibility
        if resource_path in ['/v2/tenant', '/app/api/v2/tenant']:
            if http_method == 'GET':
                return tenant_handlers['get_tenant'](event, context)
            elif http_method == 'POST':
                return tenant_handlers['create_tenant'](event, context)
            elif http_method == 'PUT':
                return tenant_handlers['update_tenant'](event, context)
        
        elif resource_path in ['/v2/tenant/users', '/app/api/v2/tenant/users']:
            if http_method == 'GET':
                return tenant_handlers['get_tenant_users'](event, context)
                
        elif resource_path in ['/v2/tenant/users/{user_id}/role', '/app/api/v2/tenant/users/{user_id}/role']:
            if http_method == 'PUT':
                return tenant_handlers['update_user_role'](event, context)
                
        elif resource_path in ['/v2/config', '/app/api/v2/config']:
            if http_method == 'GET':
                return tenant_handlers['get_config'](event, context)
            elif http_method == 'OPTIONS':
                return create_options_response()
                
        elif resource_path in ['/v2/wheels', '/app/api/v2/wheels']:
            if http_method == 'GET':
                return wheel_handlers['list_tenant_wheels'](event, context)
            elif http_method == 'POST':
                return wheel_handlers['create_wheel'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}', '/app/api/v2/wheels/{wheel_id}']:
            if http_method == 'GET':
                return wheel_handlers['get_wheel'](event, context)
            elif http_method == 'PUT':
                return wheel_handlers['update_wheel'](event, context)
            elif http_method == 'DELETE':
                return wheel_handlers['delete_wheel'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}/reset', '/app/api/v2/wheels/{wheel_id}/reset']:
            if http_method == 'POST':
                return wheel_handlers['reset_wheel_weights'](event, context)
            elif http_method == 'OPTIONS':
                return create_options_response()
                
        elif resource_path in ['/v2/wheels/{wheel_id}/participants', '/app/api/v2/wheels/{wheel_id}/participants']:
            if http_method == 'GET':
                return participant_handlers['list_wheel_participants'](event, context)
            elif http_method == 'POST':
                return participant_handlers['create_participant'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}/participants/{participant_id}', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}']:
            if http_method == 'GET':
                return participant_handlers['get_participant'](event, context)
            elif http_method == 'PUT':
                return participant_handlers['update_participant'](event, context)
            elif http_method == 'DELETE':
                return participant_handlers['delete_participant'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}/participants/{participant_id}/rig', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}/rig']:
            if http_method == 'POST':
                return participant_handlers['rig_participant'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}/participants/{participant_id}/select', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}/select']:
            if http_method == 'POST':
                return participant_handlers['select_participant'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}/unrig', '/app/api/v2/wheels/{wheel_id}/unrig']:
            if http_method == 'DELETE':
                return participant_handlers['remove_rigging'](event, context)
            elif http_method == 'OPTIONS':
                return create_options_response()
                
        elif resource_path in ['/v2/wheels/{wheel_id}/suggest', '/app/api/v2/wheels/{wheel_id}/suggest']:
            if http_method == 'POST':
                return selection_handlers['suggest_participant'](event, context)
                
        elif resource_path in ['/v2/wheels/{wheel_id}/probabilities', '/app/api/v2/wheels/{wheel_id}/probabilities']:
            if http_method == 'GET':
                return selection_handlers['get_selection_probabilities'](event, context)
                
        # Handle OPTIONS requests for CORS preflight
        elif http_method == 'OPTIONS':
            return create_options_response()
        else:
            return create_cors_response(404, {'error': f'Resource not found: {resource_path}'})
            
    except Exception as e:
        return create_cors_response(500, {'error': f'Internal server error: {str(e)}'})
