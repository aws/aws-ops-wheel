#  Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License").
#  You may not use this file except in compliance with the License.
#  A copy of the License is located at
#
#      http://aws.amazon.com/apache2.0/
#
#  or in the "license" file accompanying this file. This file is distributed
#  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#  express or implied. See the License for the specific language governing
#  permissions and limitations under the License.

import pytest
import json
import choice_algorithm
import wheel
import wheel_participant

from utils import WheelParticipant
from boto3.dynamodb.conditions import Key
from base import BadRequestError
import random

epsilon = 1E-6


@pytest.fixture(autouse=True)
def setup_data(mock_dynamodb):
    names = ['Dan', 'Bob', 'Steve', 'Jerry', 'Frank', 'Alexa', 'Jeff']

    created_wheel = json.loads(wheel.create_wheel({'body': {'name': 'Test Wheel'}})['body'])

    create_participant_events = [{
        'pathParameters': {
            'wheel_id': created_wheel['id']
        },
        'body': {
            'name': name,
            'url': 'https://amazon.com'
        }
    } for name in names]

    created_participants = [json.loads(wheel_participant.create_participant(event)['body']) for event in
                            create_participant_events]

    # Reloads the wheel with updated participant count
    return {
        'wheel': json.loads(wheel.get_wheel({'body': {}, 'pathParameters': {'wheel_id': created_wheel['id']}})['body']),
        'participants': created_participants
    }


def test_suggest_participant(mock_dynamodb, setup_data):
    participant_ids = [participant['id'] for participant in setup_data['participants']]
    assert choice_algorithm.suggest_participant(setup_data['wheel']) in participant_ids


def test_suggest_participant_no_participants(mock_dynamodb):
    wheel = {'participant_count': 0}
    with pytest.raises(BadRequestError):
        choice_algorithm.suggest_participant(wheel)


def test_select_participant(mock_dynamodb, setup_data, mock_participant_table):
    participant_to_select = setup_data['participants'][0]
    choice_algorithm.select_participant(setup_data['wheel'], participant_to_select)

    participants = mock_participant_table.query(
        KeyConditionExpression=Key('wheel_id').eq(setup_data['wheel']['id']))['Items']
    selected_participant = [participant for participant in participants
                            if participant['id'] == participant_to_select['id']][0]

    assert selected_participant['weight'] == 0
    assert abs(sum([participant['weight'] for participant in participants]) - len(participants)) < epsilon


def test_selection_cycle(mock_dynamodb, setup_data, mock_participant_table):
    def get_participant_with_id(participants, target_id):
        for p in participants:
            if p['id'] == target_id:
                return p
        return None

    rngstate = random.getstate()
    random.seed(0) # Make the (otherwise pseudorandom) test repeatable.

    participants = WheelParticipant.scan({})['Items']
    wheel = setup_data['wheel']
    total_weight_of_chosens = 0
    num_iterations = 200

    distro = {}
    for participant in participants:
        distro[participant['name']] = 0

    for _ in range(0, num_iterations):

        chosen_id = choice_algorithm.suggest_participant(wheel)

        chosen_was = get_participant_with_id(participants, chosen_id)
        chosen_was_weight = chosen_was['weight']

        distro[chosen_was['name']] = distro[chosen_was['name']] + 1

        choice_algorithm.select_participant(wheel, chosen_was)

        participants = WheelParticipant.scan({})['Items']

        chosen_now = get_participant_with_id(participants, chosen_id)
        chosen_now_weight = chosen_now['weight']

        assert chosen_was_weight > 0.0
        assert chosen_now_weight == 0
        total_weight_of_chosens += chosen_was_weight

        assert abs(sum([participant['weight'] for participant in participants]) - len(participants)) < epsilon

    # Must match human-inspected reasonable values for the RNG seed defined above for number of times
    # each participant was chosen, and the total weight of participants selected. These are a rough
    # equivalent to ensuring that the sequence of chosen participants matches the observed test run.
    dv = list(distro.values())
    list.sort(dv)
    human_observed_selection_counts = [23, 25, 26, 28, 29, 33, 36]
    human_observed_total_weight = 319.4813047089203
    assert dv == human_observed_selection_counts
    assert abs(float(total_weight_of_chosens) - human_observed_total_weight) < epsilon

    # Put things back the way they were.
    random.setstate(rngstate)


def test_reset_wheel(mock_dynamodb, setup_data, mock_participant_table):
    choice_algorithm.select_participant(setup_data['wheel'], setup_data['participants'][0])
    choice_algorithm.reset_wheel(setup_data['wheel'])

    updated_participants = mock_participant_table.query(
        KeyConditionExpression=Key('wheel_id').eq(setup_data['wheel']['id']))['Items']
    participant_weights = [participant['weight'] for participant in updated_participants]

    for weight in participant_weights:
        assert weight == 1
