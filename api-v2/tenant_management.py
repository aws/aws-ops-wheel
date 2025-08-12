#  Tenant Management APIs for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import os
import boto3
from typing import Dict, Any
from base import BadRequestError, NotFoundError
from tenant_middleware import tenant_middleware, require_auth, require_tenant_permission, get_tenant_context
from utils_v2 import (
    TenantRepository, UserRepository, check_string, get_uuid, get_utc_timestamp,
    decimal_to_float
)

# Constants
HTTP_STATUS_CODES = {
    'OK': 200,
    'CREATED': 201,
    'BAD_REQUEST': 400,
    'UNAUTHORIZED': 401,
    'NOT_FOUND': 404,
    'INTERNAL_ERROR': 500
}

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}

USER_ROLES = {
    'ADMIN': 'ADMIN',
    'WHEEL_ADMIN': 'WHEEL_ADMIN', 
    'USER': 'USER'
}

VALID_ROLES = list(USER_ROLES.values())

DEFAULT_TENANT_QUOTAS = {
    'max_wheels': 50,
    'max_participants_per_wheel': 100,
    'max_multi_select': 10
}

DEFAULT_TENANT_SETTINGS = {
    'allow_rigging': True,
    'default_participant_weight': 1.0,  # Will be converted to Decimal
    'theme': 'default',
    'timezone': 'UTC'
}

VALIDATION_MESSAGES = {
    'TENANT_NAME_REQUIRED': "tenant_name is required and must be a non-empty string",
    'ADMIN_EMAIL_REQUIRED': "admin_user.email is required",
    'USER_HAS_TENANT': "User is already associated with a tenant",
    'EMAIL_REQUIRED': "email is required and must be a non-empty string",
    'USERNAME_REQUIRED': "username is required and must be a non-empty string",
    'INVALID_ROLE': f"role must be one of: {', '.join(VALID_ROLES)}",
    'USERNAME_TAKEN': "Username '{}' is already taken in this tenant",
    'USER_ID_REQUIRED': "user_id is required",
    'USER_NOT_IN_TENANT': "User not found in this tenant",
    'CANNOT_DELETE_SELF': "Cannot delete your own account",
    'UPDATE_FIELD_REQUIRED': "At least one field must be provided for update",
    'SETTINGS_MUST_BE_OBJECT': "settings must be an object",
    'QUOTAS_MUST_BE_OBJECT': "quotas must be an object"
}

COGNITO_CONFIG = {
    'TEMP_PASSWORD': 'TempPass123!',
    'MESSAGE_ACTION': 'SUPPRESS'
}


def create_api_response(status_code: int, body: Any, additional_headers: Dict = None) -> Dict:
    """Create standardized API response with CORS headers"""
    headers = CORS_HEADERS.copy()
    if additional_headers:
        headers.update(additional_headers)
    
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(decimal_to_float(body) if isinstance(body, (dict, list)) else body)
    }


def create_error_response(status_code: int, error_message: str) -> Dict:
    """Create standardized error response"""
    return create_api_response(status_code, {'error': error_message})


def handle_api_exceptions(func):
    """Decorator to handle common API exceptions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BadRequestError as e:
            return create_error_response(HTTP_STATUS_CODES['BAD_REQUEST'], str(e))
        except NotFoundError as e:
            return create_error_response(HTTP_STATUS_CODES['NOT_FOUND'], str(e))
        except Exception as e:
            print(f"[ERROR] {func.__name__} error: {str(e)}")
            return create_error_response(HTTP_STATUS_CODES['INTERNAL_ERROR'], f'Internal server error: {str(e)}')
    
    return wrapper


def validate_role(role: str) -> None:
    """Validate user role"""
    if role not in VALID_ROLES:
        raise BadRequestError(VALIDATION_MESSAGES['INVALID_ROLE'])


def validate_required_string(value: Any, field_name: str) -> None:
    """Validate required string field"""
    if not check_string(value):
        raise BadRequestError(f"{field_name} is required and must be a non-empty string")


def create_cognito_user(email: str, username: str, tenant_id: str) -> str:
    """Create user in Cognito and return the user ID (sub)"""
    cognito_client = boto3.client('cognito-idp')
    user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
    
    try:
        cognito_response = cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'name', 'Value': username},
                {'Name': 'custom:tenant_id', 'Value': tenant_id}
            ],
            TemporaryPassword=COGNITO_CONFIG['TEMP_PASSWORD'],
            MessageAction=COGNITO_CONFIG['MESSAGE_ACTION']
        )
        
        # Extract Cognito user ID (sub)
        for attr in cognito_response['User']['Attributes']:
            if attr['Name'] == 'sub':
                return attr['Value']
        
        raise Exception("Failed to get Cognito user ID from response")
        
    except cognito_client.exceptions.UsernameExistsException:
        raise BadRequestError(f"A user with email {email} already exists")
    except Exception as e:
        print(f"[ERROR] Failed to create Cognito user: {str(e)}")
        raise BadRequestError(f"Failed to create user in authentication system: {str(e)}")


def delete_cognito_user(email: str) -> None:
    """Delete user from Cognito"""
    cognito_client = boto3.client('cognito-idp')
    user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
    
    try:
        cognito_client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=email
        )
        print(f"[DEBUG] Deleted Cognito user: {email}")
    except cognito_client.exceptions.UserNotFoundException:
        print(f"[DEBUG] User {email} not found in Cognito (already deleted?)")
    except Exception as e:
        print(f"[ERROR] Failed to delete Cognito user: {str(e)}")
        # Don't fail the request if Cognito deletion fails


@require_auth()
@handle_api_exceptions
def create_tenant(event, context=None):
    """
    Create a new tenant (open registration)
    
    POST /v2/tenant
    
    {
      "tenant_name": "My Company",
      "admin_user": {
        "email": "admin@mycompany.com",
        "name": "Admin User"
      }
    }
    """
    body = event.get('body', {})
    
    # Validate required fields
    validate_required_string(body.get('tenant_name'), 'tenant_name')
    
    admin_user = body.get('admin_user', {})
    validate_required_string(admin_user.get('email'), 'admin_user.email')
    
    # Get current user context (they will become the admin)
    user_context = get_tenant_context(event)
    user_id = user_context['user_id']
    
    # Check if user is already associated with a tenant
    try:
        existing_user = UserRepository.get_user(user_id)
        if existing_user.get('tenant_id'):
            raise BadRequestError(VALIDATION_MESSAGES['USER_HAS_TENANT'])
    except NotFoundError:
        # User doesn't exist in our system yet, which is fine
        pass
    
    from decimal import Decimal
    
    # Create tenant with default values
    tenant_data = {
        'tenant_name': body['tenant_name'],
        'quotas': body.get('quotas', DEFAULT_TENANT_QUOTAS),
        'settings': body.get('settings', {
            **DEFAULT_TENANT_SETTINGS,
            'default_participant_weight': Decimal(str(DEFAULT_TENANT_SETTINGS['default_participant_weight']))
        })
    }
    
    tenant = TenantRepository.create_tenant(tenant_data)
    
    # Create/update user as admin
    user_data = {
        'user_id': user_id,
        'tenant_id': tenant['tenant_id'],
        'email': admin_user['email'],
        'name': admin_user.get('name', admin_user['email']),
        'role': USER_ROLES['ADMIN']
    }
    
    try:
        # Update existing user
        UserRepository.update_user(user_id, {
            'tenant_id': tenant['tenant_id'],
            'role': USER_ROLES['ADMIN']
        })
    except NotFoundError:
        # Create new user
        UserRepository.create_user(user_data)
    
    # Update Cognito user attributes
    try:
        cognito_client = boto3.client('cognito-idp')
        cognito_client.admin_update_user_attributes(
            UserPoolId=event.get('requestContext', {}).get('authorizer', {}).get('userPoolId'),
            Username=user_context['email'],
            UserAttributes=[
                {'Name': 'custom:tenant_id', 'Value': tenant['tenant_id']}
            ]
        )
    except Exception as e:
        # Log error but don't fail the request
        print(f"[WARNING] Failed to update Cognito attributes: {str(e)}")
    
    return create_api_response(HTTP_STATUS_CODES['CREATED'], tenant)


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


@require_tenant_permission('manage_users')
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
def create_tenant_user(event, context=None):
    """
    Create a new user in the current tenant (Admin only)
    
    POST /v2/tenant/users
    
    {
      "email": "newuser@test.com",
      "name": "New User",
      "role": "USER"
    }
    """
    try:
        print(f"[DEBUG] create_tenant_user called with event: {json.dumps(event)}")
        tenant_context = get_tenant_context(event)
        print(f"[DEBUG] tenant_context: {tenant_context}")
        body = event.get('body', {})
        print(f"[DEBUG] request body: {body}")
        
        # Validate required fields
        if not check_string(body.get('email')):
            raise BadRequestError("email is required and must be a non-empty string")
        
        if not check_string(body.get('username')):
            raise BadRequestError("username is required and must be a non-empty string")
        
        user_role = body.get('role', 'USER')
        valid_roles = ['ADMIN', 'WHEEL_ADMIN', 'USER']
        
        if user_role not in valid_roles:
            raise BadRequestError(f"role must be one of: {', '.join(valid_roles)}")
        
        # Check if username is unique within the tenant
        try:
            existing_users = UserRepository.get_users_by_tenant(tenant_context['tenant_id'])
            for existing_user in existing_users:
                if existing_user.get('name', '').lower() == body['username'].lower():
                    raise BadRequestError(f"Username '{body['username']}' is already taken in this tenant")
        except Exception as e:
            # If we can't check existing users, log the error but don't fail
            print(f"[WARNING] Could not check existing usernames: {str(e)}")
        
        # Create user in Cognito first to get the Cognito sub (user ID)
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        
        try:
            # Create user in Cognito with temporary password
            cognito_response = cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=body['email'],  # Use email as username
                UserAttributes=[
                    {'Name': 'email', 'Value': body['email']},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'name', 'Value': body['username']},
                    {'Name': 'custom:tenant_id', 'Value': tenant_context['tenant_id']}
                ],
                TemporaryPassword='TempPass123!',  # User must change on first login
                MessageAction='SUPPRESS'  # Don't send welcome email automatically
            )
            
            print(f"[DEBUG] Created Cognito user: {cognito_response}")
            
            # Extract the Cognito user ID (sub) from the response
            cognito_user_id = None
            for attr in cognito_response['User']['Attributes']:
                if attr['Name'] == 'sub':
                    cognito_user_id = attr['Value']
                    break
            
            if not cognito_user_id:
                raise Exception("Failed to get Cognito user ID from response")
            
            print(f"[DEBUG] Cognito user ID (sub): {cognito_user_id}")
            
        except cognito_client.exceptions.UsernameExistsException:
            raise BadRequestError(f"A user with email {body['email']} already exists")
        except Exception as e:
            print(f"[ERROR] Failed to create Cognito user: {str(e)}")
            raise BadRequestError(f"Failed to create user in authentication system: {str(e)}")
        
        # Create user data using the Cognito user ID as the DynamoDB user_id
        user_data = {
            'user_id': cognito_user_id,  # Use Cognito sub as DynamoDB user_id
            'tenant_id': tenant_context['tenant_id'],
            'email': body['email'],
            'name': body['username'],
            'role': user_role,
            'created_at': get_utc_timestamp()
        }
        
        # Create user in DynamoDB with matching user_id
        created_user = UserRepository.create_user(user_data)
        
        # Add temporary password info to response (admin needs to communicate this to user)
        created_user['temporary_password'] = 'TempPass123!'
        created_user['password_reset_required'] = True
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(created_user))
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
        valid_roles = ['ADMIN', 'WHEEL_ADMIN', 'USER']
        
        if new_role not in valid_roles:
            raise BadRequestError(f"role must be one of: {', '.join(valid_roles)}")
        
        # Verify user belongs to this tenant
        user = UserRepository.get_user(user_id)
        if user['tenant_id'] != tenant_context['tenant_id']:
            raise NotFoundError("User not found in this tenant")
        
        # Update user role
        updated_user = UserRepository.update_user_role(user_id, new_role)
        
        # Update Cognito user attributes (skip role since it's not in schema)
        # Role is stored in DynamoDB and used by authorizer
        print(f"[DEBUG] Updated user role in DynamoDB: {user['email']} -> {new_role}")
        
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
            'SUPPORTED_ROLES': ['ADMIN', 'WHEEL_ADMIN', 'USER']
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
@require_auth()
def get_current_user(event, context):
    """Get current user information including role and tenant details"""
    try:
        # User info is already validated and attached by tenant_middleware
        tenant_context = get_tenant_context(event)
        
        if not tenant_context:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'User context not found'})
            }
        
        # Handle users without tenant associations
        if not tenant_context['tenant_id']:
            response_data = {
                'user_id': tenant_context['user_id'],
                'email': tenant_context.get('email'),
                'name': tenant_context.get('name'),
                'role': tenant_context.get('role', 'USER'),
                'tenant_id': None,
                'tenant_name': None,
                'permissions': tenant_context.get('permissions', []),
                'needs_tenant_association': True
            }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response_data)
            }
        
        # Get user details from DynamoDB
        try:
            user_data = UserRepository.get_user(tenant_context['user_id'])
            
            # Update last login timestamp
            try:
                UserRepository.update_last_login(tenant_context['user_id'])
                # Refresh user data to get updated last_login_at
                user_data = UserRepository.get_user(tenant_context['user_id'])
            except Exception as e:
                # Don't fail the request if last login update fails
                print(f"[WARNING] Failed to update last login: {str(e)}")
            
            # Get tenant information
            tenant_data = TenantRepository.get_tenant(tenant_context['tenant_id'])
            
        except NotFoundError:
            # If user doesn't exist in our database, create minimal response from JWT
            response_data = {
                'user_id': tenant_context['user_id'],
                'email': tenant_context.get('email'),
                'name': tenant_context.get('name'),
                'role': tenant_context.get('role', 'USER'),
                'tenant_id': tenant_context['tenant_id'],
                'tenant_name': tenant_context.get('tenant_name'),
                'status': 'ACTIVE',
                'permissions': tenant_context.get('permissions', [])
            }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response_data)
            }
        
        # Return user information from database
        response_data = {
            'user_id': user_data['user_id'],
            'email': user_data['email'],
            'name': user_data['name'],
            'role': user_data['role'],
            'tenant_id': user_data['tenant_id'],
            'tenant_name': tenant_data.get('tenant_name'),
            'created_at': user_data.get('created_at'),
            'last_login_at': user_data.get('last_login_at'),
            'permissions': tenant_context.get('permissions', [])
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(response_data))
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Failed to get user info: {str(e)}'})
        }


@require_tenant_permission('manage_users')
def delete_tenant_user(event, context=None):
    """
    Delete a user from the current tenant (Admin only)
    
    DELETE /v2/tenant/users/{user_id}
    """
    try:
        tenant_context = get_tenant_context(event)
        user_id = event.get('pathParameters', {}).get('user_id')
        
        if not user_id:
            raise BadRequestError("user_id is required")
        
        # Get user info before deletion (we need email for Cognito)
        user = UserRepository.get_user(user_id)
        if user['tenant_id'] != tenant_context['tenant_id']:
            raise NotFoundError("User not found in this tenant")
        
        # Don't allow users to delete themselves
        if user_id == tenant_context['user_id']:
            raise BadRequestError("Cannot delete your own account")
        
        # Delete user from Cognito first
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        
        try:
            cognito_client.admin_delete_user(
                UserPoolId=user_pool_id,
                Username=user['email']
            )
            print(f"[DEBUG] Deleted Cognito user: {user['email']}")
        except cognito_client.exceptions.UserNotFoundException:
            # User already deleted from Cognito, that's ok
            print(f"[DEBUG] User {user['email']} not found in Cognito (already deleted?)")
        except Exception as e:
            print(f"[ERROR] Failed to delete Cognito user: {str(e)}")
            # Don't fail the request if Cognito deletion fails
            pass
        
        # Delete user from DynamoDB
        UserRepository.delete_user(user_id)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'User {user["email"]} deleted successfully',
                'deleted_user_id': user_id
            })
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


lambda_handlers = {
    'get_tenant': get_tenant,
    'create_tenant': create_tenant,
    'update_tenant': update_tenant,
    'get_tenant_users': get_tenant_users,
    'create_tenant_user': create_tenant_user,
    'update_user_role': update_user_role,
    'delete_tenant_user': delete_tenant_user,
    'get_config': get_config,
    'get_current_user': get_current_user
}
