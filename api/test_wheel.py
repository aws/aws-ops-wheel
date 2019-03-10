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
import wheel
from utils import get_uuid
from base import NotFoundError


def test_create_wheel(mock_dynamodb, mock_wheel_table):
    event = {'body': {'name': 'Test Wheel'}}

    response = wheel.create_wheel(event)
    created_wheel = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert created_wheel['name'] == event['body']['name']
    assert mock_wheel_table.get_existing_item(Key={'id': created_wheel['id']})


def test_invalid_create_wheel(mock_dynamodb):
    response = wheel.create_wheel({'body': {'name': ''}})

    assert response['statusCode'] == 400
    assert 'New wheels require a name that must be a string with a length of at least 1' in response['body']


def test_delete_wheel(mock_dynamodb, mock_participant_table, mock_wheel_table):
    test_wheel = {'id': get_uuid()}
    participant = {'id': get_uuid(), 'wheel_id': test_wheel['id']}

    mock_wheel_table.put_item(Item=test_wheel)
    mock_participant_table.put_item(Item=participant)

    event = {'body': {}, 'pathParameters': {'wheel_id': test_wheel['id']}}
    response = wheel.delete_wheel(event)

    assert response['statusCode'] == 201
    with pytest.raises(NotFoundError):
        mock_wheel_table.get_existing_item(Key=test_wheel)
    with pytest.raises(NotFoundError):
        mock_participant_table.get_existing_item(Key=participant)


def test_get_wheel(mock_dynamodb, mock_wheel_table):
    test_wheel = {
        'id': get_uuid(),
        'name': 'Test Wheel'
    }
    mock_wheel_table.put_item(Item=test_wheel)

    event = {'body': {}, 'pathParameters': {'wheel_id': test_wheel['id']}}
    response = wheel.get_wheel(event)

    assert response['statusCode'] == 200
    assert json.loads(response['body']) == test_wheel


def test_list_wheels(mock_dynamodb, mock_wheel_table):
    test_wheels = [{
        'id': get_uuid(),
        'name': 'Wheel ' + num
    } for num in ['0', '1']]

    with mock_wheel_table.batch_writer() as batch:
        for test_wheel in test_wheels:
            batch.put_item(Item=test_wheel)

    response = wheel.list_wheels({'body': {}})

    assert response['statusCode'] == 200
    assert 'Wheel 0' in response['body'] and 'Wheel 1' in response['body']
    assert json.loads(response['body'])['Count'] == len(test_wheels)


def test_update_wheel(mock_dynamodb, mock_wheel_table):
    test_wheel = {
        'id': get_uuid(),
        'name': 'Old Wheel Name',
    }

    mock_wheel_table.put_item(Item=test_wheel)

    new_name = 'New Wheel Name'
    event = {'body': {'name': new_name}, 'pathParameters': {'wheel_id': test_wheel['id']}}
    response = wheel.update_wheel(event)

    assert response['statusCode'] == 200
    assert json.loads(response['body'])['name'] == new_name


def test_invalid_update_wheel(mock_dynamodb, mock_wheel_table):
    test_wheel = {
        'id': get_uuid(),
        'name': 'Old Wheel Name',
    }

    mock_wheel_table.put_item(Item=test_wheel)

    event = {'body': {'name': ''}, 'pathParameters': {'wheel_id': test_wheel['id']}}
    response = wheel.update_wheel(event)

    assert response['statusCode'] == 400
    assert 'Updating a wheel requires a new name of at least 1 character in length' in response['body']


def test_unrig_participant(mock_dynamodb, mock_wheel_table):
    test_wheel = {
        'id': get_uuid(),
        'name': 'Test Wheel',
        'rigging': {
            'participant_id': get_uuid(),
            'hidden': False
        }
    }

    mock_wheel_table.put_item(Item=test_wheel)

    event = {'body': {}, 'pathParameters': {'wheel_id': test_wheel['id']}}
    response = wheel.unrig_participant(event)

    assert response['statusCode'] == 201
    assert 'rigging' not in mock_wheel_table.get_existing_item(Key={'id': test_wheel['id']})
