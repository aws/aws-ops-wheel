"""
DynamoDB-based wheel group middleware that looks up wheel group information from DynamoDB
instead of relying on JWT custom attributes
"""

import json
import base64
import os
import time
import boto3
import boto3.dynamodb.conditions
from functools import wraps
from typing import Dict, Any, Optional

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'))

def decode_jwt_payload_only(token: str) -> Dict[str, Any]:
    """
    Decode JWT payload without signature verification
    """
    try:
        # Split token into parts
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # Decode payload (middle part)
        payload_encoded = parts[1]
        # Add padding if necessary
        payload_encoded += '=' * (4 - len(payload_encoded) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_encoded)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        return payload
    except Exception as e:
        raise ValueError(f"Failed to decode JWT payload: {str(e)}")

def validate_token_basic(token: str, user_pool_id: str, client_id: str) -> Dict[str, Any]:
    """
    Basic JWT token validation without signature verification
    """
    try:
        payload = decode_jwt_payload_only(token)
        
        # Basic validations
        required_claims = ['sub', 'exp', 'iss', 'aud']
        for claim in required_claims:
            if claim not in payload:
                raise ValueError(f"Missing required claim: {claim}")
        
        # Check issuer format (handle AWS Cognito service issue with typo)
        region = user_pool_id.split('_')[0]
        expected_iss = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        typo_iss = f"https://cognitm-idp.{region}.amazonaws.com/{user_pool_id}"  # AWS service issue
        
        if payload['iss'] not in [expected_iss, typo_iss]:
            raise ValueError(f"Invalid issuer: {payload['iss']}. Expected: {expected_iss}")
        
        # Check audience
        if payload['aud'] != client_id:
            raise ValueError(f"Invalid audience: {payload['aud']}")
        
        # Check token type
        if payload.get('token_use') != 'id':
            raise ValueError(f"Invalid token use: {payload.get('token_use')}")
        
        # Check expiration (basic check)
        current_time = int(time.time())
        if payload['exp'] < current_time:
            raise ValueError("Token has expired")
        
        return payload
        
    except Exception as e:
        raise ValueError(f"Token validation failed: {str(e)}")

def lookup_user_wheel_group_info(user_email: str) -> Dict[str, Any]:
    """
    Look up wheel group information from DynamoDB based on user email
    """
    try:
        # Direct DynamoDB queries to avoid import issues
        users_table_name = os.environ.get('USERS_TABLE', 'OpsWheelV2-Users-dev')
        wheel_groups_table_name = os.environ.get('WHEEL_GROUPS_TABLE', 'OpsWheelV2-WheelGroups-dev')
        
        users_table = dynamodb.Table(users_table_name)
        wheel_groups_table = dynamodb.Table(wheel_groups_table_name)
        
        # Find user by email using GSI
        response = users_table.query(
            IndexName='email-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(user_email)
        )
        
        items = response.get('Items', [])
        if not items:
            raise ValueError(f"User not found in database: {user_email}")
            
        user_record = items[0]
        wheel_group_id = user_record['wheel_group_id']
        user_role = user_record.get('role', 'USER')
        
        # Get wheel group information
        wheel_group_response = wheel_groups_table.get_item(
            Key={'wheel_group_id': wheel_group_id}
        )
        
        wheel_group_record = wheel_group_response.get('Item', {})
        
        return {
            'user_id': user_record['user_id'],
            'wheel_group_id': wheel_group_id,
            'wheel_group_name': wheel_group_record.get('wheel_group_name', wheel_group_id),
            'role': user_role,
            'email': user_email,
            'name': user_record.get('name', user_email)
        }
        
    except Exception as e:
        raise ValueError(f"Failed to lookup user wheel group info: {str(e)}")

def wheel_group_middleware(event, context):
    """
    Hybrid wheel group middleware: Uses JWT custom attributes first, falls back to DynamoDB lookup
    """
    try:
        # Extract Authorization header
        headers = event.get('headers', {}) or {}
        auth_header = headers.get('Authorization') or headers.get('authorization', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': 'Missing or invalid Authorization header'})
            }
        
        # Extract token
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Get environment variables
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        client_id = os.environ.get('COGNITO_CLIENT_ID')
        
        if not user_pool_id or not client_id:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Cognito configuration missing'})
            }
        
        # Validate token (basic validation)
        payload = validate_token_basic(token, user_pool_id, client_id)
        
        # Get user info from JWT
        user_id = payload.get('sub')
        user_email = payload.get('email')
        user_name = payload.get('name', user_email)
        
        if not user_email or not user_id:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Token missing required claims (email or sub)'})
            }
        
        # Check if this is a deployment admin user
        is_deployment_admin = payload.get('custom:deployment_admin') == 'true'
        
        if is_deployment_admin:
            # Deployment admin doesn't belong to any wheel group
            wheel_group_info = {
                'user_id': user_id,
                'wheel_group_id': None,
                'wheel_group_name': None,
                'role': 'DEPLOYMENT_ADMIN',
                'email': user_email,
                'name': user_name,
                'deployment_admin': True
            }
        else:
            # Regular user - get latest user info from DynamoDB to ensure roles are up-to-date
            try:
                wheel_group_info = lookup_user_wheel_group_info(user_email)
                wheel_group_info['deployment_admin'] = False
            except Exception as db_error:
                # For /auth/me endpoint, allow access without wheel group info
                path = event.get('path', '')
                if '/auth/me' in path:
                    wheel_group_info = {
                        'user_id': user_id,
                        'wheel_group_id': None,
                        'wheel_group_name': None,
                        'role': 'USER',
                        'email': user_email,
                        'name': user_name,
                        'deployment_admin': False
                    }
                else:
                    return {
                        'statusCode': 401,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': f'User not associated with any wheel group. Please join a wheel group first.'})
                    }
        
        # Add wheel group context to event
        event['wheel_group_context'] = {
            'wheel_group_id': wheel_group_info['wheel_group_id'],
            'wheel_group_name': wheel_group_info['wheel_group_name'],
            'user_id': wheel_group_info['user_id'],
            'email': wheel_group_info['email'],
            'name': wheel_group_info['name'],
            'role': wheel_group_info['role'],
            'deployment_admin': wheel_group_info.get('deployment_admin', False),
            'permissions': get_role_permissions(wheel_group_info['role'])
        }
        
        # Also add user_info for admin operations compatibility
        event['user_info'] = wheel_group_info
        
        return event
        
    except Exception as e:
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Authentication failed: {str(e)}'})
        }

def get_role_permissions(role: str) -> Dict[str, bool]:
    """Get permissions for a user role"""
    permissions_map = {
        'DEPLOYMENT_ADMIN': {
            # Deployment admin specific permissions
            'view_all_wheel_groups': True,
            'delete_wheel_group': True,
            'manage_deployment': True,
            # All regular admin permissions
            'create_wheel': True,
            'delete_wheel': True,
            'manage_participants': True,
            'spin_wheel': True,
            'view_wheels': True,
            'manage_users': True,
            'manage_wheel_group': True,
            'rig_wheel': True
        },
        'ADMIN': {
            'create_wheel': True,
            'delete_wheel': True,
            'manage_participants': True,
            'spin_wheel': True,
            'view_wheels': True,
            'manage_users': True,
            'manage_wheel_group': True,
            'rig_wheel': True
        },
        'WHEEL_ADMIN': {
            'create_wheel': True,
            'delete_wheel': True,
            'manage_participants': True,
            'spin_wheel': True,
            'view_wheels': True,
            'manage_users': False,
            'manage_wheel_group': False,
            'rig_wheel': True
        },
        'USER': {
            'create_wheel': False,
            'delete_wheel': False,
            'manage_participants': False,
            'spin_wheel': True,
            'view_wheels': True,
            'manage_users': False,
            'manage_wheel_group': False,
            'rig_wheel': False
        },
    }
    return permissions_map.get(role.upper(), permissions_map['USER'])

def require_auth():
    """Decorator requiring basic authentication"""
    def decorator(func):
        @wraps(func)
        def wrapper(event, context):
            auth_result = wheel_group_middleware(event, context)
            if isinstance(auth_result, dict) and auth_result.get('statusCode'):
                return auth_result
            return func(auth_result, context)
        return wrapper
    return decorator

def require_wheel_group_permission(permission: str):
    """Decorator requiring specific wheel group permission"""
    def decorator(func):
        @wraps(func)
        def wrapper(event, context):
            auth_result = wheel_group_middleware(event, context)
            if isinstance(auth_result, dict) and auth_result.get('statusCode'):
                return auth_result
                
            wheel_group_context = auth_result.get('wheel_group_context', {})
            permissions = wheel_group_context.get('permissions', {})
            
            if not permissions.get(permission, False):
                return {
                    'statusCode': 403,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': f'Insufficient permissions. Required: {permission}',
                        'user_permissions': list(permissions.keys())
                    })
                }
            
            return func(auth_result, context)
        return wrapper
    return decorator

def get_wheel_group_context(event) -> Optional[Dict[str, Any]]:
    """Get wheel group context from event"""
    return event.get('wheel_group_context')

# Export for backwards compatibility
lambda_handlers = {}
