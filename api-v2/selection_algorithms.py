#  Selection Algorithms for AWS Ops Wheel v2 - Legacy Single Selection
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import random
from typing import Dict, Any, List, Optional
from decimal import Decimal
from base import BadRequestError, NotFoundError
from wheel_group_middleware import require_wheel_group_permission, get_wheel_group_context
from utils_v2 import (
    WheelRepository, ParticipantRepository, 
    get_utc_timestamp, decimal_to_float
)

# Constants
HTTP_STATUS_CODES = {
    'OK': 200,
    'CREATED': 201,
    'BAD_REQUEST': 400,
    'NOT_FOUND': 404,
    'INTERNAL_ERROR': 500
}

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}

VALIDATION_MESSAGES = {
    'WHEEL_ID_REQUIRED': "wheel_id is required",
    'NO_PARTICIPANTS': "Wheel has no participants",
    'NO_PARTICIPANTS_AVAILABLE': "No participants available for selection"
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
            return create_error_response(HTTP_STATUS_CODES['INTERNAL_ERROR'], f'Internal server error: {str(e)}')
    
    return wrapper


def calculate_selection_probabilities(participants: List[Dict]) -> Dict[str, float]:
    """
    Calculate selection probabilities for each participant based on their weights
    
    Returns dictionary mapping participant_id to probability (0.0-1.0)
    """
    if not participants:
        return {}
    
    # Calculate total weight - add safety check for None
    total_weight = sum(float(p.get('weight', 1.0)) for p in participants if p is not None)
    
    if total_weight == 0:
        # If all weights are 0, give equal probability to all participants
        active_participants = [p for p in participants if p is not None]
        equal_prob = 1.0 / len(active_participants) if active_participants else 0
        return {p['participant_id']: equal_prob for p in active_participants}
    
    # Calculate weighted probabilities
    probabilities = {}
    for participant in participants:
        if participant is None:
            continue
        weight = float(participant.get('weight', 1.0))
        probabilities[participant['participant_id']] = weight / total_weight
    
    return probabilities


def suggest_participant_legacy(participants: List[Dict], rigging_data: Optional[Dict] = None) -> Dict:
    """
    Single selection algorithm using cumulative weight selection
    Based on original AWS Ops Wheel algorithm
    """
    if not participants:
        raise BadRequestError("No participants available for selection")
    
    # Check for rigging
    if rigging_data:
        rigged_id = rigging_data.get('rigged_participant_id')
        for participant in participants:
            if participant['participant_id'] == rigged_id:
                return participant
        # If rigged participant not found, fall through to normal selection
    
    # Calculate total weight
    total_weight = sum(float(p.get('weight', 1.0)) for p in participants)
    
    if total_weight == 0:
        # If all weights are 0, select randomly
        return random.choice(participants)
    
    # Get random number between 0 and total_weight
    target_number = total_weight * random.random()
    
    # Find participant using cumulative weight
    for participant in participants:
        target_number -= float(participant.get('weight', 1.0))
        if target_number <= 0:
            return participant
    
    # Fallback (should not reach here)
    return participants[-1]


def apply_single_selection_weight_redistribution(participants: List[Dict], selected_participant: Dict):
    """
    Apply weight redistribution for single selection
    
    When there is only one participant in the wheel, the selected participant's weight remains intact.
    Otherwise, the remaining participant(s) get a slice of the selected participant's weight. 
    That participant will not be chosen on next spin unless it's rigged.
    """
    if len(participants) <= 1:
        return  # No redistribution needed for single participant
    
    selected_weight = float(selected_participant.get('weight', 1.0))
    others_count = len(participants) - 1
    
    if others_count > 0 and selected_weight > 0:
        weight_slice = selected_weight / others_count  # Equal slice for each other participant
        
        for participant in participants:
            if participant['participant_id'] == selected_participant['participant_id']:
                # Selected participant gets 0 weight (proper conservation)
                participant['weight'] = Decimal('0')
            else:
                # Other participants get their slice of the selected participant's weight
                current_weight = float(participant.get('weight', 1.0))
                participant['weight'] = Decimal(str(current_weight + weight_slice))


@require_wheel_group_permission('spin_wheel')
@handle_api_exceptions
def suggest_participant(event, context=None):
    """
    Single participant selection endpoint (v1 compatible)
    
    POST /v2/wheels/{wheel_id}/suggest
    
    {
      "apply_changes": true
    }
    """
    wheel_group_context = get_wheel_group_context(event)
    
    # Safe extraction of wheel_id
    path_params = event.get('pathParameters') or {}
    wheel_id = path_params.get('wheel_id') if path_params else None
    body = event.get('body') or {}
    
    # Handle case where body might be a JSON string
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {}
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Get wheel and check permissions
    wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get participants
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    if not participants:
        raise BadRequestError(VALIDATION_MESSAGES['NO_PARTICIPANTS'])
    
    # Check for rigging
    rigging_data = wheel.get('rigging') if wheel else None
    
    # Select participant using legacy algorithm
    selected_participant = suggest_participant_legacy(participants, rigging_data)
    
    # Calculate probabilities for UI display
    probabilities = calculate_selection_probabilities(participants)
    
    # Apply changes if requested
    apply_changes = body.get('apply_changes', False)
    
    if apply_changes:
        # Apply weight redistribution (single selection)
        apply_single_selection_weight_redistribution(participants, selected_participant)
        
        # Update participants in database
        updates = []
        for participant in participants:
            is_selected = participant['participant_id'] == selected_participant['participant_id']
            update_data = {
                'participant_id': participant['participant_id'],
                'weight': Decimal(str(participant['weight'])) if not isinstance(participant['weight'], Decimal) else participant['weight'],
                'selection_count': Decimal(str((participant.get('selection_count', 0) + 1) if is_selected else participant.get('selection_count', 0)))
            }
            
            # Only set last_selected_at for selected participants to avoid GSI issues
            if is_selected:
                update_data['last_selected_at'] = get_utc_timestamp()
            elif participant.get('last_selected_at'):
                # Only include last_selected_at if it already exists (not None)
                update_data['last_selected_at'] = participant['last_selected_at']
            
            updates.append(update_data)
        
        ParticipantRepository.batch_update_participants(
            wheel_group_context['wheel_group_id'],
            wheel_id,
            updates
        )
        
        # Update wheel spin information
        wheel_updates = {
            'last_spun_at': get_utc_timestamp(),
            'last_spun_by': wheel_group_context['user_id'],
            'total_spins': wheel.get('total_spins', 0) + 1
        }
        
        # Clear rigging after use
        if rigging_data:
            wheel_updates['rigging'] = None
            
        WheelRepository.update_wheel(
            wheel_group_context['wheel_group_id'],
            wheel_id,
            wheel_updates
        )
    
    # Determine rigging visibility (v1 compatibility)
    # Only show rigged: True if rigging exists and is NOT hidden
    show_rigged = bool(rigging_data and not rigging_data.get('hidden', False))
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'selected_participant': selected_participant,
        'selection_type': 'single',
        'rigged': show_rigged,
        'probabilities': probabilities,
        'changes_applied': apply_changes
    })


@require_wheel_group_permission('view_wheels')
@handle_api_exceptions
def get_selection_probabilities(event, context=None):
    """
    Get current selection probabilities for all participants
    
    GET /v2/wheels/{wheel_id}/probabilities
    """
    wheel_group_context = get_wheel_group_context(event)
    wheel_id = event.get('pathParameters', {}).get('wheel_id')
    
    if not wheel_id:
        raise BadRequestError(VALIDATION_MESSAGES['WHEEL_ID_REQUIRED'])
    
    # Verify wheel exists
    wheel = WheelRepository.get_wheel(wheel_group_context['wheel_group_id'], wheel_id)
    
    # Get participants
    participants = ParticipantRepository.list_wheel_participants(
        wheel_group_context['wheel_group_id'], 
        wheel_id
    )
    
    if not participants:
        raise BadRequestError(VALIDATION_MESSAGES['NO_PARTICIPANTS'])
    
    # Calculate probabilities
    probabilities = calculate_selection_probabilities(participants)
    
    # Format response with participant details
    participant_probabilities = []
    for participant in participants:
        participant_probabilities.append({
            'participant_id': participant['participant_id'],
            'participant_name': participant['participant_name'],
            'current_weight': float(participant.get('weight', 1.0)),
            'selection_probability': probabilities.get(participant['participant_id'], 0.0),
            'selection_count': participant.get('selection_count', 0),
            'last_selected_at': participant.get('last_selected_at')
        })
    
    return create_api_response(HTTP_STATUS_CODES['OK'], {
        'wheel_id': wheel_id,
        'participants': participant_probabilities,
        'rigged': bool(wheel.get('rigging')),
        'rigged_participant': wheel.get('rigging', {}).get('rigged_participant_name') if wheel.get('rigging') else None
    })


# Export Lambda handler functions  
lambda_handlers = {
    'suggest_participant': suggest_participant,
    'get_selection_probabilities': get_selection_probabilities
}
