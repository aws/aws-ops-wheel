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
import wheel_participant
from utils import get_uuid, to_update_kwargs
from base import NotFoundError

WHEEL_ID = get_uuid()


@pytest.fixture(autouse=True)
def setup_wheel(mock_dynamodb, mock_wheel_table):
    wheel = {
        'id': WHEEL_ID,
        'name': 'Test Participant API Wheel',
        'participant_count': 0,
    }
    mock_wheel_table.put_item(Item=wheel)


def test_create_participant(mock_dynamodb, mock_participant_table):
    event = {
        'pathParameters': {
            'wheel_id': WHEEL_ID
        },
        'body': {
            'name': 'Dan',
            'url': 'https://amazon.com'
        }
    }

    response = wheel_participant.create_participant(event)
    created_participant = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert created_participant['name'] == event['body']['name']
    assert created_participant['url'] == event['body']['url']
    assert mock_participant_table.get_existing_item(Key={'id': created_participant['id'], 'wheel_id': WHEEL_ID})


def test_invalid_create_participant(mock_dynamodb):
    response = wheel_participant.create_participant({'body': {'name': '', 'url': ''}, 'pathParameters': {'wheel_id': WHEEL_ID}})

    assert response['statusCode'] == 400
    assert 'Participants require a name and url which must be at least 1 character in length' in response['body']


def test_delete_participant(mock_dynamodb, mock_participant_table):
    participants = [{
        'id': get_uuid(),
        'wheel_id': WHEEL_ID,
        'name': name,
        'url': 'https://amazon.com',
        'weight': 1
    } for name in ['Dan', 'Alexa']]

    with mock_participant_table.batch_writer() as batch:
        for participant in participants:
            batch.put_item(Item=participant)

    event = {'body': {}, 'pathParameters': {'wheel_id': WHEEL_ID, 'participant_id': participants[0]['id']}}
    response = wheel_participant.delete_participant(event)

    assert response['statusCode'] == 201
    with pytest.raises(NotFoundError):
        mock_participant_table.get_existing_item(Key={'id': participants[0]['id'], 'wheel_id': WHEEL_ID})


def test_list_participants(mock_dynamodb, mock_participant_table):
    participants = [{
        'id': get_uuid(),
        'wheel_id': WHEEL_ID,
        'name': name,
    } for name in ['Dan', 'Alexa']]

    with mock_participant_table.batch_writer() as batch:
        for participant in participants:
            batch.put_item(Item=participant)

    response = wheel_participant.list_participants({'body': {}, 'pathParameters': {'wheel_id': WHEEL_ID}})

    assert response['statusCode'] == 200
    assert 'Dan' in response['body'] and 'Alexa' in response['body']
    assert len(json.loads(response['body'])) == len(participants)


def test_update_participant(mock_dynamodb, mock_participant_table):
    participant = {
        'id': get_uuid(),
        'wheel_id': WHEEL_ID,
        'name': 'Old Name',
        'url': 'https://amazon.com',
        'weight': 1
    }
    mock_participant_table.put_item(Item=participant)

    event = {
        'pathParameters': {
            'wheel_id': WHEEL_ID,
            'participant_id': participant['id']
        },
        'body': {
            'name': 'New Name',
            'url': 'https://new-website.com'
        }
    }
    response = wheel_participant.update_participant(event)
    updated_participant = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert updated_participant['name'] == event['body']['name']
    assert updated_participant['url'] == event['body']['url']


def test_invalid_update_participant(mock_dynamodb, mock_participant_table):
    participant = {
        'id': get_uuid(),
        'wheel_id': WHEEL_ID,
        'name': 'Old Name',
        'url': 'https://amazon.com',
        'weight': 1
    }
    mock_participant_table.put_item(Item=participant)

    event = {
        'pathParameters': {
            'wheel_id': WHEEL_ID,
            'participant_id': participant['id']
        },
        'body': {
            'name': '',
            'url': ''
        }
    }
    response = wheel_participant.update_participant(event)

    assert response['statusCode'] == 400
    assert 'Participants names and urls must be at least 1 character in length' in response['body']


def test_select_participant_removes_rigging(mock_dynamodb, mock_participant_table, mock_wheel_table):
    mock_wheel_table.update_item(Key={'id': WHEEL_ID}, **to_update_kwargs({'rigging': {}}))

    participant = {
        'id': get_uuid(),
        'wheel_id': WHEEL_ID,
        'name': 'Pick me!',
        'url': 'https://amazon.com',
        'weight': 1
    }
    mock_participant_table.put_item(Item=participant)

    event = {'body': {}, 'pathParameters': {'wheel_id': WHEEL_ID, 'participant_id': participant['id']}}
    response = wheel_participant.select_participant(event)

    assert response['statusCode'] == 201
    assert 'rigging' not in mock_wheel_table.get_existing_item(Key={'id': WHEEL_ID})


def test_rig_participant(mock_dynamodb, mock_wheel_table):
    event = {
        'body': {'hidden': True},
        'pathParameters': {
            'wheel_id': WHEEL_ID,
            'participant_id': get_uuid()
        }
    }
    response = wheel_participant.rig_participant(event)

    assert response['statusCode'] == 201
    assert 'rigging' in mock_wheel_table.get_existing_item(Key={'id': WHEEL_ID})


def test_suggest_participant_comical_rig(mock_dynamodb, mock_participant_table, mock_wheel_table):
    participants = [{
        'id': get_uuid(),
        'wheel_id': WHEEL_ID,
        'name': name,
    } for name in ['Rig me!', 'I cannot win!']]

    with mock_participant_table.batch_writer() as batch:
        for participant in participants:
            batch.put_item(Item=participant)
    mock_wheel_table.update_item(Key={'id': WHEEL_ID}, **to_update_kwargs({'rigging': {'hidden': False, 'participant_id': participants[0]['id']}}))

    response = wheel_participant.suggest_participant({'body': {}, 'pathParameters': {'wheel_id': WHEEL_ID}})

    assert response['statusCode'] == 200
    assert json.loads(response['body'])['participant_id'] == participants[0]['id']
