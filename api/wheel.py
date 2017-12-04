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

from boto3.dynamodb.conditions import Key
from utils import get_utc_timestamp, get_uuid, Wheel, WheelParticipant, check_string, to_update_kwargs
import base, choice_algorithm


@base.route('/wheel', methods=['PUT', 'POST'])
def create_wheel(event):
    """
    Create a wheel. Requires a name

    :param event: Lambda event containing the API Gateway request body including a name
    {
      "body":
      {
        "name": string wheel name,
      }
    }
    :return: response dictionary containing new wheel object if successful
    {
      "body":
      {
        "id": string ID of the wheel (DDB Hash Key),
        "name": string name of the wheel,
        "participant_count": number of participants in the wheel,
        "created_at": creation timestamp,
        "updated_at": updated timestamp,
      }
    }
    """
    create_timestamp = get_utc_timestamp()
    body = event['body']
    if body is None or not check_string(body.get('name', None)):
        raise base.BadRequestError(
            f"New wheels require a name that must be a string with a length of at least 1.  Got: {body}"
        )

    wheel = {
        'id': get_uuid(),
        'name': body['name'],
        'created_at': create_timestamp,
        'updated_at': create_timestamp,
    }
    with choice_algorithm.wrap_wheel_creation(wheel):
        Wheel.put_item(Item=wheel)
    return wheel


@base.route('/wheel/{wheel_id}', methods=['DELETE'])
def delete_wheel(event):
    """
    Deletes the wheel and all of its participants

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      }
    }
    :return: response dictionary
    """
    wheel_id = event['pathParameters']['wheel_id']
    # DynamoDB always succeeds for delete_item,
    Wheel.delete_item(Key={'id': wheel_id})

    # Clear out all participants of the wheel.  Query will be empty if it was already deleted
    with WheelParticipant.batch_writer() as batch:
        query_params = {
            'KeyConditionExpression': Key('wheel_id').eq(wheel_id),
            'ProjectionExpression': 'id'
        }
        # We don't use the default generator here because we don't want the deletes to change the query results
        for p in list(WheelParticipant.iter_query(**query_params)):
            batch.delete_item(Key={'id': p['id'], 'wheel_id': wheel_id})


@base.route('/wheel/{wheel_id}', methods=['GET'])
def get_wheel(event):
    """
    Returns the wheel object corresponding to the given wheel_id

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      }
    }
    :return: response dictionary containing the requested wheel object if successful
    {
      "body":
      {
        "id": string ID of the wheel (DDB Hash Key),
        "name": string name of the wheel,
        "participant_count": number of participants in the wheel,
        "created_at": creation timestamp,
        "updated_at": updated timestamp,
      }
    }
    """
    return Wheel.get_existing_item(Key={'id': event['pathParameters']['wheel_id']})


@base.route('/wheel', methods=['GET'])
def list_wheels(event):
    """
    Get all available wheels

    :param event: Lambda event containing query string parameters that are passed to Boto's scan() API for the wheel
    table
    {
      "queryStringParameters":
      {
        ...
      }
    }
    :return: List of wheels
    {
      "body":
        "Count": number of wheels,
        "Items":
        [
          wheel1,
          wheel2,
          wheeln,
        ],
        "ScannedCount": number of items before queryStringParameters were applied,
      }
    }
    """
    parameters = event.get('queryStringParameters', None) or {}
    return Wheel.scan(**parameters)


@base.route('/wheel/{wheel_id}', methods=['PUT', 'POST'])
def update_wheel(event):
    """
    Update the name of the wheel and/or refresh its participant count

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      },
      "body":
      {
        "id": string ID of the wheel (DDB Hash Key),
        "name": string name of the wheel,
      }
    }
    :return: response dictionary containing the updated wheel object if successful
    {
      "body":
      {
        "id": string ID of the wheel (DDB Hash Key),
        "name": string name of the wheel,
        "participant_count": number of participants in the wheel,
        "created_at": creation timestamp,
        "updated_at": updated timestamp,
      }
    }
    """
    wheel_id = event['pathParameters']['wheel_id']
    key = {'id': wheel_id}
    # Make sure wheel exists
    wheel = Wheel.get_existing_item(Key=key)
    name = event['body'].get('name', None)
    if not check_string(name):
        raise base.BadRequestError("Updating a wheel requires a new name of at least 1 character in length")

    update = {'name': name, 'updated_at': get_utc_timestamp()}
    Wheel.update_item(Key=key, **to_update_kwargs(update))
    # Represent the change locally for successful responses
    wheel.update(update)
    return wheel


@base.route('/wheel/{wheel_id}/reset', methods=['PUT', 'POST'])
def reset_wheel(event):
    """
    Resets the weights of all participants of the wheel

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      }
    }
    :return: response dictionary
    """
    # Ensure that the wheel exists
    wheel_id = event['pathParameters']['wheel_id']
    wheel = Wheel.get_existing_item(Key={'id': wheel_id})
    choice_algorithm.reset_wheel(wheel)


@base.route('/wheel/{wheel_id}/unrig', methods=['PUT', 'POST'])
def unrig_participant(event):
    """
    Remove rigging for the specified wheel

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      }
    }
    :return: response dictionary
    """
    # By default, rigging the wheel isn't hidden but they can be
    wheel_id = event['pathParameters']['wheel_id']

    Wheel.update_item(Key={'id': wheel_id}, UpdateExpression='remove rigging')
