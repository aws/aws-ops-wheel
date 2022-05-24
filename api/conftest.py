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

import os
import pytest
from boto3.session import Session
from moto import mock_dynamodb as ddb_mock
with ddb_mock():
    from utils import add_extended_table_functions
    import utils

WHEEL_TABLE_NAME = os.environ.get('WHEEL_TABLE', 'DevOpsWheel-Wheels')
PARTICIPANT_TABLE_NAME = os.environ.get('PARTICIPANT_TABLE', 'DevOpsWheel-Participants')


@pytest.fixture(scope='session')
def mock_dynamodb():

    ddb_mock().start()

    session = Session(aws_access_key_id='<ACCESS_KEY_ID>',
                      aws_secret_access_key='<SECRET_KEY>')
    dynamodb = session.resource('dynamodb')

    wheel_table = dynamodb.create_table(
        TableName=WHEEL_TABLE_NAME,
        KeySchema=[
            {
                'AttributeName': 'id',
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'name',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 1,
            'WriteCapacityUnits': 1
        },
        GlobalSecondaryIndexes=[{
            'IndexName': 'name_index',
            'KeySchema': [{
                'AttributeName': 'name',
                'KeyType': 'HASH'
            }],
            'Projection': {
                'ProjectionType': 'ALL'
            },
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
          }]
    )

    participant_table = dynamodb.create_table(
        TableName=PARTICIPANT_TABLE_NAME,
        KeySchema=[
            {
                'AttributeName': 'wheel_id',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'id',
                'KeyType': 'RANGE'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'wheel_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'id',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )

    #  Wait on table creation
    wheel_table.meta.client.get_waiter('table_exists').wait(TableName=WHEEL_TABLE_NAME)
    participant_table.meta.client.get_waiter('table_exists').wait(TableName=PARTICIPANT_TABLE_NAME)

    yield dynamodb

    ddb_mock().stop()


@pytest.fixture
def mock_wheel_table(mock_dynamodb):
    Wheel = mock_dynamodb.Table(WHEEL_TABLE_NAME)
    add_extended_table_functions(Wheel)
    utils.Wheel = Wheel
    yield Wheel
    wheels = Wheel.scan()['Items']
    with Wheel.batch_writer() as batch:
        for wheel in wheels:
            batch.delete_item(Key={'id': wheel['id']})


@pytest.fixture
def mock_participant_table(mock_dynamodb):
    WheelParticipant = mock_dynamodb.Table(PARTICIPANT_TABLE_NAME)
    add_extended_table_functions(WheelParticipant)
    utils.WheelParticipant = WheelParticipant
    yield WheelParticipant
    participants = WheelParticipant.scan()['Items']
    with WheelParticipant.batch_writer() as batch:
        for participant in participants:
            batch.delete_item(Key={'id': participant['id'], 'wheel_id': participant['wheel_id']})
