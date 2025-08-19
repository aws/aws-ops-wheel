#  Wheel Group Management APIs for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import os
import boto3
from typing import Dict, Any
from base import BadRequestError, NotFoundError
from wheel_group_middleware import wheel_group_middleware, require_auth, require_wheel_group_permission, get_wheel_group_context
from utils_v2 import (
    WheelGroupRepository, UserRepository, WheelRepository, ParticipantsTable, 
    check_string, get_uuid, get_utc_timestamp, decimal_to_float
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

DEFAULT_WHEEL_GROUP_QUOTAS = {
    'max_wheels': 50,
    'max_participants_per_wheel': 100,
    'max_multi_select': 10
}

DEFAULT_WHEEL_GROUP_SETTINGS = {
    'allow_rigging': True,
    'default_participant_weight': 1.0,  # Will be converted to Decimal
    'theme': 'default',
    'timezone': 'UTC'
}

VALIDATION_MESSAGES = {
    'WHEEL_GROUP_NAME_REQUIRED': "wheel_group_name is required and must be a non-empty string",
    'ADMIN_EMAIL_REQUIRED': "admin_user.email is required",
    'USER_HAS_WHEEL_GROUP': "User is already associated with a wheel group",
    'EMAIL_REQUIRED': "email is required and must be a non-empty string",
    'USERNAME_REQUIRED': "username is required and must be a non-empty string",
    'INVALID_ROLE': f"role must be one of: {', '.join(VALID_ROLES)}",
    'USERNAME_TAKEN': "Username '{}' is already taken in this wheel group",
    'USER_ID_REQUIRED': "user_id is required",
    'USER_NOT_IN_WHEEL_GROUP': "User not found in this wheel group",
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


def create_cognito_user(email: str, username: str, wheel_group_id: str) -> str:
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
                {'Name': 'custom:wheel_group_id', 'Value': wheel_group_id}
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
def create_wheel_group(event, context=None):
    """
    Create a new wheel group (open registration)
    
    POST /v2/wheel-group
    
    {
      "wheel_group_name": "My Company",
      "admin_user": {
        "email": "admin@mycompany.com",
        "name": "Admin User"
      }
    }
    """
    body = event.get('body', {})
    
    # Validate required fields
    validate_required_string(body.get('wheel_group_name'), 'wheel_group_name')
    
    admin_user = body.get('admin_user', {})
    validate_required_string(admin_user.get('email'), 'admin_user.email')
    
    # Get current user context (they will become the admin)
    user_context = get_wheel_group_context(event)
    user_id = user_context['user_id']
    
    # Check if user is already associated with a wheel group
    try:
        existing_user = UserRepository.get_user(user_id)
        if existing_user.get('wheel_group_id'):
            raise BadRequestError(VALIDATION_MESSAGES['USER_HAS_WHEEL_GROUP'])
    except NotFoundError:
        # User doesn't exist in our system yet, which is fine
        pass
    
    from decimal import Decimal
    
    # Create wheel group with default values
    wheel_group_data = {
        'wheel_group_name': body['wheel_group_name'],
        'quotas': body.get('quotas', DEFAULT_WHEEL_GROUP_QUOTAS),
        'settings': body.get('settings', {
            **DEFAULT_WHEEL_GROUP_SETTINGS,
            'default_participant_weight': Decimal(str(DEFAULT_WHEEL_GROUP_SETTINGS['default_participant_weight']))
        })
    }
    
    wheel_group = WheelGroupRepository.create_wheel_group(wheel_group_data)
    
    # Create/update user as admin
    user_data = {
        'user_id': user_id,
        'wheel_group_id': wheel_group['wheel_group_id'],
        'email': admin_user['email'],
        'name': admin_user.get('name', admin_user['email']),
        'role': USER_ROLES['ADMIN']
    }
    
    try:
        # Update existing user
        UserRepository.update_user(user_id, {
            'wheel_group_id': wheel_group['wheel_group_id'],
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
                {'Name': 'custom:wheel_group_id', 'Value': wheel_group['wheel_group_id']}
            ]
        )
    except Exception as e:
        # Log error but don't fail the request
        print(f"[WARNING] Failed to update Cognito attributes: {str(e)}")
    
    return create_api_response(HTTP_STATUS_CODES['CREATED'], wheel_group)


@require_wheel_group_permission('view_wheels')
def get_wheel_group(event, context=None):
    """
    Get current wheel group information
    
    GET /v2/wheel-group
    """
    try:
        wheel_group_context = get_wheel_group_context(event)
        wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_context['wheel_group_id'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(wheel_group))
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


@require_wheel_group_permission('manage_wheel_group')
def update_wheel_group(event, context=None):
    """
    Update wheel group settings (Admin only)
    
    PUT /v2/wheel-group
    
    {
      "wheel_group_name": "Updated Name",
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
        wheel_group_context = get_wheel_group_context(event)
        body = event.get('body', {})
        
        # Validate updates
        updates = {}
        
        if 'wheel_group_name' in body:
            if not check_string(body['wheel_group_name']):
                raise BadRequestError("wheel_group_name must be a non-empty string")
            updates['wheel_group_name'] = body['wheel_group_name']
        
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
        
        # Update wheel group
        updated_wheel_group = WheelGroupRepository.update_wheel_group(wheel_group_context['wheel_group_id'], updates)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(updated_wheel_group))
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


@require_wheel_group_permission('manage_users')
def get_wheel_group_users(event, context=None):
    """
    Get all users in the current wheel group
    
    GET /v2/wheel-group/users
    """
    try:
        wheel_group_context = get_wheel_group_context(event)
        users = UserRepository.get_users_by_wheel_group(wheel_group_context['wheel_group_id'])
        
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


@require_wheel_group_permission('manage_users')
def create_wheel_group_user(event, context=None):
    """
    Create a new user in the current wheel group (Admin only)
    
    POST /v2/wheel-group/users
    
    {
      "email": "newuser@test.com",
      "name": "New User",
      "role": "USER"
    }
    """
    try:
        print(f"[DEBUG] create_wheel_group_user called with event: {json.dumps(event)}")
        wheel_group_context = get_wheel_group_context(event)
        print(f"[DEBUG] wheel_group_context: {wheel_group_context}")
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
        
        # Check if username is unique within the wheel group
        try:
            existing_users = UserRepository.get_users_by_wheel_group(wheel_group_context['wheel_group_id'])
            for existing_user in existing_users:
                if existing_user.get('name', '').lower() == body['username'].lower():
                    raise BadRequestError(f"Username '{body['username']}' is already taken in this wheel group")
        except Exception as e:
            # If we can't check existing users, log the error but don't fail
            print(f"[WARNING] Could not check existing usernames: {str(e)}")
        
        # Create user in Cognito first to get the Cognito sub (user ID)
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        
        try:
            # Create user in Cognito with username as the login identifier
            cognito_response = cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=body['username'],  # Use username as Cognito username
                UserAttributes=[
                    {'Name': 'email', 'Value': body['email']},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'name', 'Value': body['username']},
                    {'Name': 'custom:wheel_group_id', 'Value': wheel_group_context['wheel_group_id']},
                    {'Name': 'custom:deployment_admin', 'Value': 'false'}
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
            raise BadRequestError(f"A user with username {body['username']} already exists")
        except Exception as e:
            print(f"[ERROR] Failed to create Cognito user: {str(e)}")
            raise BadRequestError(f"Failed to create user in authentication system: {str(e)}")
        
        # Create user data using the Cognito user ID as the DynamoDB user_id
        user_data = {
            'user_id': cognito_user_id,  # Use Cognito sub as DynamoDB user_id
            'wheel_group_id': wheel_group_context['wheel_group_id'],
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


@require_wheel_group_permission('manage_users')
def update_user_role(event, context=None):
    """
    Update a user's role within the wheel group (Admin only)
    
    PUT /v2/wheel-group/users/{user_id}/role
    
    {
      "role": "WHEEL_ADMIN"
    }
    """
    try:
        wheel_group_context = get_wheel_group_context(event)
        user_id = event.get('pathParameters', {}).get('user_id')
        body = event.get('body', {})
        
        if not user_id:
            raise BadRequestError("user_id is required")
        
        new_role = body.get('role')
        valid_roles = ['ADMIN', 'WHEEL_ADMIN', 'USER']
        
        if new_role not in valid_roles:
            raise BadRequestError(f"role must be one of: {', '.join(valid_roles)}")
        
        # Verify user belongs to this wheel group
        user = UserRepository.get_user(user_id)
        if user['wheel_group_id'] != wheel_group_context['wheel_group_id']:
            raise NotFoundError("User not found in this wheel group")
        
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
            'MULTI_WHEEL_GROUP_ENABLED': True,
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
    """Get current user information including role and wheel group details"""
    try:
        # User info is already validated and attached by wheel_group_middleware
        wheel_group_context = get_wheel_group_context(event)
        
        if not wheel_group_context:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'User context not found'})
            }
        
        # Check if this is a deployment admin user
        is_deployment_admin = wheel_group_context.get('deployment_admin', False)
        
        if is_deployment_admin:
            # Deployment admin users don't exist in DynamoDB Users table
            # Return user info directly from JWT/Cognito
            response_data = {
                'user_id': wheel_group_context['user_id'],
                'email': wheel_group_context.get('email'),
                'name': wheel_group_context.get('name', wheel_group_context.get('email')),
                'role': 'DEPLOYMENT_ADMIN',
                'wheel_group_id': None,
                'wheel_group_name': None,
                'deployment_admin': True,
                'permissions': wheel_group_context.get('permissions', []),
                'status': 'ACTIVE'
            }
            
            print(f"[DEBUG] Returning deployment admin user info: {response_data}")
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response_data)
            }
        
        # Handle users without wheel group associations
        if not wheel_group_context['wheel_group_id']:
            response_data = {
                'user_id': wheel_group_context['user_id'],
                'email': wheel_group_context.get('email'),
                'name': wheel_group_context.get('name'),
                'role': wheel_group_context.get('role', 'USER'),
                'wheel_group_id': None,
                'wheel_group_name': None,
                'permissions': wheel_group_context.get('permissions', []),
                'needs_wheel_group_association': True
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
            user_data = UserRepository.get_user(wheel_group_context['user_id'])
            
            # Update last login timestamp
            try:
                UserRepository.update_last_login(wheel_group_context['user_id'])
                # Refresh user data to get updated last_login_at
                user_data = UserRepository.get_user(wheel_group_context['user_id'])
            except Exception as e:
                # Don't fail the request if last login update fails
                print(f"[WARNING] Failed to update last login: {str(e)}")
            
            # Get wheel group information
            wheel_group_data = WheelGroupRepository.get_wheel_group(wheel_group_context['wheel_group_id'])
            
        except NotFoundError:
            # If user doesn't exist in our database, create minimal response from JWT
            response_data = {
                'user_id': wheel_group_context['user_id'],
                'email': wheel_group_context.get('email'),
                'name': wheel_group_context.get('name'),
                'role': wheel_group_context.get('role', 'USER'),
                'wheel_group_id': wheel_group_context['wheel_group_id'],
                'wheel_group_name': wheel_group_context.get('wheel_group_name'),
                'status': 'ACTIVE',
                'permissions': wheel_group_context.get('permissions', [])
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
            'wheel_group_id': user_data['wheel_group_id'],
            'wheel_group_name': wheel_group_data.get('wheel_group_name'),
            'created_at': user_data.get('created_at'),
            'last_login_at': user_data.get('last_login_at'),
            'permissions': wheel_group_context.get('permissions', [])
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


@require_wheel_group_permission('manage_users')
def delete_wheel_group_user(event, context=None):
    """
    Delete a user from the current wheel group (Admin only)
    
    DELETE /v2/wheel-group/users/{user_id}
    """
    try:
        wheel_group_context = get_wheel_group_context(event)
        user_id = event.get('pathParameters', {}).get('user_id')
        
        if not user_id:
            raise BadRequestError("user_id is required")
        
        # Get user info before deletion (we need email for Cognito)
        user = UserRepository.get_user(user_id)
        if user['wheel_group_id'] != wheel_group_context['wheel_group_id']:
            raise NotFoundError("User not found in this wheel group")
        
        # Don't allow users to delete themselves
        if user_id == wheel_group_context['user_id']:
            raise BadRequestError("Cannot delete your own account")
        
        # Delete user from Cognito first
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        
        try:
            cognito_client.admin_delete_user(
                UserPoolId=user_pool_id,
                Username=user['name']  # Use username (stored in 'name' field) for Cognito
            )
            print(f"[DEBUG] Deleted Cognito user: {user['name']}")
        except cognito_client.exceptions.UserNotFoundException:
            # User already deleted from Cognito, that's ok
            print(f"[DEBUG] User {user['name']} not found in Cognito (already deleted?)")
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


@handle_api_exceptions
def create_wheel_group_public(event, context=None):
    """
    Create a new wheel group (public registration without authentication)
    
    POST /v2/wheel-group/create-public
    
    {
      "wheel_group_name": "My Company",
      "admin_user": {
        "username": "admin",
        "email": "admin@mycompany.com",
        "password": "SecurePassword123!"
      }
    }
    """
    body = event.get('body', {})
    
    # Validate required fields
    validate_required_string(body.get('wheel_group_name'), 'wheel_group_name')
    
    admin_user = body.get('admin_user', {})
    validate_required_string(admin_user.get('username'), 'admin_user.username')
    validate_required_string(admin_user.get('email'), 'admin_user.email')
    validate_required_string(admin_user.get('password'), 'admin_user.password')
    
    # Validate password strength
    if len(admin_user['password']) < 8:
        raise BadRequestError("Password must be at least 8 characters long")
    
    from decimal import Decimal
    
    # Create wheel group with default values
    wheel_group_data = {
        'wheel_group_name': body['wheel_group_name'],
        'quotas': body.get('quotas', DEFAULT_WHEEL_GROUP_QUOTAS),
        'settings': body.get('settings', {
            **DEFAULT_WHEEL_GROUP_SETTINGS,
            'default_participant_weight': Decimal(str(DEFAULT_WHEEL_GROUP_SETTINGS['default_participant_weight']))
        })
    }
    
    wheel_group = WheelGroupRepository.create_wheel_group(wheel_group_data)
    
    # Create user in Cognito first to get the Cognito user ID
    cognito_client = boto3.client('cognito-idp')
    user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
    
    try:
        # Create user in Cognito with username as login identifier
        cognito_response = cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=admin_user['username'],  # Use username as Cognito username
                UserAttributes=[
                    {'Name': 'email', 'Value': admin_user['email']},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'name', 'Value': admin_user['username']},
                    {'Name': 'custom:wheel_group_id', 'Value': wheel_group['wheel_group_id']},
                    {'Name': 'custom:deployment_admin', 'Value': 'false'}
                ],
            TemporaryPassword=admin_user['password'],
            MessageAction=COGNITO_CONFIG['MESSAGE_ACTION']
        )
        
        # Set permanent password immediately
        cognito_client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=admin_user['username'],
            Password=admin_user['password'],
            Permanent=True
        )
        
        # Extract Cognito user ID (sub)
        cognito_user_id = None
        for attr in cognito_response['User']['Attributes']:
            if attr['Name'] == 'sub':
                cognito_user_id = attr['Value']
                break
        
        if not cognito_user_id:
            raise Exception("Failed to get Cognito user ID from response")
            
    except cognito_client.exceptions.UsernameExistsException:
        # Clean up wheel group if user creation fails
        try:
            WheelGroupRepository.delete_wheel_group(wheel_group['wheel_group_id'])
        except:
            pass
        raise BadRequestError(f"A user with username {admin_user['username']} already exists")
    except Exception as e:
        # Clean up wheel group if user creation fails
        try:
            WheelGroupRepository.delete_wheel_group(wheel_group['wheel_group_id'])
        except:
            pass
        raise BadRequestError(f"Failed to create user in authentication system: {str(e)}")
    
    # Create user record in DynamoDB
    user_data = {
        'user_id': cognito_user_id,
        'wheel_group_id': wheel_group['wheel_group_id'],
        'email': admin_user['email'],
        'name': admin_user['username'],
        'role': USER_ROLES['ADMIN']
    }
    
    try:
        created_user = UserRepository.create_user(user_data)
    except Exception as e:
        # Clean up Cognito and wheel group if DynamoDB user creation fails
        try:
            cognito_client.admin_delete_user(
                UserPoolId=user_pool_id,
                Username=admin_user['username']
            )
            WheelGroupRepository.delete_wheel_group(wheel_group['wheel_group_id'])
        except:
            pass
        raise BadRequestError(f"Failed to create user record: {str(e)}")
    
    # Return success response with wheel group and user info
    response_data = {
        'wheel_group': wheel_group,
        'admin_user': {
            'user_id': created_user['user_id'],
            'email': created_user['email'],
            'name': created_user['name'],
            'role': created_user['role']
        },
        'message': f'Wheel group "{wheel_group["wheel_group_name"]}" created successfully with admin user "{admin_user["username"]}"'
    }
    
    return create_api_response(HTTP_STATUS_CODES['CREATED'], response_data)


@require_wheel_group_permission('manage_wheel_group')
def delete_wheel_group_recursive(event, context=None):
    """
    Recursively delete entire wheel group and all associated data (Admin only)
    
    DELETE /v2/wheel-group/delete-recursive
    
    This will delete:
    - All users in the wheel group (from both DynamoDB and Cognito)
    - All wheels in the wheel group
    - All participants in the wheel group
    - The wheel group itself
    
    WARNING: This is a destructive operation that cannot be undone!
    """
    try:
        wheel_group_context = get_wheel_group_context(event)
        wheel_group_id = wheel_group_context['wheel_group_id']
        current_user_id = wheel_group_context['user_id']
        
        print(f"[DEBUG] Starting recursive deletion of wheel group: {wheel_group_id}")
        
        # Get wheel group info for logging
        try:
            wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
            wheel_group_name = wheel_group.get('wheel_group_name', 'Unknown')
            print(f"[DEBUG] Deleting wheel group '{wheel_group_name}' (ID: {wheel_group_id})")
        except Exception as e:
            print(f"[WARNING] Could not get wheel group info: {str(e)}")
            wheel_group_name = 'Unknown'
        
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        
        # Step 1: Delete all wheels for this wheel group (this will also delete their participants)
        print(f"[DEBUG] Step 1: Deleting wheels for wheel group {wheel_group_id}")
        try:
            wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
            print(f"[DEBUG] Found {len(wheels)} wheels to delete")
            
            for wheel in wheels:
                try:
                    WheelRepository.delete_wheel(wheel_group_id, wheel['wheel_id'])
                    print(f"[DEBUG] Deleted wheel: {wheel['wheel_id']}")
                except Exception as e:
                    print(f"[ERROR] Failed to delete wheel {wheel['wheel_id']}: {str(e)}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to delete wheels: {str(e)}")
        
        # Step 2: Clean up any remaining participants (in case of orphaned records)
        print(f"[DEBUG] Step 2: Cleaning up any remaining participants for wheel group {wheel_group_id}")
        try:
            # Scan participants table for any remaining records with this wheel_group_id
            # Since participant keys use wheel_group_wheel_id format, we need to scan
            remaining_participants = []
            for item in ParticipantsTable.iter_scan():
                if item.get('wheel_group_wheel_id', '').startswith(f"{wheel_group_id}#"):
                    remaining_participants.append(item)
            
            print(f"[DEBUG] Found {len(remaining_participants)} remaining participants to clean up")
            
            for participant in remaining_participants:
                try:
                    ParticipantsTable.delete_item(Key={
                        'wheel_group_wheel_id': participant['wheel_group_wheel_id'],
                        'participant_id': participant['participant_id']
                    })
                    print(f"[DEBUG] Cleaned up participant: {participant['participant_id']}")
                except Exception as e:
                    print(f"[ERROR] Failed to cleanup participant {participant['participant_id']}: {str(e)}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to cleanup participants: {str(e)}")
        
        # Step 3: Delete all users for this wheel group (both DynamoDB and Cognito)
        print(f"[DEBUG] Step 3: Deleting users for wheel group {wheel_group_id}")
        try:
            users = UserRepository.get_users_by_wheel_group(wheel_group_id)
            print(f"[DEBUG] Found {len(users)} users to delete")
            
            for user in users:
                user_id = user['user_id']
                username = user.get('name', user.get('email', 'unknown'))
                
                # Delete from Cognito first
                try:
                    cognito_client.admin_delete_user(
                        UserPoolId=user_pool_id,
                        Username=username  # Use username (stored in 'name' field) for Cognito
                    )
                    print(f"[DEBUG] Deleted Cognito user: {username}")
                except cognito_client.exceptions.UserNotFoundException:
                    print(f"[DEBUG] User {username} not found in Cognito (already deleted?)")
                except Exception as e:
                    print(f"[ERROR] Failed to delete Cognito user {username}: {str(e)}")
                
                # Delete from DynamoDB
                try:
                    UserRepository.delete_user(user_id)
                    print(f"[DEBUG] Deleted DynamoDB user: {user_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to delete DynamoDB user {user_id}: {str(e)}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to delete users: {str(e)}")
        
        # Step 4: Finally delete the wheel group itself
        print(f"[DEBUG] Step 4: Deleting wheel group {wheel_group_id}")
        try:
            WheelGroupRepository.delete_wheel_group(wheel_group_id)
            print(f"[DEBUG] Successfully deleted wheel group: {wheel_group_id}")
        except Exception as e:
            print(f"[ERROR] Failed to delete wheel group {wheel_group_id}: {str(e)}")
            raise BadRequestError(f"Failed to delete wheel group: {str(e)}")
        
        print(f"[DEBUG] Recursive deletion completed for wheel group: {wheel_group_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'Wheel group "{wheel_group_name}" and all associated data has been permanently deleted',
                'deleted_wheel_group_id': wheel_group_id,
                'deleted_wheel_group_name': wheel_group_name
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
        print(f"[ERROR] Recursive wheel group deletion failed: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Failed to delete wheel group: {str(e)}'})
        }


lambda_handlers = {
    'get_wheel_group': get_wheel_group,
    'create_wheel_group': create_wheel_group,
    'create_wheel_group_public': create_wheel_group_public,
    'update_wheel_group': update_wheel_group,
    'get_wheel_group_users': get_wheel_group_users,
    'create_wheel_group_user': create_wheel_group_user,
    'update_user_role': update_user_role,
    'delete_wheel_group_user': delete_wheel_group_user,
    'delete_wheel_group_recursive': delete_wheel_group_recursive,
    'get_config': get_config,
    'get_current_user': get_current_user
}
