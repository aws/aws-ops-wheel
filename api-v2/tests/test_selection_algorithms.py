#  Unit Tests for Selection Algorithms - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
import json
from decimal import Decimal
from unittest.mock import patch, Mock

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import BadRequestError, NotFoundError
from selection_algorithms import (
    suggest_participant_legacy, calculate_selection_probabilities,
    apply_single_selection_weight_redistribution, suggest_participant,
    get_selection_probabilities
)
from utils_v2 import get_uuid, get_utc_timestamp, create_wheel_group_wheel_id


# Core Selection Logic Tests (6 tests)

def test_suggest_participant_legacy(isolated_wheel_group_setup):
    """Test single participant selection using legacy algorithm"""
    setup = isolated_wheel_group_setup
    participants = setup['participants']
    
    # Test selection
    selected = suggest_participant_legacy(participants)
    
    assert selected is not None
    assert 'participant_id' in selected
    assert 'participant_name' in selected
    assert selected['participant_id'] in [p['participant_id'] for p in participants]


def test_suggest_participant_no_participants(mock_participants_table, sample_wheel_group_data):
    """Test selection with empty wheel raises error"""
    empty_participants = []
    
    with pytest.raises(BadRequestError, match="No participants available for selection"):
        suggest_participant_legacy(empty_participants)


def test_calculate_selection_probabilities(isolated_wheel_group_setup):
    """Test probability calculation for all participants"""
    setup = isolated_wheel_group_setup
    participants = setup['participants']
    
    probabilities = calculate_selection_probabilities(participants)
    
    assert len(probabilities) == 3  # Setup creates 3 participants
    
    # Check probability structure - returns dict mapping participant_id to probability
    for participant in participants:
        participant_id = participant['participant_id']
        assert participant_id in probabilities
        assert 0 <= probabilities[participant_id] <= 1
    
    # Check probabilities sum to 1 (with some tolerance for floating point)
    total_probability = sum(probabilities.values())
    assert abs(total_probability - 1.0) < 0.001


def test_suggest_participant_with_rigging(isolated_wheel_group_setup):
    """Test rigged selection returns correct participant"""
    setup = isolated_wheel_group_setup
    participants = setup['participants']
    
    # Create rigging data for specific participant
    rigged_participant_id = participants[1]['participant_id']
    rigging_data = {
        'rigged_participant_id': rigged_participant_id,
        'rigging_reason': 'Test rigging'
    }
    
    # Test rigged selection
    selected = suggest_participant_legacy(participants, rigging_data)
    
    assert selected['participant_id'] == rigged_participant_id


def test_suggest_participant_rigging_not_found(isolated_wheel_group_setup):
    """Test rigged selection falls back when rigged participant doesn't exist"""
    setup = isolated_wheel_group_setup
    participants = setup['participants']
    
    # Create rigging data for non-existent participant
    non_existent_id = get_uuid()
    rigging_data = {
        'rigged_participant_id': non_existent_id,
        'rigging_reason': 'Test rigging'
    }
    
    # Test fallback to normal selection
    selected = suggest_participant_legacy(participants, rigging_data)
    
    assert selected is not None
    assert selected['participant_id'] != non_existent_id  # Should fall back
    assert selected['participant_id'] in [p['participant_id'] for p in participants]


def test_selection_statistical_distribution(isolated_wheel_group_setup, mock_participants_table):
    """Test statistical distribution matches weights (adapted from v1)"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
    
    # Set different weights for participants
    participants = setup['participants']
    weights = [Decimal('4.0'), Decimal('2.0'), Decimal('1.0')]  # 4:2:1 ratio
    
    for i, participant in enumerate(participants):
        mock_participants_table.update_item(
            Key={
                'wheel_group_wheel_id': wheel_group_wheel_id,
                'participant_id': participant['participant_id']
            },
            UpdateExpression='SET weight = :weight',
            ExpressionAttributeValues={':weight': weights[i]}
        )
        # Update the participant weight in our test data too
        participant['weight'] = float(weights[i])
    
    # Run multiple selections to test distribution
    selections = {}
    num_trials = 500  # Increased for better statistical reliability
    
    for _ in range(num_trials):
        selected = suggest_participant_legacy(participants)
        participant_id = selected['participant_id']
        selections[participant_id] = selections.get(participant_id, 0) + 1
    
    # Check that distribution roughly matches weights (4:2:1 = 57%:29%:14%)
    total_weight = sum(weights)
    expected_ratios = [float(w / total_weight) for w in weights]
    
    for i, participant in enumerate(participants):
        actual_ratio = selections.get(participant['participant_id'], 0) / num_trials
        expected_ratio = expected_ratios[i]
        
        # Allow 15% tolerance for randomness with increased sample size
        tolerance = 0.15
        assert abs(actual_ratio - expected_ratio) < tolerance, \
            f"Participant {i}: expected {expected_ratio:.2f}, got {actual_ratio:.2f} (tolerance: {tolerance})"


# Weight Redistribution Tests (3 tests)

def test_apply_single_selection_weight_redistribution(isolated_wheel_group_setup):
    """Test weight redistribution logic after selection"""
    setup = isolated_wheel_group_setup
    participants = setup['participants'].copy()  # Make a copy to avoid modifying original
    
    selected_participant = participants[0]
    original_weight = float(selected_participant['weight'])
    
    # Apply weight redistribution
    apply_single_selection_weight_redistribution(participants, selected_participant)
    
    # Selected participant should have 0 weight (conservation rule)
    assert participants[0]['weight'] == Decimal('0')
    
    # Other participants should have increased weight
    for i in range(1, len(participants)):
        assert float(participants[i]['weight']) > 1.0
    
    # Total weight should be conserved
    total_new_weight = sum(float(p['weight']) for p in participants)
    total_original_weight = 3.0  # 3 participants with weight 1.0 each
    assert abs(total_new_weight - total_original_weight) < 0.001


def test_weight_redistribution_single_participant():
    """Test weight redistribution with only one participant"""
    # Create single participant
    participants = [{
        'participant_id': get_uuid(),
        'participant_name': 'Solo Participant',
        'weight': Decimal('1.0')
    }]
    
    selected_participant = participants[0]
    original_weight = float(selected_participant['weight'])
    
    # Apply redistribution
    apply_single_selection_weight_redistribution(participants, selected_participant)
    
    # Single participant should keep same weight (no redistribution possible)
    assert float(participants[0]['weight']) == original_weight


def test_weight_conservation(isolated_wheel_group_setup):
    """Test that total weight is always conserved"""
    setup = isolated_wheel_group_setup
    base_participants = setup['participants']
    
    # Test with various weight distributions
    test_weights = [
        [Decimal('1.0'), Decimal('1.0'), Decimal('1.0')],
        [Decimal('2.0'), Decimal('1.0'), Decimal('0.5')],
        [Decimal('5.0'), Decimal('3.0'), Decimal('2.0')]
    ]
    
    for weights in test_weights:
        for i, selected_idx in enumerate([0, 1, 2]):  # Test selecting each participant
            # Create test participants with specific weights
            participants = []
            for j, participant in enumerate(base_participants):
                p = participant.copy()
                p['weight'] = weights[j]
                participants.append(p)
            
            selected_participant = participants[selected_idx]
            total_original = sum(float(w) for w in weights)
            
            # Apply redistribution
            apply_single_selection_weight_redistribution(participants, selected_participant)
            
            total_redistributed = sum(float(p['weight']) for p in participants)
            
            assert abs(total_original - total_redistributed) < 0.001, \
                f"Weight not conserved: {total_original} -> {total_redistributed}"


# API Endpoints Tests (6 tests)

def mock_middleware_success(event, context):
    """Mock middleware that adds wheel_group_context to event"""
    wheel_group_context = event.get('test_wheel_group_context', {})
    event['wheel_group_context'] = wheel_group_context
    return event


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('selection_algorithms.get_wheel_group_context')
def test_suggest_participant_endpoint(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test suggest participant API endpoint with middleware"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    # Mock wheel group context
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True, 'spin_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    # Create API Gateway event with context parameter
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': '{}',
        'requestContext': {'authorizer': {}},
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context  # Add for our mock middleware
    }
    
    # Create mock Lambda context
    mock_lambda_context = Mock()
    mock_lambda_context.aws_request_id = 'test-request-id'
    
    response = suggest_participant(event, context=mock_lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'selected_participant' in body
    assert 'selection_type' in body
    assert 'probabilities' in body
    assert 'changes_applied' in body
    assert 'participant_id' in body['selected_participant']


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('selection_algorithms.get_wheel_group_context')
def test_suggest_participant_apply_changes(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test selection with weight redistribution applied"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True, 'spin_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': '{"apply_changes": true}',
        'requestContext': {'authorizer': {}},
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    mock_lambda_context = Mock()
    mock_lambda_context.aws_request_id = 'test-request-id'
    
    response = suggest_participant(event, context=mock_lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['changes_applied'] is True
    assert 'selected_participant' in body


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('selection_algorithms.get_wheel_group_context')  
def test_suggest_participant_permission_required(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test that proper permissions are required"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    # Test with insufficient permissions
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}  # Missing 'spin_wheel'
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': '{}',
        'requestContext': {'authorizer': {}},
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    mock_lambda_context = Mock()
    mock_lambda_context.aws_request_id = 'test-request-id'
    
    response = suggest_participant(event, context=mock_lambda_context)
    
    # Should return 403 for insufficient permissions
    assert response['statusCode'] == 403


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('selection_algorithms.get_wheel_group_context')
def test_get_selection_probabilities_endpoint(mock_context, mock_middleware, isolated_wheel_group_setup):
    """Test selection probabilities API endpoint"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'requestContext': {'authorizer': {}},
        'httpMethod': 'GET',
        'test_wheel_group_context': wheel_group_context
    }
    
    mock_lambda_context = Mock()
    mock_lambda_context.aws_request_id = 'test-request-id'
    
    response = get_selection_probabilities(event, context=mock_lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'wheel_id' in body
    assert 'participants' in body
    assert len(body['participants']) == 3  # Setup creates 3 participants
    
    for participant in body['participants']:
        assert 'participant_id' in participant
        assert 'selection_probability' in participant
        assert 0 <= participant['selection_probability'] <= 1


def test_cross_wheel_group_isolation(isolated_wheel_group_setup, mock_wheels_table, mock_participants_table):
    """Test that selection properly isolates between wheel groups"""
    setup = isolated_wheel_group_setup
    
    # Create second wheel group with its own wheel and participants
    other_wheel_group_id = get_uuid()
    other_wheel_id = get_uuid()
    other_wheel_group_wheel_id = create_wheel_group_wheel_id(other_wheel_group_id, other_wheel_id)
    
    # Create wheel in other group
    other_wheel = {
        'wheel_group_id': other_wheel_group_id,  
        'wheel_id': other_wheel_id,
        'wheel_name': 'Other Wheel',
        'created_by': get_uuid(),
        'created_at': get_utc_timestamp(),
        'settings': {'allow_rigging': True},
        'participant_count': 1
    }
    mock_wheels_table.put_item(Item=other_wheel)
    
    # Create participant in other group
    other_participant = {
        'wheel_group_wheel_id': other_wheel_group_wheel_id,
        'participant_id': get_uuid(),
        'participant_name': 'Other Participant',
        'weight': Decimal('1.0'),
        'original_weight': Decimal('1.0'),
        'created_at': get_utc_timestamp(),
        'selection_count': 0
    }
    mock_participants_table.put_item(Item=other_participant)
    
    # Test selection from original wheel group participants only
    original_participants = setup['participants']
    selected = suggest_participant_legacy(original_participants)
    
    # Should not select participant from other wheel group
    assert selected['participant_id'] != other_participant['participant_id']
    assert selected['participant_id'] in [p['participant_id'] for p in original_participants]


@patch('wheel_group_middleware.wheel_group_middleware', side_effect=mock_middleware_success)
@patch('selection_algorithms.get_wheel_group_context')
def test_suggest_participant_rigging_visibility(mock_context, mock_middleware, isolated_wheel_group_setup, mock_wheels_table):
    """Test hidden vs visible rigging in API responses"""
    setup = isolated_wheel_group_setup
    wheel_group_id = setup['wheel_group']['wheel_group_id']
    wheel_id = setup['wheels'][0]['wheel_id']
    participants = setup['participants']
    
    wheel_group_context = {
        'wheel_group_id': wheel_group_id,
        'user_id': get_uuid(),
        'permissions': {'view_wheels': True, 'spin_wheel': True}
    }
    
    mock_context.return_value = wheel_group_context
    
    # Test with hidden rigging
    rigged_participant_id = participants[0]['participant_id']
    mock_wheels_table.update_item(
        Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id},
        UpdateExpression='SET rigging = :rigging',
        ExpressionAttributeValues={
            ':rigging': {
                'rigged_participant_id': rigged_participant_id,
                'rigging_reason': 'Hidden test',
                'hidden': True
            }
        }
    )
    
    event = {
        'pathParameters': {'wheel_id': wheel_id},
        'body': '{}',
        'requestContext': {'authorizer': {}},
        'httpMethod': 'POST',
        'test_wheel_group_context': wheel_group_context
    }
    
    mock_lambda_context = Mock()
    mock_lambda_context.aws_request_id = 'test-request-id'
    
    response = suggest_participant(event, context=mock_lambda_context)
    body = json.loads(response['body'])
    
    # Should not expose rigging details in response when hidden
    assert body['rigged'] is False  # Hidden rigging
    assert body['selected_participant']['participant_id'] == rigged_participant_id
    
    # Test with visible rigging
    mock_wheels_table.update_item(
        Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id},
        UpdateExpression='SET rigging = :rigging',
        ExpressionAttributeValues={
            ':rigging': {
                'rigged_participant_id': rigged_participant_id,
                'rigging_reason': 'Visible test',
                'hidden': False
            }
        }
    )
    
    event['test_wheel_group_context'] = wheel_group_context  # Update context for second call
    
    response = suggest_participant(event, context=mock_lambda_context)
    body = json.loads(response['body'])
    
    # Should expose rigging when not hidden
    assert body['rigged'] is True
