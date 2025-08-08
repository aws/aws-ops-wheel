#  Tenant Management APIs for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import boto3
from typing import Dict, Any
from base import BadRequestError, NotFoundError
from tenant_middleware import tenant_middleware, require_auth, require_tenant_permission, get_tenant_context
from utils_v2 import (
    TenantRepository, UserRepository, check_string, get_uuid, get_utc_timestamp,
    decimal_to_float
)


@require_auth()
def create_tenant(event, context=None):
    """
    Create a new tenant (open registration)
    
    POST /v2/tenant
    
    {
      "tenant_name": "My Company",
      "domain": "mycompany.com",  # Optional
      "admin_user": {
        "email": "admin@mycompany.com",
        "name": "Admin User"
      }
    }
    """
    try:
        body = event.get('body', {})
        
        # Validate required fields
        if not check_string(body.get('tenant_name')):
            raise BadRequestError("tenant_name is required and must be a non-empty string")
        
        admin_user = body.get('admin_user', {})
        if not check_string(admin_user.get('email')):
            raise BadRequestError("admin_user.email is required")
        
        # Get current user context (they will become the admin)
        user_context = get_tenant_context(event)
        user_id = user_context['user_id']
        
        # Check if user is already associated with a tenant
        try:
            existing_user = UserRepository.get_user(user_id)
            if existing_user.get('tenant_id'):
                raise BadRequestError("User is already associated with a tenant")
        except NotFoundError:
            # User doesn't exist in our system yet, which is fine
            pass
        
        from decimal import Decimal
        
        # Create tenant
        tenant_data = {
            'tenant_name': body['tenant_name'],
            'domain': body.get('domain'),
            'quotas': body.get('quotas', {
                'max_wheels': 50,
                'max_participants_per_wheel': 100,
                'max_multi_select': 10
            }),
            'settings': body.get('settings', {
                'allow_rigging': True,
                'default_participant_weight': Decimal('1.0'),
                'theme': 'default',
                'timezone': 'UTC'
            })
        }
        
        tenant = TenantRepository.create_tenant(tenant_data)
        
        # Create/update user as admin
        user_data = {
            'user_id': user_id,
            'tenant_id': tenant['tenant_id'],
            'email': admin_user['email'],
            'name': admin_user.get('name', admin_user['email']),
            'role': 'ADMIN'
        }
        
        try:
            # Update existing user
            UserRepository.update_user(user_id, {
                'tenant_id': tenant['tenant_id'],
                'role': 'ADMIN'
            })
        except NotFoundError:
            # Create new user
            UserRepository.create_user(user_data)
        
        # Update Cognito user attributes
        cognito_client = boto3.client('cognito-idp')
        try:
            cognito_client.admin_update_user_attributes(
                UserPoolId=event.get('requestContext', {}).get('authorizer', {}).get('userPoolId'),
                Username=user_context['email'],
                UserAttributes=[
                    {'Name': 'custom:tenant_id', 'Value': tenant['tenant_id']},
                    {'Name': 'custom:role', 'Value': 'ADMIN'},
                    {'Name': 'custom:tenant_name', 'Value': tenant['tenant_name']}
                ]
            )
        except Exception as e:
            # Log error but don't fail the request
            # Log error but don't fail the request
            pass
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(tenant))
        }
        
    except (BadRequestError, NotFoundError) as e:
        return {
            'statusCode': 400 if isinstance(e, BadRequestError) else 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }


@require_tenant_permission('view_wheels')
def get_tenant(event, context=None):
    """
    Get current tenant information
    
    GET /v2/tenant
    """
    try:
        tenant_context = get_tenant_context(event)
        tenant = TenantRepository.get_tenant(tenant_context['tenant_id'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(tenant))
        }
        
    except NotFoundError as e:
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }


@require_tenant_permission('manage_tenant')
def update_tenant(event, context=None):
    """
    Update tenant settings (Admin only)
    
    PUT /v2/tenant
    
    {
      "tenant_name": "Updated Name",
      "settings": {
        "allow_rigging": false,
        "theme": "dark"
      },
      "quotas": {
        "max_wheels": 100
      }
    }
    """
    try:
        tenant_context = get_tenant_context(event)
        body = event.get('body', {})
        
        # Validate updates
        updates = {}
        
        if 'tenant_name' in body:
            if not check_string(body['tenant_name']):
                raise BadRequestError("tenant_name must be a non-empty string")
            updates['tenant_name'] = body['tenant_name']
        
        if 'domain' in body:
            updates['domain'] = body['domain']
        
        if 'settings' in body:
            if not isinstance(body['settings'], dict):
                raise BadRequestError("settings must be an object")
            updates['settings'] = body['settings']
        
        if 'quotas' in body:
            if not isinstance(body['quotas'], dict):
                raise BadRequestError("quotas must be an object")
            updates['quotas'] = body['quotas']
        
        if not updates:
            raise BadRequestError("At least one field must be provided for update")
        
        # Update tenant
        updated_tenant = TenantRepository.update_tenant(tenant_context['tenant_id'], updates)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(updated_tenant))
        }
        
    except BadRequestError as e:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }


@require_tenant_permission('view_wheels')
def get_tenant_users(event, context=None):
    """
    Get all users in the current tenant
    
    GET /v2/tenant/users
    """
    try:
        tenant_context = get_tenant_context(event)
        users = UserRepository.get_users_by_tenant(tenant_context['tenant_id'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'users': decimal_to_float(users),
                'count': len(users)
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }


@require_tenant_permission('manage_users')
def update_user_role(event, context=None):
    """
    Update a user's role within the tenant (Admin only)
    
    PUT /v2/tenant/users/{user_id}/role
    
    {
      "role": "WHEEL_ADMIN"
    }
    """
    try:
        tenant_context = get_tenant_context(event)
        user_id = event.get('pathParameters', {}).get('user_id')
        body = event.get('body', {})
        
        if not user_id:
            raise BadRequestError("user_id is required")
        
        new_role = body.get('role')
        valid_roles = ['ADMIN', 'WHEEL_ADMIN', 'USER', 'VIEWER']
        
        if new_role not in valid_roles:
            raise BadRequestError(f"role must be one of: {', '.join(valid_roles)}")
        
        # Verify user belongs to this tenant
        user = UserRepository.get_user(user_id)
        if user['tenant_id'] != tenant_context['tenant_id']:
            raise NotFoundError("User not found in this tenant")
        
        # Update user role
        updated_user = UserRepository.update_user_role(user_id, new_role)
        
        # Update Cognito user attributes
        cognito_client = boto3.client('cognito-idp')
        try:
            cognito_client.admin_update_user_attributes(
                UserPoolId=event.get('requestContext', {}).get('authorizer', {}).get('userPoolId'),
                Username=user['email'],
                UserAttributes=[
                    {'Name': 'custom:role', 'Value': new_role}
                ]
            )
        except Exception as e:
            # Log error but don't fail the request
            pass
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(updated_user))
        }
        
    except (BadRequestError, NotFoundError) as e:
        return {
            'statusCode': e.status_code if hasattr(e, 'status_code') else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }


def get_config(event, context=None):
    """
    Get configuration information (enhanced version of original config endpoint)
    This endpoint is public and doesn't require authentication as it's needed for bootstrapping
    
    GET /v2/config
    """
    try:
        import os
        
        config = {
            'UserPoolId': os.environ.get('COGNITO_USER_POOL_ID'),
            'ClientId': os.environ.get('COGNITO_CLIENT_ID'),
            'REGION': os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'),
            'API_VERSION': '2.0',
            'MULTI_TENANT_ENABLED': True,
            'MAX_MULTI_SELECT': 10,
            'SUPPORTED_ROLES': ['ADMIN', 'WHEEL_ADMIN', 'USER', 'VIEWER']
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(config)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }


# Export Lambda handler functions
lambda_handlers = {
    'create_tenant': create_tenant,
    'get_tenant': get_tenant,
    'update_tenant': update_tenant,
    'get_tenant_users': get_tenant_users,
    'update_user_role': update_user_role,
    'get_config': get_config
}
