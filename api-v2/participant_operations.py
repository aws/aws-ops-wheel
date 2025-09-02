#  Participant Operations APIs for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
from typing import Dict, Any, List
from decimal import Decimal
from base import BadRequestError, NotFoundError
from wheel_group_middleware import require_wheel_group_permission, get_wheel_group_context
from utils_v2 import (
    WheelRepository, ParticipantRepository, check_string, 
    get_utc_timestamp, decimal_to_float
)
from selection_algorithms import apply_single_selection_weight_redistribution

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

EXTENDED_CORS_HEADERS = {
    **CORS_HEADERS,
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
}

PARTICIPANT_CONSTRAINTS = {
    'MAX_NAME_LENGTH': 100,
    'MAX_URL_LENGTH': 500,
    'MIN_WEIGHT': 0,
    'MAX_WEIGHT': 100,
    'DEFAULT_WEIGHT': 1.0,
    'DEFAULT_MAX_PARTICIPANTS': 100
}

VALIDATION_MESSAGES = {
    'WHEEL_ID_REQUIRED': "wheel_id is required",
    'PARTICIPANT_ID_REQUIRED': "participant_id is required",
    'PARTICIPANT_NAME_REQUIRED': "participant_name is required and must be a non-empty string",
    'PARTICIPANT_NAME_TOO_LONG': f"participant_name must be {PARTICIPANT_CONSTRAINTS['MAX_NAME_LENGTH']} characters or less",
    'PARTICIPANT_URL_TOO_LONG': f"participant_url must be {PARTICIPANT_CONSTRAINTS['MAX_URL_LENGTH']} characters or less",
    'INVALID_WEIGHT': f"weight must be a number between {PARTICIPANT_CONSTRAINTS['MIN_WEIGHT']} and {PARTICIPANT_CONSTRAINTS['MAX_WEIGHT']}",
    'INVALID_REQUEST_BODY': "Invalid request body format",
    'PARTICIPANT_EXISTS': "Participant '{}' already exists in this wheel",
    'MAX_PARTICIPANTS_REACHED': "Wheel has reached maximum participant limit of {}",
    'UPDATE_FIELD_REQUIRED': "At least one field must be provided for update",
    'LAST_PARTICIPANT': "Cannot delete the last participant from a wheel",
    'RIGGING_NOT_ALLOWED': "Rigging is not allowed for this wheel",
    'REASON_REQUIRED': "Reason is required for rigging this wheel",
    'PARTICIPANT_NOT_FOUND_IN_WHEEL': "Selected participant not found in wheel"
}

RIGGING_DEFAULTS = {
    'HIDDEN': False,
    'REQUIRE_REASON': False
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


def create_error_response(status_code: int, error_message: str, extended_cors: bool = False) -> Dict:
    """Create standardized error response"""
    headers = EXTENDED_CORS_HEADERS if extended_cors else CORS_HEADERS
    return create_api_response(status_code, {'error': error_message}, headers)


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
            return create_error_response(HTTP_STATUS_CODES['INTERNAL_ERROR'], f'Internal server error: {str(e)}')
    
    return wrapper


def validate_participant_name(participant_name: str) -> None:
    """Validate participant name"""
    if not check_string(participant_name):
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_NAME_REQUIRED'])
    if len(participant_name) > PARTICIPANT_CONSTRAINTS['MAX_NAME_LENGTH']:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_NAME_TOO_LONG'])


def validate_participant_url(participant_url: str) -> None:
    """Validate participant URL"""
    if participant_url and len(participant_url) > PARTICIPANT_CONSTRAINTS['MAX_URL_LENGTH']:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_URL_TOO_LONG'])


def validate_weight(weight: Any) -> float:
    """Validate and convert weight to float"""
    try:
        weight = float(weight)
        if weight < PARTICIPANT_CONSTRAINTS['MIN_WEIGHT'] or weight > PARTICIPANT_CONSTRAINTS['MAX_WEIGHT']:
            raise BadRequestError(VALIDATION_MESSAGES['INVALID_WEIGHT'])
        return weight
    except (TypeError, ValueError):
        raise BadRequestError(VALIDATION_MESSAGES['INVALID_WEIGHT'])


def validate_request_body(body: Any) -> Dict:
    """Validate and clean request body"""
    if not isinstance(body, dict):
        raise BadRequestError(VALIDATION_MESSAGES['INVALID_REQUEST_BODY'])
    
    # Remove participant_id from body if present (not needed for creation/updates)
    return {k: v for k, v in body.items() if k != 'participant_id'}


def check_participant_name_conflict(wheel_group_id: str, wheel_id: str, participant_name: str, exclude_participant_id: str = None) -> None:
    """Check if participant name already exists in wheel"""
    existing_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    
    for participant in existing_participants:
        if (participant['participant_name'].lower() == participant_name.lower() and 
            participant['participant_id'] != exclude_participant_id):
            raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_EXISTS'].format(participant_name))


def check_participant_limit(wheel: Dict, existing_participants: List) -> None:
    """Check if wheel has reached participant limit"""
    max_participants = wheel.get('settings', {}).get('max_participants_per_wheel', PARTICIPANT_CONSTRAINTS['DEFAULT_MAX_PARTICIPANTS'])
    if len(existing_participants) >= max_participants:
        raise BadRequestError(VALIDATION_MESSAGES['MAX_PARTICIPANTS_REACHED'].format(max_participants))


def parse_request_body(event) -> Dict:
    """Parse request body from event"""
    body = event.get('body', {})
    return validate_request_body(body)


@require_wheel_group_permission('view_wheels')
@handle_api_exceptions
def list_wheel_participants(event, context=None):
    """
    List all participants for a specific wheel
    
    GET /v2/wheels/{wheel_id}/participants
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get participants
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'participants': participants,
        'count': len(participants)
    }, EXTENDED_CORS_HEADERS)


@require_wheel_group_permission('manage_participants')
@handle_api_exceptions
def create_participant(event, context=None):
    """
    Add a new participant to a wheel
    
    POST /v2/wheels/{wheel_id}/participants
    
    {
      "participant_name": "Alice Johnson",
      "participant_url": "https://example.com/alice",
      "weight": 1.0
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    body = parse_request_body(event)
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Validate required fields
    validate_participant_name(body.get('participant_name'))
    
    # Validate participant URL if provided
    participant_url = body.get('participant_url', '')
    validate_participant_url(participant_url)
    
    # Validate weight
    weight = validate_weight(body.get('weight', PARTICIPANT_CONSTRAINTS['DEFAULT_WEIGHT']))
    
    # Verify wheel exists and belongs to wheel group
    wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get existing participants
    existing_participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    # Check name conflicts and participant limits
    check_participant_name_conflict(wheel_group_context['wheel_group_id'], wheel_id, body['participant_name'])
    check_participant_limit(wheel, existing_participants)
    
    # Create participant data
    participant_data = {
        'participant_name': body['participant_name'],
        'participant_url': participant_url,
        'weight': weight
    }
    
    # Create the participant
    participant = ParticipantRepository.create_participant(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        participant_data
    )
    
    # Update wheel participant count
    WheelRepository.update_wheel(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        {'participant_count': len(existing_participants) + 1}
    )
    
    return create_api_response(HTTP_STATUS_CODES['CREATED'], participant)


@require_wheel_group_permission('view_wheels')
@handle_api_exceptions
def get_participant(event, context=None):
    """
    Get specific participant details
    
    GET /v2/wheels/{wheel_id}/participants/{participant_id}
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    participant_id = event.get('pathParameters', {}).get('participant_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    if not participant_id:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get participant
    participant = ParticipantRepository.get_participant(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        participant_id
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], participant)


@require_wheel_group_permission('manage_participants')
@handle_api_exceptions
def update_participant(event, context=None):
    """
    Update participant information
    
    PUT /v2/wheels/{wheel_id}/participants/{participant_id}
    
    {
      "participant_name": "Alice Smith",
      "participant_url": "https://example.com/alice-smith",
      "weight": 1.5
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    participant_id = event.get('pathParameters', {}).get('participant_id')
    body = parse_request_body(event)
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    if not participant_id:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Verify participant exists
    existing_participant = ParticipantRepository.get_participant(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        participant_id
    )
    
    # Prepare updates
    updates = {}
    
    # Update participant name if provided
    if 'participant_name' in body:
        validate_participant_name(body['participant_name'])
        
        # Check for name conflicts with other participants
        if body['participant_name'].lower() != existing_participant['participant_name'].lower():
            check_participant_name_conflict(
                wheel_group_context['wheel_group_id'], 
                wheel_id, 
                body['participant_name'], 
                exclude_participant_id=participant_id
            )
        
        updates['participant_name'] = body['participant_name']
    
    # Update participant URL if provided
    if 'participant_url' in body:
        participant_url = body['participant_url'] or ''
        validate_participant_url(participant_url)
        updates['participant_url'] = participant_url
    
    # Update weight if provided
    if 'weight' in body:
        weight = validate_weight(body['weight'])
        updates['weight'] = weight
        updates['original_weight'] = weight
    
    if not updates:
        raise BadRequestError(VALIDATION_MESSAGES['UPDATE_FIELD_REQUIRED'])
    
    # Update the participant
    updated_participant = ParticipantRepository.update_participant(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        participant_id,
        updates
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], updated_participant, EXTENDED_CORS_HEADERS)


@require_wheel_group_permission('manage_participants')
@handle_api_exceptions
def delete_participant(event, context=None):
    """
    Remove a participant from a wheel
    
    DELETE /v2/wheels/{wheel_id}/participants/{participant_id}
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    participant_id = event.get('pathParameters', {}).get('participant_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    if not participant_id:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Verify participant exists
    ParticipantRepository.get_participant(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        participant_id
    )
    
    # Check if this is the last participant
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    if len(participants) <= 1:
        raise BadRequestError(VALIDATION_MESSAGES['LAST_PARTICIPANT'])
    
    # Delete the participant
    deleted_participant = ParticipantRepository.delete_participant(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        participant_id
    )
    
    # Update wheel participant count
    WheelRepository.update_wheel(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        {'participant_count': len(participants) - 1}
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'message': 'Participant deleted successfully',
        'deleted_participant': deleted_participant
    })


@require_wheel_group_permission('rig_wheel')
@handle_api_exceptions
def rig_participant(event, context=None):
    """
    Rig the wheel to select a specific participant next
    
    POST /v2/wheels/{wheel_id}/participants/{participant_id}/rig
    
    {
      "reason": "Alice volunteered to present",
      "hidden": false
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    participant_id = event.get('pathParameters', {}).get('participant_id')
    body = event.get('body', {})
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    if not participant_id:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Check if rigging is allowed for this wheel
    if not wheel.get('settings', {}).get('allow_rigging', True):
        raise BadRequestError(VALIDATION_MESSAGES['RIGGING_NOT_ALLOWED'])
    
    # Verify participant exists
    participant = ParticipantRepository.get_participant(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        participant_id
    )
    
    # Check if reason is required
    require_reason = wheel.get('settings', {}).get('require_reason_for_rigging', RIGGING_DEFAULTS['REQUIRE_REASON'])
    reason = body.get('reason', '')
    
    if require_reason and not check_string(reason):
        raise BadRequestError(VALIDATION_MESSAGES['REASON_REQUIRED'])
    
    # Prepare rigging data
    # Standardize on 'hidden' field name across frontend and backend
    # hidden=true means rigging is deceptive/secret, hidden=false means obvious/visible
    hidden = body.get('hidden', RIGGING_DEFAULTS['HIDDEN'])
    
    rigging_data = {
        'rigged_participant_id': participant_id,
        'rigged_participant_name': participant['participant_name'],
        'rigged_by': wheel_group_context['user_id'],
        'rigged_at': get_utc_timestamp(),
        'reason': reason,
        'hidden': hidden  # Whether rigging is hidden (true) or obvious (false)
    }
    
    # Update wheel with rigging information
    WheelRepository.update_wheel(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        {'rigging': rigging_data}
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'message': f"Wheel rigged to select {participant['participant_name']}",
        'rigging': rigging_data,
        'hidden': rigging_data['hidden']
    })


@require_wheel_group_permission('view_wheels')
@handle_api_exceptions
def select_participant(event, context=None):
    """
    Record that a participant was selected (for tracking and weight adjustment)
    
    POST /v2/wheels/{wheel_id}/participants/{participant_id}/select
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    participant_id = event.get('pathParameters', {}).get('participant_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    if not participant_id:
        raise BadRequestError(VALIDATION_MESSAGES['PARTICIPANT_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Verify participant exists
    participant = ParticipantRepository.get_participant(
        wheel_group_context['wheel_group_id'], 
        wheel_id, 
        participant_id
    )
    
    # Get all participants for weight redistribution (same as v1 logic)
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    # Find the selected participant in the list
    selected_participant = None
    for p in participants:
        if p['participant_id'] == participant_id:
            selected_participant = p
            break
    
    if not selected_participant:
        raise NotFoundError(VALIDATION_MESSAGES['PARTICIPANT_NOT_FOUND_IN_WHEEL'])
    
    # Apply weight redistribution (single selection) - same as v1 logic
    apply_single_selection_weight_redistribution(participants, selected_participant)
    
    # Update participants in database - same as v1 logic
    # IMPORTANT: Include ALL original fields to prevent data loss in batch update
    updates = []
    for participant_item in participants:
        is_selected = participant_item['participant_id'] == selected_participant['participant_id']
        
        # Ensure all numeric values are properly converted to Decimal for DynamoDB
        weight = participant_item['weight']
        if not isinstance(weight, Decimal):
            weight = Decimal(str(weight))
        
        original_weight = participant_item.get('original_weight', participant_item['weight'])
        if not isinstance(original_weight, Decimal):
            original_weight = Decimal(str(original_weight))
            
        selection_count = (participant_item.get('selection_count', 0) + 1) if is_selected else participant_item.get('selection_count', 0)
        if not isinstance(selection_count, Decimal):
            selection_count = Decimal(str(selection_count))
        
        update_data = {
            'participant_id': participant_item['participant_id'],
            'participant_name': participant_item['participant_name'],  # Preserve name
            'participant_url': participant_item.get('participant_url', ''),  # Preserve URL
            'weight': weight,
            'original_weight': original_weight,
            'selection_count': selection_count,
            'created_at': participant_item.get('created_at', get_utc_timestamp()),  # Preserve creation time
        }
        
        # Only set last_selected_at for selected participants to avoid GSI issues - same as v1 logic
        if is_selected:
            update_data['last_selected_at'] = get_utc_timestamp()
        elif participant_item.get('last_selected_at'):
            # Only include last_selected_at if it already exists (not None)
            update_data['last_selected_at'] = participant_item['last_selected_at']
        
        updates.append(update_data)
    
    ParticipantRepository.batch_update_participants(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        updates
    )
    
    # Clear rigging after selection - same as v1 logic
    if wheel.get('rigging'):
        WheelRepository.update_wheel(
            wheel_group_context['wheel_group_id'],
            wheel_id,
            {'rigging': None}
        )
    
    # Get updated selection count for response
    updated_selection_count = selected_participant.get('selection_count', 0) + 1
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'message': f"Participant {selected_participant['participant_name']} selected successfully",
        'participant': selected_participant,
        'selection_count': int(updated_selection_count)
    })


@require_wheel_group_permission('rig_wheel')
@handle_api_exceptions
def remove_rigging(event, context=None):
    """
    Remove rigging from a wheel
    
    DELETE /v2/wheels/{wheel_id}/rigging
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Verify wheel exists and belongs to wheel group
    WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Remove rigging (succeed even if wheel is not currently rigged)
    WheelRepository.update_wheel(
        wheel_group_context['wheel_group_id'],
        wheel_id,
        {'rigging': None}
    )
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'message': 'Rigging removed successfully'
    })


# Export Lambda handler functions
lambda_handlers = {
    'list_wheel_participants': list_wheel_participants,
    'create_participant': create_participant,
    'get_participant': get_participant,
    'update_participant': update_participant,
    'delete_participant': delete_participant,
    'rig_participant': rig_participant,
    'select_participant': select_participant,
    'remove_rigging': remove_rigging
}
