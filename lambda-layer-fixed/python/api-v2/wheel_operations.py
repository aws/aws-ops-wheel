#  Wheel Operations APIs for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
from decimal import Decimal
from typing import Dict, Any, List
from base import BadRequestError, NotFoundError
from tenant_middleware import tenant_middleware, require_tenant_permission, get_tenant_context
from utils_v2 import (
    WheelRepository, ParticipantRepository, check_string, get_uuid, 
    decimal_to_float, create_tenant_wheel_id, get_utc_timestamp
)


@require_tenant_permission('view_wheels')
def list_tenant_wheels(event, context=None):
    """
    List all wheels for the current tenant
    
    GET /v2/wheels
    """
    try:
        tenant_context = get_tenant_context(event)
        wheels = WheelRepository.list_tenant_wheels(tenant_context['tenant_id'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'wheels': decimal_to_float(wheels),
                'count': len(wheels)
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


@require_tenant_permission('create_wheel')
def create_wheel(event, context=None):
    """
    Create a new wheel for the current tenant
    
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
    try:
        tenant_context = get_tenant_context(event)
        body_str = event.get('body', '{}')
        body = json.loads(body_str) if isinstance(body_str, str) else body_str
        
        # Validate required fields
        if not check_string(body.get('wheel_name')):
            raise BadRequestError("wheel_name is required and must be a non-empty string")
        
        # Validate wheel name length
        if len(body['wheel_name']) > 100:
            raise BadRequestError("wheel_name must be 100 characters or less")
        
        # Validate description if provided
        description = body.get('description', '')
        if description and len(description) > 500:
            raise BadRequestError("description must be 500 characters or less")
        
        # Validate settings if provided
        settings = body.get('settings', {})
        if not isinstance(settings, dict):
            raise BadRequestError("settings must be an object")
        
        # Create wheel data
        wheel_data = {
            'wheel_name': body['wheel_name'],
            'description': description,
            'created_by': tenant_context['user_id'],
            'settings': {
                'allow_rigging': settings.get('allow_rigging', True),
                'multi_select_enabled': settings.get('multi_select_enabled', True),
                'default_multi_select_count': settings.get('default_multi_select_count', 1),
                'require_reason_for_rigging': settings.get('require_reason_for_rigging', False),
                'show_weights': settings.get('show_weights', False),
                'auto_reset_weights': settings.get('auto_reset_weights', False)
            }
        }
        
        # Validate multi-select count
        multi_select_count = wheel_data['settings']['default_multi_select_count']
        if not isinstance(multi_select_count, int) or multi_select_count < 1 or multi_select_count > 10:
            raise BadRequestError("default_multi_select_count must be between 1 and 10")
        
        # Create the wheel
        wheel = WheelRepository.create_wheel(tenant_context['tenant_id'], wheel_data)
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(wheel))
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
def get_wheel(event, context=None):
    """
    Get specific wheel details
    
    GET /v2/wheels/{wheel_id}
    """
    try:
        tenant_context = get_tenant_context(event)
        wheel_id = event.get('pathParameters', {}).get('wheel_id')
        
        if not wheel_id:
            raise BadRequestError("wheel_id is required")
        
        # Get wheel
        wheel = WheelRepository.get_wheel(tenant_context['tenant_id'], wheel_id)
        
        # Get participants for this wheel
        participants = ParticipantRepository.list_wheel_participants(
            tenant_context['tenant_id'], 
            wheel_id
        )
        
        # Include participant count and details
        wheel_with_participants = decimal_to_float(wheel)
        wheel_with_participants['participants'] = participants
        wheel_with_participants['participant_count'] = len(participants)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(wheel_with_participants)
        }
        
    except (BadRequestError, NotFoundError) as e:
        status_code = getattr(e, 'status_code', 400) if hasattr(e, 'status_code') else (404 if isinstance(e, NotFoundError) else 400)
        return {
            'statusCode': status_code,
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


@require_tenant_permission('create_wheel')
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
    try:
        tenant_context = get_tenant_context(event)
        wheel_id = event.get('pathParameters', {}).get('wheel_id')
        body_str = event.get('body', '{}')
        
        # Body is already parsed by main lambda handler
        body = body_str if isinstance(body_str, dict) else (json.loads(body_str) if body_str else {})
        
        if not wheel_id:
            raise BadRequestError("wheel_id is required")
        
        # Verify wheel exists and belongs to tenant
        existing_wheel = WheelRepository.get_wheel(tenant_context['tenant_id'], wheel_id)
        
        # Prepare updates
        updates = {}
        
        # Update wheel name if provided
        if 'wheel_name' in body:
            if not check_string(body['wheel_name']):
                raise BadRequestError("wheel_name must be a non-empty string")
            if len(body['wheel_name']) > 100:
                raise BadRequestError("wheel_name must be 100 characters or less")
            updates['wheel_name'] = body['wheel_name']
        
        # Update description if provided
        if 'description' in body:
            description = body['description'] or ''
            if len(description) > 500:
                raise BadRequestError("description must be 500 characters or less")
            updates['description'] = description
        
        # Update settings if provided
        if 'settings' in body:
            if not isinstance(body['settings'], dict):
                raise BadRequestError("settings must be an object")
            
            # Merge with existing settings
            current_settings = existing_wheel.get('settings', {})
            new_settings = {**current_settings, **body['settings']}
            
            # Validate multi-select count if provided
            if 'default_multi_select_count' in new_settings:
                count = new_settings['default_multi_select_count']
                if not isinstance(count, int) or count < 1 or count > 10:
                    raise BadRequestError("default_multi_select_count must be between 1 and 10")
            
            updates['settings'] = new_settings
        
        if not updates:
            raise BadRequestError("At least one field must be provided for update")
        
        # Update the wheel
        updated_wheel = WheelRepository.update_wheel(
            tenant_context['tenant_id'], 
            wheel_id, 
            updates
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(decimal_to_float(updated_wheel))
        }
        
    except (BadRequestError, NotFoundError) as e:
        status_code = getattr(e, 'status_code', 400) if hasattr(e, 'status_code') else (404 if isinstance(e, NotFoundError) else 400)
        return {
            'statusCode': status_code,
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


@require_tenant_permission('delete_wheel')
def delete_wheel(event, context=None):
    """
    Delete a wheel and all its participants
    
    DELETE /v2/wheels/{wheel_id}
    """
    try:
        tenant_context = get_tenant_context(event)
        wheel_id = event.get('pathParameters', {}).get('wheel_id')
        
        if not wheel_id:
            raise BadRequestError("wheel_id is required")
        
        # Verify wheel exists and belongs to tenant (this will throw NotFoundError if not)
        WheelRepository.get_wheel(tenant_context['tenant_id'], wheel_id)
        
        # Delete wheel and all participants
        WheelRepository.delete_wheel(tenant_context['tenant_id'], wheel_id)
        
        return {
            'statusCode': 204,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': ''
        }
        
    except (BadRequestError, NotFoundError) as e:
        status_code = getattr(e, 'status_code', 400) if hasattr(e, 'status_code') else (404 if isinstance(e, NotFoundError) else 400)
        return {
            'statusCode': status_code,
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


@require_tenant_permission('manage_participants')
def reset_wheel_weights(event, context=None):
    """
    Reset all participant weights in a wheel to their original values
    
    POST /v2/wheels/{wheel_id}/reset
    
    {
      "reason": "Starting fresh for new sprint"
    }
    """
    try:
        tenant_context = get_tenant_context(event)
        wheel_id = event.get('pathParameters', {}).get('wheel_id')
        body_str = event.get('body', '{}')
        
        # Body is already parsed by main lambda handler
        body = body_str if isinstance(body_str, dict) else (json.loads(body_str) if body_str else {})
        
        if not wheel_id:
            raise BadRequestError("wheel_id is required")
        
        # Verify wheel exists and belongs to tenant
        WheelRepository.get_wheel(tenant_context['tenant_id'], wheel_id)
        
        # Get all participants
        participants = ParticipantRepository.list_wheel_participants(
            tenant_context['tenant_id'], 
            wheel_id
        )
        
        if not participants:
            raise BadRequestError("Wheel has no participants to reset")
        
        # Helper function to get sub-wheel size (V1 compatibility)
        def get_sub_wheel_size(participant_name, tenant_id):
            """
            Look for a wheel with the same name as the participant and return its participant count.
            This implements the same logic as V1's get_sub_wheel_size function.
            """
            try:
                # Look for wheels in the same tenant with matching name
                tenant_wheels = WheelRepository.list_tenant_wheels(tenant_id)
                for wheel in tenant_wheels:
                    if wheel.get('wheel_name') == participant_name:
                        # Get participants for this wheel to count them
                        wheel_participants = ParticipantRepository.list_wheel_participants(
                            tenant_id, 
                            wheel['wheel_id']
                        )
                        participant_count = len(wheel_participants)
                        return participant_count if participant_count > 0 else 1
                return 1  # Default to 1 if no matching wheel found
            except:
                return 1  # Default to 1 on any error
        
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
            reset_weight = get_sub_wheel_size(participant['participant_name'], tenant_context['tenant_id'])
            reset_weight_decimal = Decimal(str(reset_weight))
            
            update_data = {
                'participant_id': participant['participant_id'],
                'participant_name': participant['participant_name'],  # Preserve name
                'participant_url': participant.get('participant_url', ''),  # Preserve URL
                'weight': reset_weight_decimal,  # Reset using V1 sub-wheel logic
                'original_weight': reset_weight_decimal,  # Store this as the new original weight
                'selection_count': Decimal('0'),  # Reset selection count as Decimal
                'status': participant.get('status', 'ACTIVE'),  # Preserve status
                'created_at': participant.get('created_at'),  # Preserve creation time
                'updated_at': get_utc_timestamp(),  # Add required updated_at timestamp
                # Note: last_selected_at is intentionally omitted to be set to None/removed
            }
            participant_updates.append(update_data)
        
        # Batch update all participants
        ParticipantRepository.batch_update_participants(
            tenant_context['tenant_id'],
            wheel_id,
            participant_updates
        )
        
        # Update wheel's reset information
        # Note: Don't set last_spun_at to None - just remove those fields and reset spins
        WheelRepository.update_wheel(
            tenant_context['tenant_id'],
            wheel_id,
            {
                'total_spins': 0
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'Reset weights for {len(participants)} participants',
                'participants_affected': len(participants),
                'reason': body.get('reason', 'Manual reset')
            })
        }
        
    except (BadRequestError, NotFoundError) as e:
        status_code = getattr(e, 'status_code', 400) if hasattr(e, 'status_code') else (404 if isinstance(e, NotFoundError) else 400)
        return {
            'statusCode': status_code,
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


# Export Lambda handler functions
lambda_handlers = {
    'list_tenant_wheels': list_tenant_wheels,
    'create_wheel': create_wheel,
    'get_wheel': get_wheel,
    'update_wheel': update_wheel,
    'delete_wheel': delete_wheel,
    'reset_wheel_weights': reset_wheel_weights
}
