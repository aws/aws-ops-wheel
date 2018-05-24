#!/usr/bin/env python3
#
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

import sys
import re
import yaml
import base
import os
# Load up all wheel and wheel_participant routes
import wheel
import wheel_participant


class Ref(str): pass
class GetAtt(str): pass
yaml.add_representer(Ref, lambda dumper, data: dumper.represent_scalar(u'!Ref', str(data)))
yaml.add_representer(GetAtt, lambda dumper, data: dumper.represent_scalar(u'!GetAtt', str(data)))


S3_PROXY_HEADERS = ['content-type', 'Content-Type', 'Date', 'content-length', 'Content-Length', 'Etag', 'etag']

# Recursive finder for config references
def find_refs(config):
    if isinstance(config, dict):
        return find_refs(list(config.values()))
    elif isinstance(config, list):
        refs = set()
        for item in config:
            refs.update(find_refs(item))
        return refs
    elif isinstance(config, Ref):
        return {str(config)}
    else:
        return set()


PATH_PARAMETER_MATCHER = re.compile(r'{([a-zA-Z0-9_]+)\+?}')


def path_to_parameters(path):
    return PATH_PARAMETER_MATCHER.findall(path)


def snake_case_to_capitalized_words(string):
    return ''.join([s.capitalize() for s in string.split('_')])


def make_api_path_config(lambda_name, path):
    path_config = {
        'x-amazon-apigateway-integration': {
            'contentHandling': 'CONVERT_TO_TEXT',
            'httpMethod': 'POST',
            'passthroughBehavior': 'WHEN_NO_MATCH',
            'responses': {'default': {'statusCode': 200}},
            'type': 'aws_proxy',
            'uri': {
                'Fn::Join': ['', [
                    'arn:aws:apigateway:',
                    Ref('AWS::Region'),
                    ':lambda:path/2015-03-31/functions/arn:aws:lambda:',
                    Ref('AWS::Region'),
                    ':',
                    Ref('AWS::AccountId'),
                    ':function:',
                    Ref(lambda_name),
                    '/invocations'
                ]]
            }
        },
    }

    if path != '/config':  # The configuration variables need to be retrieved without security
        path_config['security'] = [{'apiUsers': []}]

    parameters = path_to_parameters(path)
    if parameters:
        path_config['parameters'] = [{'in': 'path', 'name': p, 'required': True, 'type': 'string'} for p in parameters]
    return path_config


class TemplateCompiler:
    def __init__(self, in_dir, out_dir, *filenames):
        self.in_dir = in_dir
        self.out_dir = out_dir
        self.filenames = filenames

    def __enter__(self):
        self.configs = [yaml.load(open(os.path.join(self.in_dir, name))) for name in self.filenames]
        for config in self.configs:
            config.setdefault('Resources', {})
            config.setdefault('Outputs', {})
        return tuple(self.configs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            global_resources = {}

            for template_filename, config in zip(self.filenames, self.configs):
                stack_prefix = snake_case_to_capitalized_words(template_filename.split('.')[0])
                stack_name = f'{stack_prefix}Stack'

                for ref in find_refs(config):
                    if ref not in config['Resources'] and not ref.startswith('AWS::'):
                        config.setdefault('Parameters', {})
                        config['Parameters'][ref] = {'Type': 'String'}

                for resource in config['Resources'].keys():
                    config['Outputs'][resource] = {'Value': Ref(resource)}

                for output in config['Outputs']:
                    global_resources[output] = stack_name

                with open(os.path.join(self.out_dir, template_filename), 'w') as f:
                    f.write(yaml.dump(config))

            # Compile the overall configuration
            overall_config = yaml.load(open(os.path.join(self.in_dir, 'aws-ops-wheel.yml')))
            overall_config.setdefault('Resources', {})
            overall_config.setdefault('Outputs', {})
            for template_filename, config in zip(self.filenames, self.configs):
                stack_prefix = snake_case_to_capitalized_words(template_filename.split('.')[0])
                stack_name = f'{stack_prefix}Stack'
                params = {}
                for p in config.get('Parameters', dict()):
                    if p in global_resources:
                        params[p] = GetAtt(f"{global_resources[p]}.Outputs.{p}")
                    else:
                        overall_config.setdefault('Parameters', dict())
                        overall_config['Parameters'][p] = config['Parameters'][p]
                        params[p] = Ref(p)
                overall_config['Resources'][stack_name] = {
                    'Type': "AWS::CloudFormation::Stack",
                    'Properties': {
                        'TemplateURL': f'./compiled_templates/{template_filename}',
                        'TimeoutInMinutes': 20,
                        'Parameters': params,
                    }
                }
                for p in global_resources:
                    overall_config['Outputs'][p] = {'Value': GetAtt(f"{global_resources[p]}.Outputs.{p}")}


            with open(os.path.join(self.out_dir, 'aws-ops-wheel.yml'), 'w') as f:
                f.write(yaml.dump(overall_config))

def main():
    in_dir, out_dir, static_asset_s3_prefix = sys.argv[1:4]
    static_asset_s3_prefix = static_asset_s3_prefix.strip('/')

    # Unfortunately we've had to split our template into multiple configs with the API config at the top so that
    # we could get past the 50kb limit of CloudFormation
    with TemplateCompiler(
            in_dir, out_dir,
            'cognito.yml', 'lambda.yml', 'api_gateway.yml', 'api_gateway_lambda_roles.yml') as configs:
        cognito_config, lambda_config, api_config, api_lambda_roles_config = configs
        paths = {}
        for func in base.route.registry.values():
            lambda_name = snake_case_to_capitalized_words(func.__name__) + 'Lambda'
            # Strip the parameter and return documentation out of the Lambda description as this confuses Lambda
            lambda_description = ''
            if func.__doc__:
                for line in func.__doc__.splitlines():
                    line = line.strip()
                    if (':param' or ':return') in line:
                        break
                    if line:
                        lambda_description += f'{line} '
            # Generate Lambda Resources
            lambda_config['Resources'][lambda_name] = {
                'Type': 'AWS::Lambda::Function',
                'Properties': {
                    'Code': './build',
                    'Description': lambda_description,
                    'Environment': {
                        'Variables': {
                            'APP_CLIENT_ID': Ref('CognitoUserPoolClient'),
                            'USER_POOL_ID': Ref('CognitoUserPool'),
                            'PARTICIPANT_TABLE': Ref('participantDynamoDBTable'),
                            'WHEEL_TABLE': Ref('wheelDynamoDBTable'),
                        }
                    },
                    'Handler': f"{func.__module__}.{func.__name__}",
                    'MemorySize': 128,
                    'Role': GetAtt('AWSOpsWheelLambdaRole.Arn'),
                    'Runtime': 'python3.6',
                    'Timeout': 3
                }
            }

            path = f'/api/{func.route.path.lstrip("/")}'
            paths.setdefault(path, {})
            for method in func.route.methods:
                paths[path][method.lower()] = make_api_path_config(lambda_name, func.route.path)
                stripped_path = path.lstrip('/')
                api_lambda_roles_config['Resources'][f"{lambda_name}GatewayPermissions{method}"] = {
                    'Type': 'AWS::Lambda::Permission',
                    'Properties': {
                        'Action': 'lambda:invokeFunction',
                        'FunctionName': Ref(lambda_name),
                        'Principal': 'apigateway.amazonaws.com',
                        'SourceArn': {'Fn::Join': ['', [
                            'arn:aws:execute-api:',
                            Ref('AWS::Region'),
                            ':',
                            Ref('AWS::AccountId'),
                            ':',
                            Ref("AWSOpsWheelAPI"),
                            f"/*/{method.upper()}/{stripped_path}",
                        ]]},
                    }
                }

        paths['/favicon.ico'] = {'get': {
            'produces': [ 'image/x-icon' ],
            'responses': {
                '200': {
                    'description': '200 response',
                    'schema': {
                        '$ref': '#/definitions/Empty'
                    },
                    'headers': {
                        'Content-Length': {
                            'type': 'string'
                        },
                        'Content-Type': {
                            'type': 'string'
                        }
                    }
                }
            },
            'x-amazon-apigateway-integration': {
              'responses': {
                'default': {
                  'statusCode': '200',
                  'responseParameters': {
                    'method.response.header.Content-Type': 'integration.response.header.Content-Type',
                    'method.response.header.Content-Length': 'integration.response.header.Content-Length'
                  },
                  'contentHandling': 'CONVERT_TO_BINARY'
                }
              },
              'uri': f'{static_asset_s3_prefix}/favicon.ico',
              'passthroughBehavior': 'when_no_match',
              'httpMethod': 'GET',
              'contentHandling': 'CONVERT_TO_BINARY',
              'type': 'http'
            }
        }}

        paths['/static/{proxy+}'] = {'x-amazon-apigateway-any-method': {
            'parameters': [{'in': 'path', 'name': 'proxy', 'required': True, 'type': 'string'}],
            'produces': ['application/json'],
            'responses': {},
            'x-amazon-apigateway-integration': {
                'cacheKeyParameters': ['method.request.path.proxy'],
                'cacheNamespace': 'static_assets',
                'httpMethod': 'ANY',
                'passthroughBehavior': 'when_no_match',
                'requestParameters': {'integration.request.path.proxy': 'method.request.path.proxy'},
                'responses': {'default': {'statusCode': '200'}},
                'type': 'http_proxy',
                'uri': f'{static_asset_s3_prefix}/{{proxy}}',
                'contentHandling': 'CONVERT_TO_BINARY'}
        }}

        paths['/'] = {'x-amazon-apigateway-any-method': {
            'parameters': [],
            'produces': ['application/json'],
            'responses': {},
            'x-amazon-apigateway-integration': {
                'httpMethod': 'ANY',
                'passthroughBehavior': 'when_no_match',
                'requestParameters': {},
                'responses': {'default': {'statusCode': '200'}},
                'type': 'http_proxy',
                'uri': f'{static_asset_s3_prefix}/index.production.html'}
        }}

        paths['/{proxy+}'] = {'x-amazon-apigateway-any-method': {
            'parameters': [{'in': 'path', 'name': 'proxy', 'required': False, 'type': 'string'}],
            'produces': ['application/json'],
            'responses': {},
            'x-amazon-apigateway-integration': {
                'cacheKeyParameters': ['method.request.path.proxy'],
                'cacheNamespace': 'static_assets',
                'httpMethod': 'ANY',
                'passthroughBehavior': 'when_no_match',
                'requestParameters': {'integration.request.path.proxy': 'method.request.path.proxy'},
                'responses': {'default': {'statusCode': '200'}},
                'type': 'http_proxy',
                'uri': f'{static_asset_s3_prefix}/index.production.html'}
        }}

        api_config['Resources']['AWSOpsWheelAPI']['Properties']['Body'] = {
            'schemes': ['https'],
            'swagger': '2.0',
            'info': {'title': 'AWSOpsWheel', 'version': '0.1'},
            'definitions': {
                'Empty': {'title': 'Empty Schema', 'type': 'object'}
            },
            'x-amazon-apigateway-binary-media-types': ['audio/mpeg', 'audio/*', 'image/x-icon', 'application/font*', 'font/*'],
            'basePath': '/',
            'paths': paths,
            'securityDefinitions': {
                'apiUsers': {
                    'type': 'apiKey',
                    'name': 'Authorization',
                    'in': 'header',
                    'x-amazon-apigateway-authtype': 'cognito_user_pools',
                    'x-amazon-apigateway-authorizer': {
                        'type': 'COGNITO_USER_POOLS',
                        'providerARNs': [Ref('CognitoUserPoolArn')]
                    }
                }
            }
        }


if __name__ == '__main__':
    main()
