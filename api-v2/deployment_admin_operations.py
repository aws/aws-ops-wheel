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
        logger.info(f"[DEBUG] Checking deployment admin permission for event: {json.dumps(event, default=str)}")
        
        # Get user info from authenticated event
        user_info = event.get('user_info', {})
        wheel_group_context = event.get('wheel_group_context', {})
        
        # Also check API Gateway authorizer context
        authorizer_context = event.get('requestContext', {}).get('authorizer', {})
        
        logger.info(f"[DEBUG] user_info: {user_info}")
        logger.info(f"[DEBUG] wheel_group_context: {wheel_group_context}")
        logger.info(f"[DEBUG] authorizer_context: {authorizer_context}")
        
        # Check all locations for deployment admin flag
        deployment_admin = (
            user_info.get('deployment_admin', False) or 
            wheel_group_context.get('deployment_admin', False) or
            str(authorizer_context.get('deployment_admin', '')).lower() == 'true'  # Handle both 'True' and 'true'
        )
        
        logger.info(f"[DEBUG] deployment_admin flag: {deployment_admin}")
        
        if not deployment_admin:
            logger.warning(f"User attempted admin operation without deployment admin privileges")
            logger.warning(f"Available user_info keys: {list(user_info.keys())}")
            logger.warning(f"Available wheel_group_context keys: {list(wheel_group_context.keys())}")
            logger.warning(f"Available authorizer_context keys: {list(authorizer_context.keys())}")
            return False
            
        logger.info(f"[DEBUG] Deployment admin access granted")
        return True
        
    except Exception as e:
        logger.error(f"Error checking deployment admin permission: {str(e)}")
        return False


def get_wheel_group_statistics(wheel_group_id):
    """
    Get comprehensive statistics for a specific wheel group including actual last updated timestamp
    Returns user count, wheel count, created at, and calculated last_updated timestamp
    """
    try:
        logger.info(f"Getting statistics for wheel group: {wheel_group_id} (type: {type(wheel_group_id)})")
        logger.info(f"wheel_group_id repr: {repr(wheel_group_id)}")
        
        # Validate input - defensive check for None values
        if wheel_group_id is None:
            logger.error(f"get_wheel_group_statistics called with None wheel_group_id - returning default stats")
            return {
                'user_count': 0,
                'wheel_count': 0,
                'created_at': None,
                'last_updated': None
            }
        
        if not wheel_group_id or not isinstance(wheel_group_id, str):
            logger.error(f"Invalid wheel_group_id: {repr(wheel_group_id)} (type: {type(wheel_group_id)})")
            return {
                'user_count': 0,
                'wheel_count': 0,
                'created_at': None,
                'last_updated': None
            }
        
        # Debug the key that will be used for DynamoDB
        key_for_dynamodb = {'wheel_group_id': wheel_group_id}
        logger.info(f"DynamoDB key that will be used: {key_for_dynamodb}")
        
        # Get the wheel group info
        logger.info(f"Calling WheelGroupRepository.get_wheel_group with: {wheel_group_id}")
        wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
        logger.info(f"Successfully retrieved wheel group: {wheel_group.get('wheel_group_name', 'Unknown')}")
        
        # Initialize timestamps list with wheel group created_at as fallback
        timestamps = [wheel_group.get('created_at')]
        
        # Get users and their max updated_at timestamp
        users = UserRepository.get_users_by_wheel_group(wheel_group_id)
        user_count = len(users)
        
        # Find max updated_at from users
        user_timestamps = [user.get('updated_at') for user in users if user.get('updated_at')]
        if user_timestamps:
            max_user_timestamp = max(user_timestamps)
            timestamps.append(max_user_timestamp)
            logger.info(f"Max user updated_at: {max_user_timestamp}")
        
        # Get wheels and their max last_spun_at timestamp
        wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
        wheel_count = len(wheels)
        
        # Find max last_spun_at from wheels
        wheel_timestamps = [wheel.get('last_spun_at') for wheel in wheels if wheel.get('last_spun_at')]
        if wheel_timestamps:
            max_wheel_timestamp = max(wheel_timestamps)
            timestamps.append(max_wheel_timestamp)
            logger.info(f"Max wheel last_spun_at: {max_wheel_timestamp}")
        
        # Get participants from all wheels and find max last_selected_at and updated_at
        all_participant_timestamps = []
        for wheel in wheels:
            participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel['wheel_id'])
            
            # Collect last_selected_at timestamps
            participant_selected_timestamps = [p.get('last_selected_at') for p in participants if p.get('last_selected_at')]
            all_participant_timestamps.extend(participant_selected_timestamps)
            
            # Collect updated_at timestamps
            participant_updated_timestamps = [p.get('updated_at') for p in participants if p.get('updated_at')]
            all_participant_timestamps.extend(participant_updated_timestamps)
        
        if all_participant_timestamps:
            max_participant_timestamp = max(all_participant_timestamps)
            timestamps.append(max_participant_timestamp)
            logger.info(f"Max participant timestamp: {max_participant_timestamp}")
        
        # Filter out None values and find the maximum timestamp
        valid_timestamps = [ts for ts in timestamps if ts is not None]
        last_updated = max(valid_timestamps) if valid_timestamps else wheel_group.get('created_at')
        
        logger.info(f"Calculated last_updated for {wheel_group_id}: {last_updated}")
        
        return {
            'user_count': user_count,
            'wheel_count': wheel_count,
            'created_at': wheel_group.get('created_at'),
            'last_updated': last_updated
        }
        
    except Exception as e:
        logger.error(f"Error getting wheel group statistics for {wheel_group_id}: {str(e)}")
        import traceback
        logger.error(f"Stacktrace: {traceback.format_exc()}")
        # Return basic stats on error
        return {
            'user_count': 0,
            'wheel_count': 0,
            'created_at': None,
            'last_updated': None
        }


def list_all_wheel_groups(event, context):
    """
    List all wheel groups in the system with statistics
    Only accessible to deployment admin
    """
    logger.info("Admin request: List all wheel groups")
    logger.info(f"[DEBUG] Full event received: {json.dumps(event, default=str)}")
    
    try:
        # Check deployment admin permission
        if not check_deployment_admin_permission(event):
            return create_response(STATUS_CODES['FORBIDDEN'], {
                'error': 'Access denied. Deployment admin privileges required.'
            })
        
        logger.info("Deployment admin permission granted, fetching wheel groups from database")
        
        # Debug table names
        logger.info(f"[DEBUG] WheelGroupsTable name: {WheelGroupsTable.name}")
        logger.info(f"[DEBUG] Environment variables:")
        for key, value in os.environ.items():
            if 'TABLE' in key or 'ENVIRONMENT' in key:
                logger.info(f"[DEBUG] {key}: {value}")
        
        # Get all wheel groups from database
        wheel_groups_response = []
        
        # Scan all wheel groups with error handling
        try:
            scan_count = 0
            valid_wheel_groups = []
            
            for wheel_group in WheelGroupsTable.iter_scan():
                scan_count += 1
                wheel_group_id = wheel_group.get('wheel_group_id')
                
                # Debug the wheel group data
                logger.info(f"Processing wheel group {scan_count}:")
                logger.info(f"  - wheel_group_id: {wheel_group_id} (type: {type(wheel_group_id)})")
                logger.info(f"  - wheel_group_id repr: {repr(wheel_group_id)}")
                
                # Validate wheel_group_id - skip items with null/invalid keys
                if wheel_group_id is None:
                    logger.warning(f"Skipping wheel group with None wheel_group_id. This indicates corrupted data that should be cleaned up.")
                    continue
                
                if not wheel_group_id or not isinstance(wheel_group_id, str) or wheel_group_id.strip() == '':
                    logger.warning(f"Skipping wheel group with invalid wheel_group_id: {repr(wheel_group_id)} (type: {type(wheel_group_id)})")
                    continue
                
                # Additional validation for proper UUID format (optional but recommended)
                wheel_group_id = wheel_group_id.strip()
                if len(wheel_group_id) < 10:  # Basic sanity check for reasonable ID length
                    logger.warning(f"Skipping wheel group with suspiciously short wheel_group_id: {repr(wheel_group_id)}")
                    continue
                
                # Add to valid wheel groups list
                valid_wheel_groups.append({
                    'wheel_group_id': wheel_group_id,
                    'wheel_group_name': wheel_group.get('wheel_group_name', 'Unknown'),
                    'created_at': wheel_group.get('created_at')
                })
            
            logger.info(f"Successfully scanned {scan_count} wheel groups, {len(valid_wheel_groups)} are valid")
            
            # Process only valid wheel groups
            for wheel_group_data in valid_wheel_groups:
                wheel_group_id = wheel_group_data['wheel_group_id']
                
                logger.info(f"Getting statistics for valid wheel group: {wheel_group_id}")
                
                # Get comprehensive statistics for this wheel group with error handling
                try:
                    stats = get_wheel_group_statistics(wheel_group_id)
                except Exception as stats_error:
                    logger.error(f"Error getting stats for wheel group {wheel_group_id}: {str(stats_error)}")
                    logger.error(f"Stats error type: {type(stats_error)}")
                    import traceback
                    logger.error(f"Stats error traceback: {traceback.format_exc()}")
                    # Use default stats if we can't get real ones
                    stats = {
                        'user_count': 0,
                        'wheel_count': 0,
                        'created_at': wheel_group_data.get('created_at'),
                        'last_updated': wheel_group_data.get('created_at')
                    }
                
                # Build response object using validated data
                response_item = {
                    'wheel_group_id': wheel_group_data['wheel_group_id'],
                    'wheel_group_name': wheel_group_data['wheel_group_name'],
                    'user_count': stats['user_count'],
                    'wheel_count': stats['wheel_count'],
                    'created_at': stats['created_at'],
                    'last_updated': stats['last_updated']  # This is the calculated timestamp
                }
                
                wheel_groups_response.append(response_item)
            
            logger.info(f"Successfully processed {len(wheel_groups_response)} valid wheel groups out of {scan_count} total")
            
        except ClientError as ce:
            logger.error(f"DynamoDB ClientError during scan: {str(ce)}")
            if ce.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.error(f"Table {WheelGroupsTable.name} not found! Check table name and environment suffix.")
                return create_response(STATUS_CODES['INTERNAL_ERROR'], {
                    'error': f'Database table not found. Expected table: {WheelGroupsTable.name}. Please check environment configuration.'
                })
            raise ce
        
        logger.info(f"Successfully retrieved {len(wheel_groups_response)} wheel groups")
        return create_response(STATUS_CODES['OK'], {
            'wheel_groups': wheel_groups_response
        })
        
    except Exception as e:
        logger.error(f"Error listing wheel groups: {str(e)}")
        logger.error(f"Error type: {str(type(e))}")
        import traceback
        logger.error(f"Stacktrace: {traceback.format_exc()}")
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
        try:
            wheel_group = WheelGroupRepository.get_wheel_group(wheel_group_id)
            wheel_group_name = wheel_group.get('wheel_group_name', 'Unknown')
            logger.info(f"Deleting wheel group '{wheel_group_name}' (ID: {wheel_group_id})")
        except Exception as e:
            logger.warning(f"Could not get wheel group info: {str(e)}")
            wheel_group_name = 'Unknown'
        
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
                except cognito_client.exceptions.UserNotFoundException:
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
