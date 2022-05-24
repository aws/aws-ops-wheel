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
import wheel
from moto import mock_dynamodb


@mock_dynamodb
def test_no_dynamodb_available():
    response = wheel.create_wheel({'body': {'name': 'DDB not available'}})
    assert response['statusCode'] == 500


def test_missing_body(mock_dynamodb):
    with pytest.raises(Exception):
        wheel.create_wheel({'not_body': 'Nobody is in here'})
