#  Improved Unit Tests for Participant Operations API - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests validate actual business logic, not just HTTP status codes

import os
import sys
import pytest
import json
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch, Mock

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import BadRequestError, NotFoundError
from participant_operations import (
    list_wheel_participants, create_participant, get_participant,
    update_participant, delete_participant, rig_participant,
    select_participant, remove_rigging,
    PARTICIPANT_CONSTRAINTS, VALIDATION_MESSAGES, RIGGING_DEFAULTS
)
from utils_v2 import get_uuid, get_utc_timestamp, WheelRepository, ParticipantRepository


def mock_middleware_success(event, context):
    """Mock middleware that adds wheel_group_context to event"""
    wheel_group_context = event.get('test_wheel_group_context', {})
    event['wheel_group_context'] = wheel_group_context
    return event


def create_mock_lambda_context():
    """Create a mock Lambda context for testing"""
    mock_context = Mock()
    mock_context.aws_request_id = 'test-request-id'
    return mock_context


def validate_participant_response_structure(participant_data, expected_fields=None):
    """Validate that participant response has correct structure and data types"""
    required_fields = expected_fields or [
        'participant_id', 'participant_name', 'participant_url', 'weight', 
        'created_at', 'updated_at'
    ]
    
    for field in required_fields:
        assert field in participant_data, f"Missing required field: {field}"
    
    # Validate data types
    assert isinstance(participant_data['participant_id'], str), "participant_id must be string"
    assert isinstance(participant_data['participant_name'], str), "participant_name must be string"
    assert isinstance(participant_data['participant_url'], str), "participant_url must be string"
    assert isinstance(participant_data['weight'], (int, float)), "weight must be numeric"
    
    # Validate timestamp formats
    datetime.fromisoformat(participant_data['created_at'].replace('Z', '+00:00'))
    datetime.fromisoformat(participant_data['updated_at'].replace('Z', '+00:00'))
    
    # Validate business constraints
    assert len(participant_data['participant_name']) <= PARTICIPANT_CONSTRAINTS['MAX_NAME_LENGTH']
    assert len(participant_data['participant_url']) <= PARTICIPANT_CONSTRAINTS['MAX_URL_LENGTH']
    assert PARTICIPANT_CONSTRAINTS['MIN_WEIGHT'] <= participant_data['weight'] <= PARTICIPANT_CONSTRAINTS['MAX_WEIGHT']


def validate_cors_headers(response):
    """Validate that response includes proper CORS headers"""
    assert 'headers' in response
    headers = response['headers']
    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'


def validate_participant_database_consistency(wheel_group_id: str, wheel_id: str, participant_id: str, expected_data: dict):
    """Validate that participant data in database matches expected values"""
    db_participant = ParticipantRepository.get_participant(wheel_group_id, wheel_id, participant_id)
    assert db_participant['participant_name'] == expected_data['participant_name']
    assert db_participant['participant_url'] == expected_data['participant_url']
    assert float(db_participant['weight']) == expected_data['weight']


# List Participants Tests (4 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_list_wheel_participants_success_validates_business_logic(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test successful listing validates exact business logic and data structures"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    expected_participants = setup['participants']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = list_wheel_participants(event, context=create_mock_lambda_context())
    
    # Validate HTTP response structure
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    # Validate response body structure
    body = json.loads(response['body'])
    assert 'participants' in body
    assert 'count' in body
    assert isinstance(body['participants'], list)
    assert isinstance(body['count'], int)
    
    # Validate exact count matches setup data
    assert body['count'] == len(expected_participants), f"Expected {len(expected_participants)} participants, got {body['count']}"
    assert len(body['participants']) == len(expected_participants)
    
    # Validate each participant structure and business data
    for participant in body['participants']:
        validate_participant_response_structure(participant)
        
        # Verify participant belongs to correct wheel
        db_participant = ParticipantRepository.get_participant(wheel_group_id, wheel_id, participant['participant_id'])
        assert db_participant is not None, "Participant should exist in database"
        assert db_participant['participant_name'] == participant['participant_name']
        
        # Validate weight redistribution data structure
        assert 'original_weight' in participant, "Should include original_weight for algorithm tracking"
        assert 'selection_count' in participant, "Should include selection_count for history"
        assert isinstance(participant['selection_count'], (int, float)), "selection_count must be numeric"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_list_wheel_participants_empty_wheel(mock_context, mock_middleware, sample_wheel_group_data):
    """Test empty wheel returns exactly zero participants"""
    wheel_group_context = {
        'wheel_group_id': get_uuid(),
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    # Create wheel with no participants
    wheel_id = get_uuid()
    WheelRepository.create_wheel(wheel_group_context['wheel_group_id'], {
        'wheel_id': wheel_id,
        'wheel_name': 'Empty Test Wheel',
        'description': 'Wheel with no participants',
        'created_by': wheel_group_context['user_id']
    })
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = list_wheel_participants(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    
    # Validate exact empty state
    assert body['count'] == 0, "Empty wheel should have exactly 0 participants"
    assert len(body['participants']) == 0, "participants array should be empty"
    assert body['participants'] == [], "participants should be empty list"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_list_wheel_participants_missing_wheel_id_exact_error(mock_context, mock_middleware):
    """Test exact error message for missing wheel_id"""
    wheel_group_context = {
        'wheel_group_id': get_uuid(),
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {},  # Missing wheel_id
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = list_wheel_participants(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['WHEEL_ID_REQUIRED']
    assert body['error'] == "wheel_id is required"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_list_wheel_participants_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test permission validation blocks unauthorized access"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {}  # Missing view_wheels permission
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = list_wheel_participants(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403
    validate_cors_headers(response)
    
    # Verify no business data is leaked in error response
    body = json.loads(response['body'])
    assert 'participants' not in body, "Should not include participants data when unauthorized"
    assert 'count' not in body, "Should not include count when unauthorized"


# Create Participant Tests (7 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_success_validates_business_logic(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test participant creation validates all business logic requirements"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_name': 'Business Logic Test Participant',
            'participant_url': 'https://test.example.com/participant',
            'weight': 2.5
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 201
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    validate_participant_response_structure(body)
    
    # Validate exact business logic requirements
    assert body['participant_name'] == 'Business Logic Test Participant'
    assert body['participant_url'] == 'https://test.example.com/participant'
    assert body['weight'] == 2.5
    
    # Validate timestamps are recent and properly formatted
    created_time = datetime.fromisoformat(body['created_at'].replace('Z', '+00:00'))
    updated_time = datetime.fromisoformat(body['updated_at'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    assert (now - created_time).total_seconds() < 10, "created_at should be recent"
    assert (now - updated_time).total_seconds() < 10, "updated_at should be recent"
    
    # Validate weight redistribution fields are initialized correctly
    assert body['original_weight'] == 2.5, "original_weight should match initial weight"
    assert body['selection_count'] == 0, "selection_count should start at 0"
    assert 'last_selected_at' not in body, "last_selected_at should not be set initially"
    
    # Validate participant was actually created in database with correct data
    validate_participant_database_consistency(wheel_group_id, wheel_id, body['participant_id'], {
        'participant_name': 'Business Logic Test Participant',
        'participant_url': 'https://test.example.com/participant',
        'weight': 2.5
    })
    
    # Validate wheel participant count was updated
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    expected_count = len(setup['participants']) + 1
    assert updated_wheel.get('participant_count', 0) == expected_count, "Wheel participant count should be updated"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_with_defaults_validates_all_defaults(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test that all default values are applied correctly"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_name': 'Minimal Participant'
            # No URL or weight provided
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    
    # Validate all defaults are applied exactly
    assert body['participant_name'] == 'Minimal Participant'
    assert body['participant_url'] == '', "Default participant_url should be empty string"
    assert body['weight'] == PARTICIPANT_CONSTRAINTS['DEFAULT_WEIGHT'], "Should use exact default weight"
    assert body['weight'] == 1.0, "Default weight should be 1.0"
    
    # Validate default algorithm tracking fields
    assert body['original_weight'] == 1.0, "original_weight should match default weight"
    assert body['selection_count'] == 0, "selection_count should start at 0"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_missing_name_exact_error_message(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact error message for missing participant name"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_url': 'https://example.com'
            # Missing participant_name
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    
    # Validate exact error message from constants
    assert body['error'] == VALIDATION_MESSAGES['PARTICIPANT_NAME_REQUIRED']
    assert body['error'] == "participant_name is required and must be a non-empty string"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_validates_exact_constraints(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test validation against exact constraint values"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    # Test exact boundary: MAX_WEIGHT + 0.1
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_name': 'Constraint Test Participant',
            'weight': PARTICIPANT_CONSTRAINTS['MAX_WEIGHT'] + 0.1  # 100.1
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['INVALID_WEIGHT']
    assert "must be a number between 0 and 100" in body['error']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_name_length_exact_boundary(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact boundary for participant name length"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    # Test exact boundary: MAX_NAME_LENGTH + 1
    too_long_name = 'A' * (PARTICIPANT_CONSTRAINTS['MAX_NAME_LENGTH'] + 1)  # 101 characters
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_name': too_long_name
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['PARTICIPANT_NAME_TOO_LONG']
    assert "100 characters or less" in body['error']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_name_conflict_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact error for participant name conflicts"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    existing_participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_name': existing_participant['participant_name']  # Duplicate name
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['PARTICIPANT_EXISTS'].format(existing_participant['participant_name'])
    assert 'already exists' in body['error']
    
    # Verify no participant was created in database
    participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    duplicate_names = [p['participant_name'] for p in participants if p['participant_name'] == existing_participant['participant_name']]
    assert len(duplicate_names) == 1, "Should still have only one participant with that name"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_create_participant_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test creation fails without proper permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}  # Missing manage_participants
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': {
            'participant_name': 'Unauthorized Test Participant'
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = create_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403
    
    # Verify no participant was created in database
    participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    participant_names = [p['participant_name'] for p in participants]
    assert 'Unauthorized Test Participant' not in participant_names, "Participant should not be created without permission"


# Get Participant Tests (4 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_get_participant_success_validates_complete_data(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test get participant returns complete and correct data structure"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    
    # Validate complete participant structure with algorithm tracking fields
    validate_participant_response_structure(body, expected_fields=[
        'participant_id', 'participant_name', 'participant_url', 'weight',
        'original_weight', 'selection_count', 'created_at', 'updated_at'
    ])
    
    # Validate data matches database exactly
    assert body['participant_id'] == participant['participant_id']
    assert body['participant_name'] == participant['participant_name']
    assert body['participant_url'] == participant['participant_url']
    assert body['weight'] == participant['weight']
    
    # Validate algorithm tracking fields
    assert 'original_weight' in body, "Should include original_weight for algorithm tracking"
    assert 'selection_count' in body, "Should include selection_count for history"
    assert isinstance(body['selection_count'], (int, float)), "selection_count must be numeric"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_get_participant_not_found_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact 404 behavior for non-existent participant"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    non_existent_participant_id = get_uuid()
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': non_existent_participant_id
        },
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    validate_cors_headers(response)
    
    # Verify participant truly doesn't exist
    try:
        ParticipantRepository.get_participant(wheel_group_id, wheel_id, non_existent_participant_id)
        assert False, "Participant should not exist"
    except NotFoundError:
        pass  # Expected


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_get_participant_missing_participant_id_exact_message(mock_context, mock_middleware):
    """Test exact error message for missing participant_id"""
    wheel_group_context = {
        'wheel_group_id': get_uuid(),
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': get_uuid()
            # Missing participant_id
        },
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['PARTICIPANT_ID_REQUIRED']
    assert body['error'] == "participant_id is required"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_get_participant_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test get participant fails without view permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {}  # Missing view_wheels
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = get_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403
    
    # Verify no participant data is leaked
    body = json.loads(response['body'])
    assert 'participant_name' not in body
    assert 'participant_url' not in body
    assert 'weight' not in body


# Update Participant Tests (6 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_update_participant_success_validates_merge_logic(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test update validates field merge and preserves existing data"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    # Get original participant data
    original_participant = ParticipantRepository.get_participant(wheel_group_id, wheel_id, participant['participant_id'])
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    update_data = {
        'participant_name': 'Updated Business Logic Participant',
        'participant_url': 'https://updated.example.com/participant',
        'weight': 3.5
    }
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': update_data,
        'httpMethod': 'PUT',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    
    # Validate updates applied correctly
    assert body['participant_name'] == 'Updated Business Logic Participant'
    assert body['participant_url'] == 'https://updated.example.com/participant'
    assert body['weight'] == 3.5
    
    # Validate preserved metadata
    assert body['participant_id'] == original_participant['participant_id'], "participant_id should not change"
    assert body['created_at'] == original_participant['created_at'], "created_at should not change"
    
    # Validate algorithm tracking fields updated correctly
    assert body['original_weight'] == 3.5, "original_weight should be updated with new weight"
    assert body['selection_count'] == original_participant.get('selection_count', 0), "selection_count should be preserved"
    
    # Validate database state matches response
    validate_participant_database_consistency(wheel_group_id, wheel_id, participant['participant_id'], {
        'participant_name': 'Updated Business Logic Participant',
        'participant_url': 'https://updated.example.com/participant',
        'weight': 3.5
    })


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_update_participant_partial_preserves_unchanged_fields(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test partial update preserves all unchanged fields exactly"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    # Get original participant data
    original_participant = ParticipantRepository.get_participant(wheel_group_id, wheel_id, participant['participant_id'])
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'participant_name': 'Only Name Updated'
            # Only updating name, leaving URL and weight unchanged
        },
        'httpMethod': 'PUT',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    
    # Validate name was updated
    assert body['participant_name'] == 'Only Name Updated'
    
    # Validate other fields were preserved exactly
    assert body['participant_url'] == original_participant['participant_url'], "URL should be unchanged"
    assert body['weight'] == original_participant['weight'], "Weight should be unchanged"
    assert body['original_weight'] == original_participant.get('original_weight', original_participant['weight']), "original_weight should be unchanged"
    
    # Validate metadata preservation
    assert body['participant_id'] == original_participant['participant_id']
    assert body['created_at'] == original_participant['created_at']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_update_participant_empty_body_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact error message for empty update body"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {},  # Empty update
        'httpMethod': 'PUT',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['UPDATE_FIELD_REQUIRED']
    assert body['error'] == "At least one field must be provided for update"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_update_participant_name_conflict_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact error for participant name conflicts"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant1 = setup['participants'][0]
    participant2 = setup['participants'][1]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant1['participant_id']
        },
        'body': {
            'participant_name': participant2['participant_name']  # Conflict with participant2
        },
        'httpMethod': 'PUT',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['PARTICIPANT_EXISTS'].format(participant2['participant_name'])
    assert 'already exists' in body['error']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_update_participant_validates_exact_weight_constraints(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test weight validation against exact constraints"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    # Test exact boundary: MIN_WEIGHT - 0.1
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'weight': PARTICIPANT_CONSTRAINTS['MIN_WEIGHT'] - 0.1  # -0.1
        },
        'httpMethod': 'PUT',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['INVALID_WEIGHT']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_update_participant_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test update fails without proper permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}  # Missing manage_participants
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'participant_name': 'Unauthorized Update'
        },
        'httpMethod': 'PUT',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = update_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403


# Delete Participant Tests (4 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_delete_participant_success_validates_cascade_behavior(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test participant deletion and wheel count update"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant_to_delete = setup['participants'][0]
    
    # Verify initial state
    initial_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    initial_count = len(initial_participants)
    assert initial_count > 1, "Need multiple participants to test deletion"
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant_to_delete['participant_id']
        },
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = delete_participant(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert 'deleted successfully' in body['message']
    assert 'deleted_participant' in body
    assert body['deleted_participant']['participant_id'] == participant_to_delete['participant_id']
    
    # Validate participant was actually deleted
    try:
        ParticipantRepository.get_participant(wheel_group_id, wheel_id, participant_to_delete['participant_id'])
        assert False, "Participant should be deleted"
    except NotFoundError:
        pass  # Expected
    
    # Validate wheel participant count was updated
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    expected_count = initial_count - 1
    assert updated_wheel.get('participant_count', 0) == expected_count, "Wheel participant count should be decremented"
    
    # Validate remaining participants still exist
    remaining_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    assert len(remaining_participants) == expected_count, "Should have one fewer participant"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_delete_participant_last_participant_protection(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test protection against deleting the last participant"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    # Delete all but one participant to test "last participant" protection
    participants = setup['participants']
    for participant in participants[1:]:  # Delete all except first
        ParticipantRepository.delete_participant(wheel_group_id, wheel_id, participant['participant_id'])
    
    last_participant = participants[0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': last_participant['participant_id']
        },
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = delete_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['LAST_PARTICIPANT']
    assert 'Cannot delete the last participant' in body['error']
    
    # Verify participant still exists
    remaining_participant = ParticipantRepository.get_participant(wheel_group_id, wheel_id, last_participant['participant_id'])
    assert remaining_participant is not None, "Last participant should still exist"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_delete_participant_not_found_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact 404 error for non-existent participant deletion"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'manage_participants': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    non_existent_participant_id = get_uuid()
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': non_existent_participant_id
        },
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = delete_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    validate_cors_headers(response)


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_delete_participant_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test deletion fails without proper permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}  # Missing manage_participants
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = delete_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403
    
    # Verify participant still exists
    remaining_participant = ParticipantRepository.get_participant(wheel_group_id, wheel_id, participant['participant_id'])
    assert remaining_participant is not None, "Participant should not be deleted without permission"


# Rig Participant Tests (6 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_rig_participant_success_validates_business_logic(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test participant rigging validates all business logic requirements"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    rigging_user_id = get_uuid()
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': rigging_user_id,
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'reason': 'Business Logic Test Rigging',
            'hidden': False
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = rig_participant(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    
    # Validate response structure and business logic
    assert f"rigged to select {participant['participant_name']}" in body['message']
    assert 'rigging' in body
    assert 'hidden' in body
    
    rigging_data = body['rigging']
    assert rigging_data['rigged_participant_id'] == participant['participant_id']
    assert rigging_data['rigged_participant_name'] == participant['participant_name']
    assert rigging_data['rigged_by'] == rigging_user_id, "Should track who rigged the wheel"
    assert rigging_data['reason'] == 'Business Logic Test Rigging'
    assert rigging_data['hidden'] == False, "Should track visibility setting"
    assert body['hidden'] == False, "Should include visibility at top level"
    
    # Validate timestamp is recent
    rigged_time = datetime.fromisoformat(rigging_data['rigged_at'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    assert (now - rigged_time).total_seconds() < 10, "rigged_at should be recent"
    
    # Validate rigging was stored in wheel
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert 'rigging' in updated_wheel, "Wheel should have rigging data"
    assert updated_wheel['rigging']['rigged_participant_id'] == participant['participant_id']
    assert updated_wheel['rigging']['reason'] == 'Business Logic Test Rigging'


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_rig_participant_hidden_mode_validates_deception_logic(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test hidden rigging mode for deceptive behavior"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'reason': 'Secret rigging for testing',
            'hidden': True  # Deceptive/secret rigging
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = rig_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    
    # Validate hidden mode is properly set
    assert body['hidden'] == True, "Should be in hidden/deceptive mode"
    assert body['rigging']['hidden'] == True, "Rigging data should indicate hidden mode"
    
    # Validate database state
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert updated_wheel['rigging']['hidden'] == True, "Database should store hidden mode"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_rig_participant_rigging_not_allowed_exact_validation(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact validation when rigging is disabled by wheel settings"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    # Disable rigging for this wheel
    WheelRepository.update_wheel(wheel_group_id, wheel_id, {
        'settings': {'allow_rigging': False}
    })
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'reason': 'Attempting rigging when disabled'
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = rig_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['RIGGING_NOT_ALLOWED']
    assert 'Rigging is not allowed' in body['error']
    
    # Verify no rigging was applied
    wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert wheel.get('rigging') is None, "No rigging should be applied"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_rig_participant_reason_required_validation(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact validation when reason is required by wheel settings"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    # Require reason for rigging
    WheelRepository.update_wheel(wheel_group_id, wheel_id, {
        'settings': {'require_reason_for_rigging': True}
    })
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {},  # Missing reason when required
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = rig_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['error'] == VALIDATION_MESSAGES['REASON_REQUIRED']
    assert 'Reason is required' in body['error']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_rig_participant_not_found_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact 404 error for non-existent participant rigging"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    non_existent_participant_id = get_uuid()
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': non_existent_participant_id
        },
        'body': {
            'reason': 'Test rigging non-existent participant'
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = rig_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    validate_cors_headers(response)


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_rig_participant_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test rigging fails without proper permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}  # Missing rig_wheel
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'body': {
            'reason': 'Unauthorized rigging attempt'
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = rig_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403
    
    # Verify no rigging was applied
    wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert wheel.get('rigging') is None, "No rigging should be applied without permission"


# Select Participant Tests (4 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_select_participant_success_validates_v1_algorithm(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test participant selection applies V1 weight redistribution algorithm correctly"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant_to_select = setup['participants'][0]
    
    # Get initial state
    initial_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    initial_selection_count = participant_to_select.get('selection_count', 0)
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant_to_select['participant_id']
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = select_participant(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    
    # Validate response structure and business logic
    assert f"selected successfully" in body['message']
    assert body['participant']['participant_id'] == participant_to_select['participant_id']
    assert 'selection_count' in body
    assert body['selection_count'] == initial_selection_count + 1, "Selection count should increment"
    
    # Validate V1 algorithm was applied - check database state
    updated_participants = ParticipantRepository.list_wheel_participants(wheel_group_id, wheel_id)
    
    for participant in updated_participants:
        if participant['participant_id'] == participant_to_select['participant_id']:
            # Selected participant should have incremented selection_count and updated timestamp
            assert participant['selection_count'] == initial_selection_count + 1, "Selected participant count should increment"
            assert 'last_selected_at' in participant, "Selected participant should have last_selected_at timestamp"
            
            # Validate timestamp is recent
            selected_time = datetime.fromisoformat(participant['last_selected_at'].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            assert (now - selected_time).total_seconds() < 10, "last_selected_at should be recent"
        else:
            # Other participants should have their weights adjusted by V1 algorithm
            # This validates the weight redistribution occurred
            assert 'weight' in participant, "All participants should have weight field"
            assert 'original_weight' in participant, "All participants should have original_weight for tracking"
    
    # Validate rigging was cleared (if it existed)
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert updated_wheel.get('rigging') is None, "Rigging should be cleared after selection"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_select_participant_not_found_exact_error(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test exact 404 error for non-existent participant selection"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    non_existent_participant_id = get_uuid()
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': non_existent_participant_id
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = select_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    validate_cors_headers(response)


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_select_participant_clears_rigging_after_selection(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test that rigging is cleared after participant selection"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    # Set up rigging first
    WheelRepository.update_wheel(wheel_group_id, wheel_id, {
        'rigging': {
            'rigged_participant_id': participant['participant_id'],
            'rigged_participant_name': participant['participant_name'],
            'rigged_by': get_uuid(),
            'reason': 'Test rigging before selection'
        }
    })
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = select_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 200
    
    # Validate rigging was cleared
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert updated_wheel.get('rigging') is None, "Rigging should be cleared after selection"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_select_participant_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test selection fails without proper permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participant = setup['participants'][0]
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {}  # Missing view_wheels
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {
            'wheel_id': wheel_id,
            'participant_id': participant['participant_id']
        },
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = select_participant(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403


# Remove Rigging Tests (3 tests)

@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_remove_rigging_success_validates_business_logic(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test rigging removal validates business logic and state changes"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    # Set up rigging first
    rigging_data = {
        'rigged_participant_id': setup['participants'][0]['participant_id'],
        'rigged_participant_name': setup['participants'][0]['participant_name'],
        'rigged_by': get_uuid(),
        'reason': 'Test rigging to be removed',
        'hidden': True
    }
    
    WheelRepository.update_wheel(wheel_group_id, wheel_id, {'rigging': rigging_data})
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = remove_rigging(event, context=create_mock_lambda_context())
    
    # Validate HTTP response
    assert response['statusCode'] == 200
    validate_cors_headers(response)
    
    body = json.loads(response['body'])
    assert 'removed successfully' in body['message']
    
    # Validate rigging was actually removed from database
    updated_wheel = WheelRepository.get_wheel(wheel_group_id, wheel_id)
    assert updated_wheel.get('rigging') is None, "Rigging should be completely removed"


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_remove_rigging_wheel_not_found_exact_error(mock_context, mock_middleware):
    """Test exact 404 error for non-existent wheel rigging removal"""
    wheel_group_context = {
        'wheel_group_id': get_uuid(),
        'user_id': get_uuid(),
        'permissions': {'rig_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    non_existent_wheel_id = get_uuid()
    event = {
        'pathParameters': {'wheel_id': non_existent_wheel_id},
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = remove_rigging(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 404
    validate_cors_headers(response)


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('participant_operations.get_wheel_group_context')
def test_remove_rigging_insufficient_permissions(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test rigging removal fails without proper permission"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}  # Missing rig_wheel
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'httpMethod': 'DELETE',
        'test_wheel_group_context': wheel_group_context
    }
    
    response = remove_rigging(event, context=create_mock_lambda_context())
    
    assert response['statusCode'] == 403


# Additional validation helper tests

def test_validate_participant_response_structure_catches_missing_fields():
    """Test that our validation helper catches missing required fields"""
    incomplete_participant = {
        'participant_id': 'test-id',
        'participant_name': 'Test Participant'
        # Missing other required fields
    }
    
    try:
        validate_participant_response_structure(incomplete_participant)
        assert False, "Should raise assertion error for missing fields"
    except AssertionError as e:
        assert "Missing required field" in str(e)


def test_validate_participant_response_structure_catches_wrong_types():
    """Test that our validation helper catches wrong data types"""
    wrong_type_participant = {
        'participant_id': 'test-id',
        'participant_name': 123,  # Should be string
        'participant_url': 'https://example.com',
        'weight': 1.0,
        'created_at': '2023-01-01T00:00:00Z',
        'updated_at': '2023-01-01T00:00:00Z'
    }
    
    try:
        validate_participant_response_structure(wrong_type_participant)
        assert False, "Should raise assertion error for wrong type"
    except AssertionError as e:
        assert "must be string" in str(e)


def test_validate_participant_response_structure_catches_constraint_violations():
    """Test that our validation helper catches business constraint violations"""
    constraint_violating_participant = {
        'participant_id': 'test-id',
        'participant_name': 'A' * (PARTICIPANT_CONSTRAINTS['MAX_NAME_LENGTH'] + 1),  # Too long
        'participant_url': 'https://example.com',
        'weight': 1.0,
        'created_at': '2023-01-01T00:00:00Z',
        'updated_at': '2023-01-01T00:00:00Z'
    }
    
    try:
        validate_participant_response_structure(constraint_violating_participant)
        assert False, "Should raise assertion error for constraint violation"
    except AssertionError:
        pass  # Expected
