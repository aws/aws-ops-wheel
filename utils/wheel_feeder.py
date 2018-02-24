#!/usr/bin/env python3.6

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
import sys

try:
    import boto3
    # required for easy Cognito Authentication
    from warrant import Cognito
except ImportError:
    print(f'Missing Python dependencies.  Install by running:  pip3.6 install boto3 warrant')
    raise SystemExit(1)


class CSVRowNumberOfElementsMismatch(Exception):
    pass


class WheelMetadataProvider(object):
    def __init__(self, stackname, region, wheel_name):
        self.stackname = stackname
        self.region = region
        self.wheel_name = wheel_name

        self._cognito_stack_arn = None
        self._apigw_stack_arn = None
        self._lambda_stack_arn = None
        self._cognito_client_id = None
        self._apigw_id = None
        self._cognito_user_pool_id = None
        self._wheel_table_name = None
        self._participant_table_name = None
        self._lambda_stack_arn = None
        self._cognito_stack_arn = None
        self._wheel_id = None

    @property
    def cognito_client_id(self):
        if self._cognito_client_id is None:
            self._get_stack_information()
        return self._cognito_client_id

    @property
    def cognito_user_pool_id(self):
        if self._cognito_user_pool_id is None:
            self._get_stack_information()
        return self._cognito_user_pool_id

    @property
    def wheel_table_name(self):
        if self._wheel_table_name is None:
            self._get_stack_information()
        return self._wheel_table_name

    @property
    def cognito_stack_arn(self):
        if self._cognito_stack_arn is None:
            self._get_stack_information()
        return self._cognito_stack_arn

    @property
    def apigw_stack_arn(self):
        if self._apigw_stack_arn is None:
            self._get_stack_information()
        return self._apigw_stack_arn

    @property
    def apigw_id(self):
        if self._apigw_id is None:
            self._get_stack_information()
        return self._apigw_id

    @property
    def wheel_url(self):
        return "https://%s.execute-api.%s.amazonaws.com" % (self.apigw_id, self.region)

    @property
    def lambda_stack_arn(self):
        if self._lambda_stack_arn is None:
            self._get_stack_information()
        return self._lambda_stack_arn

    @property
    def wheel_id(self):
        if self._wheel_id is None:
            self._get_wheel_id()
        return self._wheel_id

    def _get_stack_information(self):
        # find the cognito stack arn
        cf = boto3.client('cloudformation', region_name=self.region)

        res = cf.list_stack_resources(StackName=self.stackname)
        for p in res['StackResourceSummaries']:
            if p['ResourceType'] == 'AWS::CloudFormation::Stack' and \
                p['ResourceStatus'] == 'CREATE_COMPLETE' and \
                    'CognitoStack' in p['PhysicalResourceId']:
                self._cognito_stack_arn = p['PhysicalResourceId']

            if p['ResourceType'] == 'AWS::CloudFormation::Stack' and \
                p['ResourceStatus'] == 'CREATE_COMPLETE' and \
                    'ApiGatewayStack' in p['PhysicalResourceId']:
                self._apigw_stack_arn = p['PhysicalResourceId']

            if p['ResourceType'] == 'AWS::CloudFormation::Stack' and \
                p['ResourceStatus'] == 'CREATE_COMPLETE' and \
                    'LambdaStack' in p['PhysicalResourceId']:
                self._lambda_stack_arn = p['PhysicalResourceId']

        # find the cognito resources created
        res = cf.list_stack_resources(StackName=self._cognito_stack_arn)
        for p in res['StackResourceSummaries']:
            if p['ResourceType'] == 'AWS::Cognito::UserPoolClient':
                self._cognito_client_id = p['PhysicalResourceId']
            if p['ResourceType'] == 'AWS::Cognito::UserPool':
                self._cognito_user_pool_id = p['PhysicalResourceId']

        # find the apigw resources created
        res = cf.list_stack_resources(StackName=self._apigw_stack_arn)
        for p in res['StackResourceSummaries']:
            if p['ResourceType'] == 'AWS::ApiGateway::RestApi':
                self._apigw_id = p['PhysicalResourceId']

        # find the dynamodb tables created (via lambda stack)
        res = cf.list_stack_resources(StackName=self._lambda_stack_arn)
        for p in res['StackResourceSummaries']:
            if p['ResourceType'] == 'AWS::DynamoDB::Table':
                if 'wheelDynamoDBTable' in p['PhysicalResourceId']:
                    self._wheel_table_name = p['PhysicalResourceId']
                if 'participantDynamoDBTable' in p['PhysicalResourceId']:
                    self._participant_table_name = p['PhysicalResourceId']

    def _get_wheel_id(self):
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        wheel_table = dynamodb.Table(self.wheel_table_name)
        # note: this assumes the table is small
        # if you have a lot of wheels, querying against
        # a secondary index would be prudent
        for item in wheel_table.scan()['Items']:
            if item['name'] == self.wheel_name:
                self._wheel_id = item['id']


class WheelFeederAuthentication:

    """
    WheelFeederAuthentication takes care about building valid session with the Wheel's API
    using Cognito User Pool that gets created using Cloudformation Template during deployment of the Wheel.
    """

    def __init__(self, cognito_user_pool_id, cognito_client_id, region):
        """
        :param cognito_user_pool_id: Cognito User Pool Id which the Wheel uses to authenticate the Users
        :type cognito_user_pool_id: str
        :param cognito_client_id: Client Id configured in the Cognito User Pool
        :type cognito_client_id: str
        """
        self._username = None
        self._password = None
        self.region = region
        self._cognito_user_pool_id = cognito_user_pool_id
        self._cognito_client_id = cognito_client_id

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
            user_pool_region=self.region
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

    STAGE_IDENTIFIER = 'app'
    STATUS_CODES_SUCCESS = [200]

    """
    Wheel Feeder is a utility to ease populating the Wheel with CSV File.
    Requires authentication with one of the Users configured in the Cognito User Pool used by the Wheel.
    """

    def __init__(self, wheel_url, wheel_id, csv_file_path, cognito_user_pool_id, cognito_client_id, region):
        """
        :param wheel_url: URL of the Wheel
        :type wheel_url: str
        :param wheel_id: Id of the Wheel which will be fed
        :type wheel_id: str
        :param csv_file_path: Path of the CSV File
        :type csv_file_path: str
        :param region: Region of the wheel
        """
        self._wheel_url = wheel_url
        self._wheel_id = wheel_id
        self._region = region
        self._csv_file_path = csv_file_path
        self._csv_file = open(self._csv_file_path)
        self._authentication = WheelFeederAuthentication(
            cognito_user_pool_id,
            cognito_client_id,
            self._region
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
        wheel_full_url = "{}/{}/api/wheel/{}/participant".format(
            self._wheel_url,
            self.STAGE_IDENTIFIER,
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
                print(f'Upload was not successful. Status Code: {r.status_code} {r.text}')
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
            nr_cols = len(row)
            if nr_cols != 2:
                raise CSVRowNumberOfElementsMismatch(
                    f'Row: {row} is not valid, has {nr_cols} columns'
                )

        # Rewind the reader to the beginning of the file
        self._csv_file.seek(0)


DESCRIPTION = """
The Wheel Feeder is a script that allows you
to add participants from a CSV File.

The format of the file is:
<participant-name>,<target-url>
"""


def main():
    print("Initializing the Wheel Feeder...")
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""

%(program)s -r <region> -s <stack name> -n <wheel name> -c <csv file path>

%(program)s -r <region> -u <wheel url> -w <wheel uuid> -p <cognito group id> -i <cognito client id> -c <csv file path>
""" % {"program": sys.argv[0]}
    )

    parser.add_argument(
        '-u', '--wheel-url', required=False,
        help='Full URL of the Wheel\'s API Gateway endpoint. \n'
        'Example: https://<API_ID>.execute-api.us-west-2.amazonaws.com'
    )
    parser.add_argument(
        '-w', '--wheel-id', required=False,
        help='UUID of the Wheel which you want to feed. \n'
        'Example: 57709419-17c9-4b77-ac99-77fb0d7c7c51'
    )
    parser.add_argument(
        '-c', '--csv-file-path', required=False,
        help='Path to the CSV file. \n'
        'Example: /home/foo/participants.csv'
    )
    parser.add_argument(
        '-p', '--cognito-user-pool-id', required=False,
        help='Cognito User Pool Id. \n'
        'Example: us-west-2_K4oiNOTREAL'
    )
    parser.add_argument(
        '-i', '--cognito-client-id', required=False,
        help='Cognito Client Id (get it by visiting your Cognito User Pool). \n'
        'Example: 6e6p1k4qaNOTREAL'
    )
    parser.add_argument(
        '-s', '--stack-name', required=False,
        help='The CloudFormation stack name used to set up your wheel.\n'
        'Example: MyAWSWheel Stack'
    )
    parser.add_argument(
        '-r', '--region', required=False, default="us-west-2",
        help='The AWS Region in which your Wheel stack lives, defaults to us-west-2\n'
        'Example: us-west-2'
    )
    parser.add_argument(
        '-n', '--wheel-name', required=False,
        help='The name of your Wheel\n'
        'Example: MyOrganizationWheel'
    )
    args = parser.parse_args()

    if args.wheel_name and args.stack_name and args.region:
        metadata = WheelMetadataProvider(args.stack_name,
                                         args.region,
                                         args.wheel_name)
        print("url=%s id=%s userpoolid=[%s] clientid=[%s]" % (metadata.wheel_url,
                                                              metadata.wheel_id,
                                                              metadata.cognito_user_pool_id,
                                                              metadata.cognito_client_id))

        wheel_feeder = WheelFeeder(metadata.wheel_url,
                                   metadata.wheel_id,
                                   args.csv_file_path,
                                   metadata.cognito_user_pool_id,
                                   metadata.cognito_client_id,
                                   args.region)

    elif args.wheel_url and args.wheel_id and \
            args.cognito_user_pool_id and args.cognito_client_id:
        # Initialize the Feeder and execute it.
        wheel_feeder = WheelFeeder(
            args.wheel_url,
            args.wheel_id,
            args.csv_file_path,
            args.cognito_user_pool_id,
            args.cognito_client_id,
            args.region
        )
    else:
        parser.print_usage()
        raise SystemExit("FIXME: need usage")

    wheel_feeder.execute()


if __name__ == "__main__":
    main()
