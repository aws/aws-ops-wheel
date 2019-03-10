#!/usr/bin/env python3

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

import requests
import argparse
import csv
import json
import getpass

try:
    import boto3
    # required for easy Cognito Authentication
    from warrant import Cognito
except ImportError:
    print(f'Missing Python dependencies.  Install by running:  pip3 install boto3 warrant')
    raise SystemExit(1)


class CSVRowNumberOfElementsMismatch(Exception):
    pass


class WheelFeederAuthentication:

    """
    WheelFeederAuthentication takes care about building valid session with the Wheel's API
    using Cognito User Pool that gets created using Cloudformation Template during deployment of the Wheel.
    """

    def __init__(self, cognito_user_pool_id, cognito_client_id, region_name=None):
        """
        :param cognito_user_pool_id: Cognito User Pool Id which the Wheel uses to authenticate the Users
        :type cognito_user_pool_id: str
        :param cognito_client_id: Client Id configured in the Cognito User Pool
        :type cognito_client_id: str
        """
        self._username = None
        self._password = None
        self._cognito_user_pool_id = cognito_user_pool_id
        self._cognito_client_id = cognito_client_id
        self.region_name = region_name

        # stores object returned by warrant
        self._cognito_user_obj = None

    def build(self):
        """
        Drives the process of getting credentials from the User and initializing valid session with Cognito.
        """
        print("Initiating Authentication with Cognito")
        self._prompt_for_credentials()
        self._initalize_tokens()
        return self

    @property
    def id_token(self):
        return self._cognito_user_obj.id_token

    def _initalize_tokens(self):
        """
        Calls Cognito to initialize Credentials.
        There is no easy way yet to authenticate a user against a Cognito User Pool in Boto3.
        Hence we are using a library that makes it easy:
          - https://github.com/capless/warrant/tree/master/warrant
        """
        self._cognito_user_obj = Cognito(
            self._cognito_user_pool_id,
            self._cognito_client_id,
            username=self._username,
            user_pool_region=self.region_name
        )

        try:
            self._cognito_user_obj.authenticate(password=self._password)
        except Exception as e:
            print('Authentication Failed. Please try again. Error message:')
            print(f'{str(e)}')
            exit(1)

    def _prompt_for_credentials(self):
        """
        Prompts the user for username and password interactively
        """
        print("In order to be able to upload Participants, you need to authenticate.")
        print("Provide credentials of one of the valid users stored in Cognito User Pool")
        self._username = input('Username: ')
        self._password = getpass.getpass('Password: ')


class WheelFeeder:

    STATUS_CODES_SUCCESS = [200]

    """
    Wheel Feeder is a utility to ease populating the Wheel with CSV File.
    Requires authentication with one of the Users configured in the Cognito User Pool used by the Wheel.
    """

    def __init__(self, wheel_url, wheel_id, csv_file_path, cognito_user_pool_id, cognito_client_id, region_name=None):
        """
        :param wheel_url: URL of the Wheel
        :type wheel_url: str
        :param wheel_id: Id of the Wheel which will be fed
        :type wheel_id: str
        :param csv_file_path: Path of the CSV File
        :type csv_file_path: str
        """
        self._wheel_url = wheel_url
        self._wheel_id = wheel_id
        self._csv_file_path = csv_file_path
        self._csv_file = open(self._csv_file_path)
        self._authentication = WheelFeederAuthentication(
            cognito_user_pool_id,
            cognito_client_id,
            region_name=region_name
        ).build()

    def execute(self):
        """
        Main method executing the feeding.
        """
        csv_reader = self.get_csv_reader()

        # Validate whether all rows are valid before adding
        self._validate_csv_file(csv_reader)

        # Perform the upload of participants
        self._upload_participants(csv_reader)

    def get_csv_reader(self):
        """
        Helper method getting the CSV Reader ready.
        """
        print(f'Trying to open the CSV file: {self._csv_file_path}')
        return csv.reader(self._csv_file)

    def _upload_participants(self, csv_reader):
        """
        Drives upload of all participants.
        :param csv_reader: CSV Reader Object
        :type csv_reader: obj
        """
        wheel_full_url = "{}/api/wheel/{}/participant".format(
            self._wheel_url,
            self._wheel_id
        )
        print(f'Full URL of the Wheel: {wheel_full_url}')

        for row in csv_reader:
            self._upload_participant(row, wheel_full_url)

    def _upload_participant(self, participant_details, full_wheel_url):
        """
        Stores one participant using the Wheels API
        :param participant_details: 2 elements list: [<name>, <url>]
        :type participant_details: list
        :param full_wheel_url: Full URL of the Wheel
        :type full_wheel_url: str
        """
        participant_name = participant_details[0]
        participant_url = participant_details[1]
        headers = {
            'content-type': 'application/json',
            'authorization': self._authentication.id_token
        }
        payload = {'id': '', 'name': participant_name, 'url': participant_url}

        print('-------------------------------------------------------------')
        print('Uploading Participant:')
        print(f' - name: {participant_name}')
        print(f' - url: {participant_url}')

        try:
            r = requests.post(
                full_wheel_url,
                data=json.dumps(payload),
                headers=headers
            )

            if r.status_code in self.STATUS_CODES_SUCCESS:
                print('Upload successful')
            else:
                print(f'Upload was not successful. Status Code: {r.status_code}')
        except Exception as e:
            print(f'There was an error during upload of the participant:')
            print(f' - name: {participant_name}')
            print(f' - url: {participant_url}')
            print(f'Following error has been raised: {e}')

    def _validate_csv_file(self, csv_reader):
        """
        Performs basic format validation of the CSV file.

        :param csv_reader: CSV reader object
        :type csv_reader: obj
        """
        for row in csv_reader:
            if len(row) != 2:
                raise CSVRowNumberOfElementsMismatch(
                    f'Row: {row} is not valid.'
                )

        # Rewind the reader to the beginning of the file
        self._csv_file.seek(0)


DESCRIPTION = """
The Wheel Feeder is a script that allows you
to add participants from a CSV File.

You must specify either:
--stack-name and --wheel-name OR --wheel-url, --wheel-id, --cognito-client-id, and --cognito-user-pool-id

The format of the file is:
<participant-name>,<target-url>
"""


def main():
    print("Initializing the Wheel Feeder...")
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        '-u', '--wheel-url',
        help='Full URL of the Wheel\'s API Gateway endpoint and stage. \n'
        'Example: https://<API_ID>.execute-api.us-west-2.amazonaws.com/app'
    )
    parser.add_argument(
        '-w', '--wheel-id',
        help='UUID of the Wheel which you want to feed. Alternatively you can use --wheel-name and --stack-name\n'
        'Example: 57709419-17c9-4b77-ac99-77fb0d7c7c51'
    )
    parser.add_argument(
        '-c', '--csv-file-path', required=True,
        help='Path to the CSV file. \n'
        'Example: /home/foo/participants.csv'
    )
    parser.add_argument(
        '-p', '--cognito-user-pool-id',
        help='Cognito User Pool Id. \n'
        'Example: us-west-2_K4oiNOTREAL'
    )
    parser.add_argument(
        '-i', '--cognito-client-id',
        help='Cognito Client Id (get it by visiting your Cognito User Pool). \n'
        'Example: 6e6p1k4qaNOTREAL'
    )
    parser.add_argument(
        '-sn', '--stack-name',
        help='Cloudformation stack name used during initial Wheel creation'
    )
    parser.add_argument(
        '-wn', '--wheel-name',
        help='Wheel name.  An alternative to wheel-id but requires you also specify the stack_name parameter'
    )
    parser.add_argument(
        '-r', '--region',
        help='Region the stack is deployed in.  E.G: us-east-1.  '
             'Defaults to the default region in your boto/awscli configuration'
    )
    args = parser.parse_args()
    if args.stack_name:
        cf_client = boto3.client('cloudformation', region_name=args.region)
        stack = cf_client.describe_stacks(StackName=args.stack_name)['Stacks'][0]
        stack_outputs = {output['OutputKey']: output['OutputValue'] for output in stack['Outputs']}
        args.cognito_client_id = args.cognito_client_id or stack_outputs['CognitoUserPoolClient']
        args.cognito_user_pool_id = args.cognito_user_pool_id or stack_outputs['CognitoUserPool']
        args.wheel_url = args.wheel_url or stack_outputs['Endpoint']

        if args.wheel_name:
            ddb_client = boto3.resource('dynamodb', region_name=args.region)
            for item in ddb_client.Table(stack_outputs['wheelDynamoDBTable']).scan()['Items']:
                if item['name'] == args.wheel_name:
                    args.wheel_id = item['id']
                    break
            else:
                raise SystemExit("ERROR: Could not find a wheel with the name '%s'" % args.wheel_name)

    if not (args.wheel_url and args.wheel_id and args.cognito_user_pool_id and args.cognito_client_id):
        raise SystemExit("Error:  You must specify either --stack-name and --wheel-name parameters or "
                         "--wheel-url, --wheel-id, --cognito-user-pool-id, and --cognito-client-id parameters")

    # Initialize the Feeder and execute it.
    wheel_feeder = WheelFeeder(
        args.wheel_url,
        args.wheel_id,
        args.csv_file_path,
        args.cognito_user_pool_id,
        args.cognito_client_id,
        region_name=args.region
    )
    wheel_feeder.execute()


if __name__ == "__main__":
    main()
