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

import boto3
import datetime
import os
import uuid
from base import NotFoundError


dynamodb = boto3.resource('dynamodb')
Wheel = dynamodb.Table(os.environ.get('WHEEL_TABLE', 'DevOpsWheel-Wheels'))
WheelParticipant = dynamodb.Table(os.environ.get('PARTICIPANT_TABLE', 'DevOpsWheel-Participants'))


def add_extended_table_functions(table):
    def get_existing_item(Key, *args, **kwargs):
        """
        Add a new 'get_existing_item' method for our tables that will throw a 404 when it doesn't exist
        """
        response = table.get_item(Key=Key, *args, **kwargs)
        if 'Item' not in response:
            raise NotFoundError(f"{table.name} : {Key} Could Not Be Found")
        return response['Item']

    def iter_query(*args, **kwargs):
        """Unwrap pagination from DynamoDB query results to yield items"""
        query_results = None
        while query_results is None or 'LastEvaluatedKey' in query_results:
            if query_results is not None:
                kwargs['ExclusiveStartKey'] = query_results['LastEvaluatedKey']
            query_results = table.query(*args, **kwargs)
            for item in query_results['Items']:
                yield item

    table.get_existing_item = get_existing_item
    table.iter_query = iter_query


add_extended_table_functions(Wheel)
add_extended_table_functions(WheelParticipant)


def check_string(string):
    return isinstance(string, str) and len(string) > 0


def get_uuid():
    return str(uuid.uuid4())


def get_utc_timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def to_update_kwargs(attributes):
    """
    For an attribute dictionary, make a default update expression for setting the values

    Notes: Use an expression attribute name to replace that attribute's name with reserved word in the expression,
    reference can be found here:
    http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ExpressionAttributeNames.html#ExpressionAttributeNames
    """

    return {
        'UpdateExpression': 'set {}'.format(', '.join([f"#{k} = :{k}" for k in attributes])),
        'ExpressionAttributeValues': {f":{k}": v for k, v in attributes.items()},
        'ExpressionAttributeNames': {f"#{k}": k for k in attributes}
    }
