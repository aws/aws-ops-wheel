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
from utils import Wheel, WheelParticipant, to_update_kwargs
from base import BadRequestError
import random
import contextlib
from decimal import Decimal


def suggest_participant(wheel):
    """
    Suggest a participant given weights of all participants with randomization.
    This is weighted selection where all participants start with a weight of 1, so the sum of the weights will always
    equal the number of participants
    :param wheel: Wheel dictionary:
    {
      "id": string ID of the wheel (DDB Hash Key),
      "name": string name of the wheel,
      "participant_count": number of participants in the wheel,
    }
    :return: ID of the suggested participant
    """
    if wheel['participant_count'] == 0:
        raise BadRequestError("Cannot suggest a participant when the wheel doesn't have any!")

    query_params = {'KeyConditionExpression': Key('wheel_id').eq(wheel['id'])}

    # selected_total_weight = random.random() * float(wheel['participant_count'])
    participants = WheelParticipant.iter_query(**query_params)
    selected_total_weight = random.random() * float(sum([participant['weight'] for participant in participants]))

    # We do potentially want to return the last participant just as a safe-guard for rounding errors
    participant = None
    for participant in WheelParticipant.iter_query(**query_params):
        selected_total_weight -= float(participant['weight'])
        if selected_total_weight <= 0:
            return participant['id']
    return participant['id']


def select_participant(wheel, participant):
    """
    Register the selection of a participant by updating the weights of all participants for a given wheel
    :param wheel: Wheel dictionary:
    {
      "id": string ID of the wheel (DDB Hash Key),
      "name": string name of the wheel,
      "participant_count": number of participants in the wheel,
    }
    :param participant: Participant dictionary:
    {
      "id": string ID of the participant (DDB Hash Key),
      "name": string name of the participant,
      "url": Participant's URL,
      "wheel_id": string ID of the wheel the participant belongs to,
      "weight": participant's weight in the selection algorithm
    }
    :return: None
    """
    participant_count = wheel['participant_count']

    total_weight = Decimal(0)
    for p in WheelParticipant.iter_query(KeyConditionExpression=Key('wheel_id').eq(wheel['id'])):
        total_weight += p['weight']
    factor = Decimal(participant_count) / total_weight

    if participant_count > 1:
        weight_share = participant['weight'] / Decimal(participant_count - 1)
        with WheelParticipant.batch_writer() as batch:
            for p in WheelParticipant.iter_query(KeyConditionExpression=Key('wheel_id').eq(wheel['id'])):
                if p['id'] == participant['id']:
                    p['weight'] = 0
                else:
                    p['weight'] += Decimal(weight_share)
                    p['weight'] *= factor  # This normalizes any imbalanced wheel back to an average of 1.0
                batch.put_item(Item=p)


def reset_wheel(wheel):
    """
    Resets the weights of all participants in the wheel and updates the wheel's participant count
    :param wheel: Wheel dictionary:
    {
      "id": string ID of the wheel (DDB Hash Key),
      "name": string name of the wheel,
      "participant_count": number of participants in the wheel,
    }
    :return: None
    """
    count = 0
    with WheelParticipant.batch_writer() as batch:
        for p in WheelParticipant.iter_query(KeyConditionExpression=Key('wheel_id').eq(wheel['id'])):
            p['weight'] = 1
            batch.put_item(Item=p)
            count += 1
    Wheel.update_item(Key={'id': wheel['id']}, **to_update_kwargs({'participant_count': count}))


@contextlib.contextmanager
def wrap_wheel_creation(wheel):
    wheel['participant_count'] = 0
    yield


@contextlib.contextmanager
def wrap_participant_creation(wheel, participant):
    participant['weight'] = 1
    yield
    Wheel.update_item(
        Key={'id': wheel['id']},
        **to_update_kwargs({'participant_count': wheel['participant_count'] + 1})
    )


def on_participant_deletion(wheel, participant):
    """
    Normalize the remaining participant weights to account for participant removal.
    The ratio is based on the following:
     1) The participant should be at weight=1 when it leaves the system (which is the same as it arrived)
     2) That difference should be split by the remaining participants proportional by weight
        This ensures that 'weight=0' participants are still at weight=0 and that the sum of all
        weights is equal to the number of participants, so new additions are treated fairly
    :param wheel: Wheel dictionary:
    {
      "id": string ID of the wheel (DDB Hash Key),
      "name": string name of the wheel,
      "participant_count": number of participants in the wheel,
    }
    :param participant: Participant dictionary:
    {
      "id": string ID of the wheel (DDB Hash Key),
      "name": string name of the wheel,
      "url": Participant's URL,
      "wheel_id": string ID of the wheel the participant belongs to,
    }
    :return: None
    """
    total_weight = participant['weight']
    for p in WheelParticipant.iter_query(KeyConditionExpression=Key('wheel_id').eq(wheel['id'])):
        total_weight += p['weight']

    weight = participant['weight']
    remaining_weight = total_weight - weight  # <-- no longer presumes existing weight balance via 'int(participant_count)'
    ratio = (1 + ((weight - 1) / remaining_weight)) if (remaining_weight != 0) else 1
    with WheelParticipant.batch_writer() as batch:
        for p in WheelParticipant.iter_query(KeyConditionExpression=Key('wheel_id').eq(wheel['id'])):
            if p['id'] != participant['id']:
                # This is cast to a string before turning into a decimal because of rounding/inexact guards in boto3
                p['weight'] = Decimal(str(float(p['weight']) * float(ratio))) if (remaining_weight != 0) else 1
                batch.put_item(Item=p)

    Wheel.update_item(
        Key={'id': wheel['id']},
        **to_update_kwargs({'participant_count': Decimal(wheel['participant_count'] - 1)})
    )
