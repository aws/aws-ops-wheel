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
import choice_algorithm, wheel, wheel_participant
from boto3.dynamodb.conditions import Key
from base import BadRequestError


@pytest.fixture(autouse=True)
def setup_data(mock_dynamodb):
    created_wheel = json.loads(wheel.create_wheel({'body': {'name': 'Test Wheel'}})['body'])

    create_participant_events = [{
        'pathParameters': {
            'wheel_id': created_wheel['id']
        },
        'body': {
            'name': name,
            'url': 'https://amazon.com'
        }
    } for name in ['Dan', 'Alexa', 'Jeff']]

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

    updated_participants = mock_participant_table.query(KeyConditionExpression=Key('wheel_id').eq(setup_data['wheel']['id']))['Items']
    selected_participant = [participant for participant in updated_participants if participant['id'] == participant_to_select['id']][0]
    other_participants_weights = [participant['weight'] for participant in updated_participants if participant['id'] != participant_to_select['id']]

    assert selected_participant['weight'] == 0
    for weight in other_participants_weights:
        assert weight == 1.5


def test_reset_wheel(mock_dynamodb, setup_data, mock_participant_table):
    choice_algorithm.select_participant(setup_data['wheel'], setup_data['participants'][0])
    choice_algorithm.reset_wheel(setup_data['wheel'])

    updated_participants = mock_participant_table.query(KeyConditionExpression=Key('wheel_id').eq(setup_data['wheel']['id']))['Items']
    participant_weights = [participant['weight'] for participant in updated_participants]

    for weight in participant_weights:
        assert weight == 1
