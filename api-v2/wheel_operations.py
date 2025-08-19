#  Wheel Operations APIs for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
from decimal import Decimal
from typing import Dict, Any, List
from base import BadRequestError, NotFoundError
from wheel_group_middleware import wheel_group_middleware, require_wheel_group_permission, get_wheel_group_context
from utils_v2 import (
    WheelRepository, ParticipantRepository, check_string, get_uuid, 
    decimal_to_float, create_wheel_group_wheel_id, get_utc_timestamp
)

# Constants
HTTP_STATUS_CODES = {
    'OK': 200,
    'CREATED': 201,
    'NO_CONTENT': 204,
    'BAD_REQUEST': 400,
    'NOT_FOUND': 404,
    'INTERNAL_ERROR': 500
}

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}

WHEEL_CONSTRAINTS = {
    'MAX_NAME_LENGTH': 100,
    'MAX_DESCRIPTION_LENGTH': 500,
    'MIN_MULTI_SELECT_COUNT': 1,
    'MAX_MULTI_SELECT_COUNT': 10
}

DEFAULT_WHEEL_SETTINGS = {
    'allow_rigging': True,
    'multi_select_enabled': True,
    'default_multi_select_count': 1,
    'require_reason_for_rigging': False,
    'show_weights': False,
    'auto_reset_weights': False
}

VALIDATION_MESSAGES = {
    'WHEEL_NAME_REQUIRED': "wheel_name is required and must be a non-empty string",
    'WHEEL_NAME_TOO_LONG': f"wheel_name must be {WHEEL_CONSTRAINTS['MAX_NAME_LENGTH']} characters or less",
    'DESCRIPTION_TOO_LONG': f"description must be {WHEEL_CONSTRAINTS['MAX_DESCRIPTION_LENGTH']} characters or less",
    'SETTINGS_MUST_BE_OBJECT': "settings must be an object",
    'INVALID_MULTI_SELECT_COUNT': f"default_multi_select_count must be between {WHEEL_CONSTRAINTS['MIN_MULTI_SELECT_COUNT']} and {WHEEL_CONSTRAINTS['MAX_MULTI_SELECT_COUNT']}",
    'WHEEL_ID_REQUIRED': "wheel_id is required",
    'UPDATE_FIELD_REQUIRED': "At least one field must be provided for update",
    'NO_PARTICIPANTS_TO_RESET': "Wheel has no participants to reset"
}


def create_api_response(status_code: int, body: Any, additional_headers: Dict = None) -> Dict:
    """Create standardized API response with CORS headers"""
    headers = CORS_HEADERS.copy()
    if additional_headers:
        headers.update(additional_headers)
    
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(decimal_to_float(body) if isinstance(body, (dict, list)) else body) if body != '' else ''
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


def validate_wheel_name(wheel_name: str) -> None:
    """Validate wheel name"""
    if not check_string(wheel_name):
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_NAME_REQUIRED'])
    if len(wheel_name) > WHEEL_CONSTRAINTS['MAX_NAME_LENGTH']:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_NAME_TOO_LONG'])


def validate_description(description: str) -> None:
    """Validate wheel description"""
    if description and len(description) > WHEEL_CONSTRAINTS['MAX_DESCRIPTION_LENGTH']:
        raise BadRequestError(VALIDATION_MESSAGES['DESCRIPTION_TOO_LONG'])


def validate_settings(settings: Dict) -> None:
    """Validate wheel settings"""
    if not isinstance(settings, dict):
        raise BadRequestError(VALIDATION_MESSAGES['SETTINGS_MUST_BE_OBJECT'])
    
    # Validate multi-select count if provided
    if 'default_multi_select_count' in settings:
        count = settings['default_multi_select_count']
        if not isinstance(count, int) or count < WHEEL_CONSTRAINTS['MIN_MULTI_SELECT_COUNT'] or count > WHEEL_CONSTRAINTS['MAX_MULTI_SELECT_COUNT']:
            raise BadRequestError(VALIDATION_MESSAGES['INVALID_MULTI_SELECT_COUNT'])


def parse_request_body(event) -> Dict:
    """Parse request body from event"""
    body_str = event.get('body', '{}')
    return body_str if isinstance(body_str, dict) else (json.loads(body_str) if body_str else {})


def get_sub_wheel_size(participant_name: str, wheel_group_id: str) -> int:
    """
    Look for a wheel with the same name as the participant and return its participant count.
    This implements the same logic as V1's get_sub_wheel_size function.
    """
    try:
        # Look for wheels in the same wheel group with matching name
        wheel_group_wheels = WheelRepository.list_wheel_group_wheels(wheel_group_id)
        for wheel in wheel_group_wheels:
            if wheel.get('wheel_name') == participant_name:
                # Get participants for this wheel to count them
                wheel_participants = ParticipantRepository.list_wheel_participants(
                    wheel_group_id, 
                    wheel['wheel_id']
                )
                participant_count = len(wheel_participants)
                return participant_count if participant_count > 0 else 1
        return 1  # Default to 1 if no matching wheel found
    except:
        return 1  # Default to 1 on any error


@require_wheel_group_permission('view_wheels')
@handle_api_exceptions
def list_wheel_group_wheels(event, context=None):
    """
    List all wheels for the current wheel group
    
    GET /v2/wheels
    """
    try:
        print(f"[DEBUG] list_wheel_group_wheels called")
        wheel_group_context = get_wheel_group_context(event)
        print(f"[DEBUG] wheel_group_context: {wheel_group_context}")
        
        if not wheel_group_context or not wheel_group_context.get('wheel_group_id'):
            print(f"[ERROR] Missing wheel_group_context or wheel_group_id")
            raise BadRequestError("No wheel group associated with user")
        
        wheels = WheelRepository.list_wheel_group_wheels(wheel_group_context['wheel_group_id'])
        print(f"[DEBUG] Found {len(wheels)} wheels")
        
        return create_api_response(HTTP_STATUS_CODES['OK'], {
            'wheels': wheels,
            'count': len(wheels)
        })
    except Exception as e:
        print(f"[ERROR] list_wheel_group_wheels detailed error: {str(e)}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise e


@require_wheel_group_permission('create_wheel')
@handle_api_exceptions
def create_wheel(event, context=None):
    """
    Create a new wheel for the current wheel group
    
    POST /v2/wheels
    
    {
      "wheel_name": "Daily Standup",
      "description": "Choose who leads today's standup",
      "settings": {
        "allow_rigging": true,
        "multi_select_enabled": true,
        "default_multi_select_count": 1,
        "show_weights": false
      }
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    body = parse_request_body(event)
    
    # Validate required fields
    validate_wheel_name(body.get('wheel_name'))
    
    # Validate description if provided
    description = body.get('description', '')
    validate_description(description)
    
    # Validate settings if provided
    settings = body.get('settings', {})
    validate_settings(settings)
    
    # Create wheel data with defaults
    wheel_data = {
        'wheel_name': body['wheel_name'],
        'description': description,
        'created_by': wheel_group_context['user_id'],
        'settings': {**DEFAULT_WHEEL_SETTINGS, **settings}
    }
    
    # Create the wheel
    wheel = WheelRepository.create_wheel(wheel_group_context['wheel_group_id'], wheel_data)
    
    return create_api_response(HTTP_STATUS_CODES['CREATED'], wheel)


@require_wheel_group_permission('view_wheels')
@handle_api_exceptions
def get_wheel(event, context=None):
    """
    Get specific wheel details
    
    GET /v2/wheels/{wheel_id}
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Get wheel
    wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get participants for this wheel
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    # Include participant count and details
    wheel_with_participants = wheel.copy()
    wheel_with_participants['participants'] = participants
    wheel_with_participants['participant_count'] = len(participants)
    
    return create_api_response(HTTP_STATUS_CODES['OK'], wheel_with_participants)


@require_wheel_group_permission('create_wheel')
@handle_api_exceptions
def update_wheel(event, context=None):
    """
    Update wheel settings
    
    PUT /v2/wheels/{wheel_id}
    
    {
      "wheel_name": "Updated Name",
      "description": "Updated description",
      "settings": {
        "allow_rigging": false,
        "multi_select_enabled": true
      }
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    body = parse_request_body(event)
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    existing_wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Prepare updates
    updates = {}
    
    # Update wheel name if provided
    if 'wheel_name' in body:
        validate_wheel_name(body['wheel_name'])
        updates['wheel_name'] = body['wheel_name']
    
    # Update description if provided
    if 'description' in body:
        description = body['description'] or ''
        validate_description(description)
        updates['description'] = description
    
    # Update settings if provided
    if 'settings' in body:
        validate_settings(body['settings'])
        
        # Merge with existing settings
        current_settings = existing_wheel.get('settings', {})
        new_settings = {**current_settings, **body['settings']}
        updates['settings'] = new_settings
    
    if not updates:
        raise BadRequestError(VALIDATION_MESSAGES['UPDATE_FIELD_REQUIRED'])
    
    # Update the wheel
    updated_wheel = WheelRepository.update_wheel(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        updates
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], updated_wheel)


@require_wheel_group_permission('delete_wheel')
@handle_api_exceptions
def delete_wheel(event, context=None):
    """
    Delete a wheel and all its participants
    
    DELETE /v2/wheels/{wheel_id}
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group (this will throw NotFoundError if not)
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Delete wheel and all participants
    WheelRepository.delete_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    return create_api_response(HTTP_STATUS_CODES['NO_CONTENT'], '')


@require_wheel_group_permission('manage_participants')
@handle_api_exceptions  
def reset_wheel_weights(event, context=None):
    """
    Reset all participant weights in a wheel to their original values
    
    POST /v2/wheels/{wheel_id}/reset
    
    {
      "reason": "Starting fresh for new sprint"
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    body = parse_request_body(event)
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get all participants
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    if not participants:
        raise BadRequestError(VALIDATION_MESSAGES['NO_PARTICIPANTS_TO_RESET'])
    
    # Reset weights for all participants using V1 logic
    # IMPORTANT: Include ALL original fields to prevent data loss in batch update
    participant_updates = []
    for participant in participants:
        # Skip any None participant records
        if not participant or not isinstance(participant, dict):
            continue
        
        # Skip participants without required fields
        if not participant.get('participant_id') or not participant.get('participant_name'):
            continue
            
        # Use V1 logic: get sub-wheel size based on participant name
        reset_weight = get_sub_wheel_size(participant['participant_name'], wheel_group_context['wheel_group_id'])
        reset_weight_decimal = Decimal(str(reset_weight))
        
        update_data = {
            'participant_id': participant['participant_id'],
            'participant_name': participant['participant_name'],  # Preserve name
            'participant_url': participant.get('participant_url', ''),  # Preserve URL
            'weight': reset_weight_decimal,  # Reset using V1 sub-wheel logic
            'original_weight': reset_weight_decimal,  # Store this as the new original weight
            'selection_count': Decimal('0'),  # Reset selection count as Decimal
            'created_at': participant.get('created_at'),  # Preserve creation time
            'updated_at': get_utc_timestamp(),  # Add required updated_at timestamp
            # Note: last_selected_at is intentionally omitted to be set to None/removed
        }
        participant_updates.append(update_data)
    
    # Batch update all participants
    ParticipantRepository.batch_update_participants(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        participant_updates
    )
    
    # Update wheel's reset information
    WheelRepository.update_wheel(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        {'total_spins': 0}
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'message': f'Reset weights for {len(participants)} participants',
        'participants_affected': len(participants),
        'reason': body.get('reason', 'Manual reset')
    })


# Export Lambda handler functions
lambda_handlers = {
    'list_wheel_group_wheels': list_wheel_group_wheels,
    'create_wheel': create_wheel,
    'get_wheel': get_wheel,
    'update_wheel': update_wheel,
    'delete_wheel': delete_wheel,
    'reset_wheel_weights': reset_wheel_weights
}
