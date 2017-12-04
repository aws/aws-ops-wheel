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


@base.route('/wheel/{wheel_id}/participant', methods=['PUT', 'POST'])
def create_participant(event):
    """
    Create a participant

    :param event: Lambda event containing the API Gateway request body including a name and a url and the
    path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      },
      "body":
      {
        "name": participant name string,
        "url: Valid URL for the participant,
      }
    }
    :return: response dictionary containing new participant object if successful
    {
      "body":
      {
        "id": string ID of the participant (DDB Hash Key),
        "wheel_id": string ID of the wheel (DDB Hash Key),
        "name": string name of the wheel,
        "url: URL for the participant,
        "created_at": creation timestamp,
        "updated_at": updated timestamp,
      }
    }
    """
    wheel_id = event['pathParameters']['wheel_id']
    body = event['body']
    if not check_string(body.get('name', None)) or not check_string(body.get('url', None)):
        raise base.BadRequestError("Participants require a name and url which must be at least 1 character in length")

    wheel = Wheel.get_existing_item(Key={'id': wheel_id})
    create_timestamp = get_utc_timestamp()

    participant = {
        'wheel_id': wheel_id,
        'id': get_uuid(),
        'name': body['name'],
        'url': body['url'],
        'created_at': create_timestamp,
        'updated_at': create_timestamp,
    }
    with choice_algorithm.wrap_participant_creation(wheel, participant):
        WheelParticipant.put_item(Item=participant)
    return participant


@base.route('/wheel/{wheel_id}/participant/{participant_id}', methods=['DELETE'])
def delete_participant(event):
    """
    Deletes the participant from the wheel and redistributes wheel weights

    :param event: Lambda event containing the API Gateway request path parameters wheel_id and participant_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
        "participant_id": string ID of the participant (DDB Hash Key)
      },
    }
    :return: response dictionary
    """
    wheel_id = event['pathParameters']['wheel_id']
    participant_id = event['pathParameters']['participant_id']
    # Make sure the wheel exists
    wheel = Wheel.get_existing_item(Key={'id': wheel_id})

    # REST-ful Deletes are idempotent and should not error if it's already been deleted
    response = WheelParticipant.delete_item(Key={'wheel_id': wheel_id, 'id': participant_id}, ReturnValues='ALL_OLD')
    if 'Attributes' in response:
        choice_algorithm.on_participant_deletion(wheel, response['Attributes'])


@base.route('/wheel/{wheel_id}/participant', methods=['GET'])
def list_participants(event):
    """
    Gets the participants for the specified wheel_id

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      },
    }
    :return: response dictionary containing a list of participants
    {
      "body":
      [
        participant1,
        participant2,
        ...
        participantn,
      ]
    }
    """
    wheel_id = event['pathParameters']['wheel_id']
    # Make sure the wheel exists
    Wheel.get_existing_item(Key={'id': wheel_id})
    return list(WheelParticipant.iter_query(KeyConditionExpression=Key('wheel_id').eq(wheel_id)))


@base.route('/wheel/{wheel_id}/participant/{participant_id}', methods=['PUT', 'POST'])
def update_participant(event):
    """
    Update a participant's name and/or url

    :param event: Lambda event containing the API Gateway request body including updated name or url and the
    path parameters wheel_id and participant_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
        "participant_id": string ID of the participant (DDB Hash Key)
      },
      "body":
      {
        "id": string ID of the participant (DDB Hash Key),
        "name": string name of the wheel (optional),
        "url: Valid URL for the participant (optional),
      }
    }
    :return: response dictionary containing the updated participant object if successful
    {
      "body":
      {
        "id": string ID of the participant (DDB Hash Key),
        "wheel_id": string ID of the wheel (DDB Hash Key),
        "name": string name of the wheel,
        "url: URL for the participant,
        "created_at": creation timestamp,
        "updated_at": updated timestamp,
      }
    }
    """
    wheel_id = event['pathParameters']['wheel_id']
    participant_id = event['pathParameters']['participant_id']
    # Check that the participant exists
    participant = WheelParticipant.get_existing_item(Key={'id': participant_id, 'wheel_id': wheel_id})
    body = event['body']
    params = {'updated_at': get_utc_timestamp()}
    if not check_string(body.get('name', 'Not Specified')) or not check_string(body.get('url', 'Not Specified')):
        raise base.BadRequestError("Participants names and urls must be at least 1 character in length")

    if 'name' in body:
        params['name'] = body['name']

    if 'url' in body:
        params['url'] = body['url']

    WheelParticipant.update_item(Key={'id': participant_id, 'wheel_id': wheel_id}, **to_update_kwargs(params))
    participant.update(params)
    return participant


@base.route('/wheel/{wheel_id}/participant/{participant_id}/select', methods=['PUT', 'POST'])
def select_participant(event):
    """
    Indicates selection of a participant by the wheel.  This will cause updates to the weights for all participants
    or removal of rigging if the wheel is rigged.

    :param event: Lambda event containing the API Gateway request path parameters wheel_id and participant_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel to rig (DDB Hash Key)
        "participant_id": string ID of the participant to rig (DDB Hash Key)
      },
    }
    :return: response dictionary
    """
    wheel_id = event['pathParameters']['wheel_id']
    participant_id = event['pathParameters']['participant_id']
    wheel = Wheel.get_existing_item(Key={'id': wheel_id})
    participant = WheelParticipant.get_existing_item(Key={'id': participant_id, 'wheel_id': wheel_id})
    choice_algorithm.select_participant(wheel, participant)

    # Undo any rigging that has been set up
    Wheel.update_item(Key={'id': wheel['id']}, UpdateExpression='remove rigging')


@base.route('/wheel/{wheel_id}/participant/{participant_id}/rig', methods=['PUT', 'POST'])
def rig_participant(event):
    """
    Rig the specified wheel for the specified participant.  Default behavior is comical rigging (hidden == False)
    but hidden can be specified to indicate deceptive rigging (hidden == True)

    :param event: Lambda event containing the API Gateway request path parameters wheel_id and participant_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel to rig (DDB Hash Key)
        "participant_id": string ID of the participant to rig (DDB Hash Key)
      },
      "body":
      {
        "hidden": boolean indicates deceptive rigging if True, comical if False
      }
    }
    :return: response dictionary
    """
    # By default, rigging the wheel isn't hidden but they can be
    wheel_id = event['pathParameters']['wheel_id']
    participant_id = event['pathParameters']['participant_id']
    hidden = bool(event['body'].get('hidden', False))
    update = {'rigging': {'participant_id': participant_id, 'hidden': hidden}}
    Wheel.update_item(Key={'id': wheel_id}, **to_update_kwargs(update))


@base.route('/wheel/{wheel_id}/participant/suggest', methods=['GET'])
def suggest_participant(event):
    """
    Returns a suggested participant to be selected by the next wheel spin

    :param event: Lambda event containing the API Gateway request path parameter wheel_id
    {
      "pathParameters":
      {
        "wheel_id": string ID of the wheel (DDB Hash Key)
      },
    }
    :return: response dictionary containing a selected participant_id
    {
      "body":
      {
        "participant_id": string ID of the suggested participant (DDB Hash Key),
        "rigged": True (if rigged, otherwise this key is not present)
      }
    }
    """
    wheel_id = event['pathParameters']['wheel_id']
    wheel = Wheel.get_existing_item(Key={'id': wheel_id})
    # Only return rigged participant if we're not using hidden rigging
    if 'rigging' in wheel and not wheel['rigging'].get('hidden', False):
        participant_id = wheel['rigging']['participant_id']
        # Use rigging only if the rigged participant is still available
        if 'Item' in WheelParticipant.get_item(Key={'wheel_id': wheel_id, 'id': participant_id}):
            return {'participant_id': participant_id, 'rigged': True}
    return {'participant_id': choice_algorithm.suggest_participant(wheel)}
