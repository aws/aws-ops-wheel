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

import decimal
import functools
import json
import traceback
import os


class ClientError(Exception):
    status_code = 400


class BadRequestError(ClientError):
    pass


class NotFoundError(ClientError):
    status_code = 404


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


class Response:
    def __init__(self, body=None, headers=None, status_code=None):
        self.headers = headers or {}
        self.body = body
        self.status_code = status_code

    def to_response(self):
        response = {'headers': self.headers}
        status_code = self.status_code
        if self.body is not None:
            if status_code is None:
                status_code = 200
            if 'Content-Type' in response['headers']:
                response['body'] = self.body
            else:
                response['headers']['Content-Type'] = 'application/json'
                response['body'] = json.dumps(self.body, cls=DecimalEncoder, sort_keys=True, indent=2)

        if status_code is None:
            status_code = 201
        response['statusCode'] = status_code
        return response


class route:
    # Shared route registry
    registry = {}

    def __init__(self, path, methods):
        self.path = path
        self.methods = methods

    def __call__(self, func):
        """
        Helper for handling exceptions within the lambda function
        and returning back appropriate responses
        """
        assert func.__name__ not in self.__class__.registry, f"There are 2 routed functions called {func.__name__}"

        @functools.wraps(func)
        def wrapper(event, context=None):
            try:
                if event['body'] is None or isinstance(event['body'], str):
                    event['body'] = json.loads(event.get('body', None) or '{}')
                if not isinstance(event['body'], dict):
                    raise Exception
            except Exception:
                return Response(body=f"Malformed JSON: {event['body']}", status_code=400).to_response()
            try:
                response = func(event)
                if not isinstance(response, Response):
                    response = Response(body=response)
                return response.to_response()
            except ClientError as e:
                return Response(body=str(e), status_code=e.status_code).to_response()
            except Exception as e:
                return Response(
                    body=f"Internal Service Exception: {traceback.format_exc()}",
                    status_code=500
                ).to_response()
        wrapper.route = self
        self.__class__.registry[func.__name__] = wrapper
        setattr(self.__class__, func.__name__, wrapper)
        return wrapper


@route('/config', methods=['GET'])
def config(event):
    return {
        'USER_POOL_ID': os.environ.get('USER_POOL_ID', None),
        'APP_CLIENT_ID': os.environ.get('APP_CLIENT_ID', None),
    }
