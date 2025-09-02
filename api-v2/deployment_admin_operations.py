"""
AWS Ops Wheel v2 - Admin Operations
Handles deployment admin operations like listing and deleting wheel groups
"""

import json
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime
import logging

# Import Cognito exceptions
try:
    from botocore.exceptions import ClientError
    # Try to get Cognito-specific exceptions
    cognito_client_temp = boto3.client('cognito-idp')
    UserNotFoundException = cognito_client_temp.exceptions.UserNotFoundException
except Exception:
    # Fallback if exceptions can't be imported (e.g., in test environment)
    class UserNotFoundException(Exception):
        pass

# Import utilities and repositories
from utils_v2 import (
    WheelGroupsTable, UsersTable, WheelsTable, ParticipantsTable,
    WheelGroupRepository, UserRepository, WheelRepository, ParticipantRepository,
    create_wheel_group_wheel_id, decimal_to_float
)

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cognito_client = boto3.client('cognito-idp')

# Constants
STATUS_CODES = {
    'OK': 200,
    'CREATED': 201,
    'BAD_REQUEST': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'CONFLICT': 409,
    'INTERNAL_ERROR': 500
}

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
}

USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')


def create_response(status_code, body, additional_headers=None):
    """Create standardized API response with CORS headers"""
    headers = CORS_HEADERS.copy()
    if additional_headers:
        headers.update(additional_headers)
    
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(body) if isinstance(body, (dict, list)) else body
    }


def check_deployment_admin_permission(event):
    """
    Check if the authenticated user is a deployment admin
    Returns True if authorized, False otherwise
    """
    try:
        
        # Get user info from authenticated event
        user_info = event.get('user_info', {})
        wheel_group_context = event.get('wheel_group_context', {})
        
        # Also check API Gateway authorizer context
        authorizer_context = event.get('requestContext', {}).get('authorizer', {})
        
        
        # Check all locations for deployment admin flag
        deployment_admin = (
            user_info.get('deployment_admin', False) or 
            wheel_group_context.get('deployment_admin', False) or
            str(authorizer_context.get('deployment_admin', '')).lower() == 'true'  # Handle both 'True' and 'true'
        )

        
        if not deployment_admin:
            logger.warning(f"User attempted admin operation without deployment admin privileges")
            logger.warning(f"Available user_info keys: {list(user_info.keys())}")
            logger.warning(f"Available wheel_group_context keys: {list(wheel_group_context.keys())}")
            logger.warning(f"Available authorizer_context keys: {list(authorizer_context.keys())}")
            return False

        return True
        
    except Exception as e:
        logger.error(f"Error checking deployment admin permission: {str(e)}")
        return False


def get_wheel_group_statistics(wheel_group_id):
    """
    Get comprehensive statistics for a specific wheel group including actual last updated timestamp
    Returns user count, wheel count, created at, and calculated last_updated timestamp
    """
    # Validate input - defensive check for None values
    if not wheel_group_id or not isinstance(wheel_group_id, str) or len(wheel_group_id.strip()) < 10:
        return {
            'user_count': 0,
            'wheel_count': 0,
            'created_at': None,
            'last_updated': None
        }
    
    wheel_group_id = wheel_group_id.strip()
    
    # Get the wheel group info - if this fails, return default stats
    try:
        wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
    except:
        return {
            'user_count': 0,
            'wheel_count': 0,
            'created_at': None,
            'last_updated': None
        }
    
    # Initialize timestamps list with wheel group created_at as fallback
    timestamps = [wheel_group.get('created_at')]
    
    # Get users and their max updated_at timestamp (graceful failure)
    user_count = 0
    try:
        users = UserRepository.get_users_by_wheel_group(wheel_group_id)
        user_count = len(users)
        
        # Find max updated_at from users
        user_timestamps = [user.get('updated_at') for user in users if user.get('updated_at')]
        if user_timestamps:
            timestamps.append(max(user_timestamps))
    except Exception as e:
        logger.warning(f"Error getting users for statistics: {str(e)}")
    
    # Get wheels and their max last_spun_at timestamp (graceful failure)
    wheel_count = 0
    try:
        wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
        wheel_count = len(wheels)
        
        # Find max last_spun_at from wheels
        wheel_timestamps = [wheel.get('last_spun_at') for wheel in wheels if wheel.get('last_spun_at')]
        if wheel_timestamps:
            timestamps.append(max(wheel_timestamps))
        
        # Get participants from all wheels and find max last_selected_at and updated_at (graceful failure)
        try:
            all_participant_timestamps = []
            for wheel in wheels:
                try:
                    participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel['wheel_id'])
                    
                    # Collect timestamps from participants
                    for p in participants:
                        if p.get('last_selected_at'):
                            all_participant_timestamps.append(p['last_selected_at'])
                        if p.get('updated_at'):
                            all_participant_timestamps.append(p['updated_at'])
                except:
                    continue  # Skip this wheel's participants if error
            
            if all_participant_timestamps:
                timestamps.append(max(all_participant_timestamps))
        except:
            pass  # Continue without participant timestamps
            
    except Exception as e:
        logger.warning(f"Error getting wheels for statistics: {str(e)}")
    
    # Filter out None values and find the maximum timestamp
    valid_timestamps = [ts for ts in timestamps if ts is not None]
    last_updated = max(valid_timestamps) if valid_timestamps else wheel_group.get('created_at')
    
    return {
        'user_count': user_count,
        'wheel_count': wheel_count,
        'created_at': wheel_group.get('created_at'),
        'last_updated': last_updated
    }


def list_all_wheel_groups(event, context):
    """
    List all wheel groups in the system with statistics
    Only accessible to deployment admin
    """
    try:
        # Check deployment admin permission
        if not check_deployment_admin_permission(event):
            return create_response(STATUS_CODES['FORBIDDEN'], {
                'error': 'Access denied. Deployment admin privileges required.'
            })
        
        # Get all wheel groups from database
        wheel_groups_response = []
        
        # Get all wheel groups using repository method
        wheel_groups = WheelGroupRepository.list_all_wheel_groups()
        
        for wheel_group in wheel_groups:
            wheel_group_id = wheel_group.get('wheel_group_id')
            
            # Validate wheel_group_id - skip items with null/invalid keys
            if not wheel_group_id or not isinstance(wheel_group_id, str) or len(wheel_group_id.strip()) < 10:
                continue
            
            wheel_group_id = wheel_group_id.strip()
            
            # Get comprehensive statistics for this wheel group
            stats = get_wheel_group_statistics(wheel_group_id)
            
            # Build response object
            response_item = {
                'wheel_group_id': wheel_group_id,
                'wheel_group_name': wheel_group.get('wheel_group_name', 'Unknown'),
                'user_count': stats['user_count'],
                'wheel_count': stats['wheel_count'],
                'created_at': stats['created_at'],
                'last_updated': stats['last_updated']
            }
            
            wheel_groups_response.append(response_item)
        
        return create_response(STATUS_CODES['OK'], {
            'wheel_groups': wheel_groups_response
        })
        
    except Exception as e:
        logger.error(f"Error listing wheel groups: {str(e)}")
        return create_response(STATUS_CODES['INTERNAL_ERROR'], {
            'error': f'Internal server error: {str(e)}'
        })


def delete_wheel_group(event, context):
    """
    Delete a wheel group and all associated data
    Only accessible to deployment admin
    """
    logger.info("Admin request: Delete wheel group")
    logger.info(f"EVENT RECEIVED: {json.dumps(event, default=str)}")
    
    try:
        # Check deployment admin permission
        if not check_deployment_admin_permission(event):
            logger.error("Permission check failed - not a deployment admin")
            return create_response(STATUS_CODES['FORBIDDEN'], {
                'error': 'Access denied. Deployment admin privileges required.'
            })
        
        # Extract wheel group ID from path parameters
        path_params = event.get('pathParameters', {})
        wheel_group_id = path_params.get('wheel_group_id')
        
        logger.info(f"EXTRACTED WHEEL GROUP ID: {wheel_group_id}")
        
        if not wheel_group_id:
            logger.error("No wheel group ID provided in path parameters")
            return create_response(STATUS_CODES['BAD_REQUEST'], {
                'error': 'wheel_group_id is required in path'
            })
        
        # Get wheel group info for logging before deletion
        # Also verify that the wheel group exists - fail if it doesn't
        try:
            wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
            wheel_group_name = wheel_group.get('wheel_group_name', 'Unknown')
            logger.info(f"Deleting wheel group '{wheel_group_name}' (ID: {wheel_group_id})")
        except Exception as e:
            logger.error(f"Wheel group {wheel_group_id} not found: {str(e)}")
            return create_response(STATUS_CODES['INTERNAL_ERROR'], {
                'error': f'Wheel group {wheel_group_id} not found or could not be accessed: {str(e)}'
            })
        
        # Perform the actual deletion
        logger.info(f"Starting recursive deletion of wheel group: {wheel_group_id}")
        
        # Step 1: Delete all wheels for this wheel group (this will also delete their participants)
        logger.info(f"Step 1: Deleting wheels for wheel group {wheel_group_id}")
        try:
            wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
            logger.info(f"Found {len(wheels)} wheels to delete")
            
            for wheel in wheels:
                try:
                    # Delete participants first
                    participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel['wheel_id'])
                    for participant in participants:
                        ParticipantRepository.delete_participant(wheel_group_id, wheel['wheel_id'], participant['participant_id'])
                        logger.info(f"Deleted participant: {participant['participant_id']}")
                    
                    # Delete the wheel
                    WheelRepository.delete_wheel(wheel_group_id, wheel['wheel_id'])
                    logger.info(f"Deleted wheel: {wheel['wheel_id']}")
                except Exception as e:
                    logger.error(f"Failed to delete wheel {wheel['wheel_id']}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Failed to delete wheels: {str(e)}")
        
        # Step 2: Delete all users for this wheel group (both DynamoDB and Cognito)
        logger.info(f"Step 2: Deleting users for wheel group {wheel_group_id}")
        try:
            users = UserRepository.get_users_by_wheel_group(wheel_group_id)
            logger.info(f"Found {len(users)} users to delete")
            
            for user in users:
                user_id = user['user_id']
                username = user.get('name', user.get('email', 'unknown'))
                
                # Delete from Cognito first
                try:
                    cognito_client.admin_delete_user(
                        UserPoolId=USER_POOL_ID,
                        Username=username  # Use username (stored in 'name' field) for Cognito
                    )
                    logger.info(f"Deleted Cognito user: {username}")
                except UserNotFoundException:
                    logger.info(f"User {username} not found in Cognito (already deleted?)")
                except Exception as e:
                    logger.error(f"Failed to delete Cognito user {username}: {str(e)}")
                
                # Delete from DynamoDB
                try:
                    UserRepository.delete_user(user_id)
                    logger.info(f"Deleted DynamoDB user: {user_id}")
                except Exception as e:
                    logger.error(f"Failed to delete DynamoDB user {user_id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Failed to delete users: {str(e)}")
        
        # Step 3: Clean up any remaining participants (in case of orphaned records)
        logger.info(f"Step 3: Cleaning up any remaining participants for wheel group {wheel_group_id}")
        try:
            # Scan participants table for any remaining records with this wheel_group_id
            # Since participant keys use wheel_group_wheel_id format, we need to scan
            remaining_participants = []
            for item in ParticipantsTable.iter_scan():
                if item.get('wheel_group_wheel_id', '').startswith(f"{wheel_group_id}#"):
                    remaining_participants.append(item)
            
            logger.info(f"Found {len(remaining_participants)} remaining participants to clean up")
            
            for participant in remaining_participants:
                try:
                    ParticipantsTable.delete_item(Key={
                        'wheel_group_wheel_id': participant['wheel_group_wheel_id'],
                        'participant_id': participant['participant_id']
                    })
                    logger.info(f"Cleaned up participant: {participant['participant_id']}")
                except Exception as e:
                    logger.error(f"Failed to cleanup participant {participant['participant_id']}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup participants: {str(e)}")
        
        # Step 4: Finally delete the wheel group itself
        logger.info(f"Step 4: Deleting wheel group {wheel_group_id}")
        try:
            WheelGroupRepository.delete_wheel_group(wheel_group_id)
            logger.info(f"Successfully deleted wheel group: {wheel_group_id}")
        except Exception as e:
            logger.error(f"Failed to delete wheel group {wheel_group_id}: {str(e)}")
            return create_response(STATUS_CODES['INTERNAL_ERROR'], {
                'error': f'Failed to delete wheel group: {str(e)}'
            })
        
        logger.info(f"Recursive deletion completed for wheel group: {wheel_group_id}")
        
        return create_response(STATUS_CODES['OK'], {
            'message': f'Wheel group "{wheel_group_name}" and all associated data has been permanently deleted',
            'deleted_wheel_group_id': wheel_group_id,
            'deleted_wheel_group_name': wheel_group_name
        })
        
    except Exception as e:
        logger.error(f"Error in delete_wheel_group: {str(e)}")
        import traceback
        logger.error(f"Stacktrace: {traceback.format_exc()}")
        return create_response(STATUS_CODES['INTERNAL_ERROR'], {
            'error': f'Failed to delete wheel group: {str(e)}'
        })


# Lambda handlers dictionary for easy import
lambda_handlers = {
    'list_all_wheel_groups': list_all_wheel_groups,
    'delete_wheel_group': delete_wheel_group
}
