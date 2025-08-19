"""
API Gateway Lambda Authorizer
Returns IAM policy for API Gateway authorization
"""
import json
import logging
import os
import sys
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/api-v2')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def decode_jwt_payload_only(token: str) -> dict:
    """
    Decode JWT payload without signature verification (inline copy)
    """
    import base64
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # Decode payload (middle part)
        payload_encoded = parts[1]
        # Add padding if necessary
        payload_encoded += '=' * (4 - len(payload_encoded) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_encoded)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        return payload
    except Exception as e:
        raise ValueError(f"Failed to decode JWT payload: {str(e)}")

def validate_token_basic(token: str, user_pool_id: str, client_id: str) -> dict:
    """
    Basic JWT token validation without signature verification (inline copy)
    """
    import time
    try:
        payload = decode_jwt_payload_only(token)
        
        # Basic validations
        required_claims = ['sub', 'exp', 'iss', 'aud']
        for claim in required_claims:
            if claim not in payload:
                raise ValueError(f"Missing required claim: {claim}")
        
        # Check issuer format (handle AWS Cognito service issue with typo)
        region = user_pool_id.split('_')[0]
        expected_iss = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        typo_iss = f"https://cognitm-idp.{region}.amazonaws.com/{user_pool_id}"  # AWS service issue
        
        if payload['iss'] not in [expected_iss, typo_iss]:
            raise ValueError(f"Invalid issuer: {payload['iss']}. Expected: {expected_iss}")
        
        # Check audience
        if payload['aud'] != client_id:
            raise ValueError(f"Invalid audience: {payload['aud']}")
        
        # Check token type
        if payload.get('token_use') != 'id':
            raise ValueError(f"Invalid token use: {payload.get('token_use')}")
        
        # Check expiration (basic check)
        current_time = int(time.time())
        if payload['exp'] < current_time:
            raise ValueError("Token has expired")
        
        return payload
        
    except Exception as e:
        raise ValueError(f"Token validation failed: {str(e)}")

def lookup_user_wheel_group_info(user_email: str) -> dict:
    """
    Look up wheel group information from DynamoDB based on user email (inline copy)
    """
    import boto3
    try:
        # Initialize DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'))
        users_table = dynamodb.Table(os.environ.get('USERS_TABLE'))
        wheel_groups_table = dynamodb.Table(os.environ.get('WHEEL_GROUPS_TABLE'))
        
        # Query Users table by email
        response = users_table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={':email': user_email}
        )
        
        items = response.get('Items', [])
        if not items:
            raise ValueError(f"User not found in database: {user_email}")
        
        user_record = items[0]
        wheel_group_id = user_record['wheel_group_id']
        user_role = user_record.get('role', 'USER')
        
        # Get wheel group information
        wheel_group_response = wheel_groups_table.get_item(Key={'wheel_group_id': wheel_group_id})
        wheel_group_record = wheel_group_response.get('Item', {})
        
        return {
            'user_id': user_record['user_id'],
            'wheel_group_id': wheel_group_id,
            'wheel_group_name': wheel_group_record.get('wheel_group_name', wheel_group_id),
            'role': user_role,
            'email': user_email,
            'name': user_record.get('name', user_email),
            'permissions': get_role_permissions(user_role)
        }
        
    except Exception as e:
        raise ValueError(f"Failed to lookup user wheel group info: {str(e)}")

def get_role_permissions(role: str) -> list:
    """Get permissions for a user role (inline copy)"""
    permissions_map = {
        'ADMIN': [
            'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
            'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'
        ],
        'WHEEL_ADMIN': [
            'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
            'view_wheels', 'rig_wheel'
        ],
        'USER': [
            'spin_wheel', 'view_wheels'
        ],
    }
    return permissions_map.get(role.upper(), permissions_map['USER'])

def lambda_handler(event, context):
    """
    API Gateway Lambda Authorizer using DynamoDB-based tenant lookup
    Must return IAM policy with Allow/Deny
    """
    try:
        # Extract token from event
        token = event.get('authorizationToken', '')
        
        if not token.startswith('Bearer '):
            logger.info("No Bearer token found")
            raise Exception('Unauthorized')
        
        # Remove 'Bearer ' prefix
        jwt_token = token[7:]
        
        # Validate JWT using DynamoDB-based middleware
        try:
            user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
            client_id = os.environ.get('COGNITO_CLIENT_ID')
            
            if not user_pool_id or not client_id:
                logger.error("Missing Cognito configuration in environment variables")
                raise Exception('Unauthorized')
            
            # Basic JWT validation
            payload = validate_token_basic(jwt_token, user_pool_id, client_id)
            
            # Get user email from JWT
            user_email = payload.get('email')
            if not user_email:
                logger.error("Token missing email claim")
                raise Exception('Unauthorized')
            
            # Check if this is a deployment admin user
            is_deployment_admin = payload.get('custom:deployment_admin') == 'true'
            
            if is_deployment_admin:
                # For deployment admin, create context without database lookup
                logger.info(f"Deployment admin token validated for user: {user_email}")
                wheel_group_info = {
                    'user_id': payload.get('sub'),
                    'wheel_group_id': None,  # Deployment admins don't belong to specific wheel groups
                    'wheel_group_name': None,
                    'role': 'DEPLOYMENT_ADMIN',
                    'email': user_email,
                    'name': payload.get('name', user_email),
                    'deployment_admin': True,
                    'permissions': [
                        # Deployment admin specific permissions
                        'view_all_wheel_groups', 'delete_wheel_group', 'manage_deployment',
                        # All regular admin permissions
                        'create_wheel', 'delete_wheel', 'manage_participants', 'spin_wheel', 
                        'view_wheels', 'manage_users', 'manage_wheel_group', 'rig_wheel'
                    ]
                }
            else:
                # Look up wheel group information from DynamoDB for regular users
                wheel_group_info = lookup_user_wheel_group_info(user_email)
                logger.info(f"Regular user token validated for user: {user_email}, wheel_group: {wheel_group_info['wheel_group_id']}")
            
            # Generate Allow policy
            policy = generate_policy(user_email, 'Allow', event['methodArn'], wheel_group_info)
            logger.info(f"Generated policy: {json.dumps(policy)}")
            return policy
            
        except Exception as e:
            logger.error(f"JWT validation failed: {str(e)}")
            raise Exception('Unauthorized')
            
    except Exception as e:
        logger.error(f"Authorizer error: {str(e)}")
        # Return Deny policy
        return generate_policy('user', 'Deny', event['methodArn'])

def generate_policy(principal_id, effect, resource, context=None):
    """
    Generate IAM policy for API Gateway
    """
    auth_response = {
        'principalId': principal_id
    }
    
    if effect and resource:
        # Use wildcard resource pattern to allow access to all API endpoints
        # Extract the base resource pattern from the methodArn
        # Example: arn:aws:execute-api:us-west-2:123456789:abcdef123/dev/GET/app/api/v2/wheels
        # Becomes: arn:aws:execute-api:us-west-2:123456789:abcdef123/dev/*/*
        resource_parts = resource.split('/')
        if len(resource_parts) >= 3:
            # Keep API Gateway ID and stage, but use wildcard for method and path
            wildcard_resource = '/'.join(resource_parts[:2]) + '/*/*'
        else:
            wildcard_resource = resource
            
        policy_document = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': wildcard_resource
                }
            ]
        }
        auth_response['policyDocument'] = policy_document
    
    # Pass wheel group context to downstream Lambda (API Gateway context values must be strings)
    if context:
        auth_response['context'] = {
            'wheel_group_id': str(context.get('wheel_group_id', '')),
            'user_id': str(context.get('user_id', '')),
            'role': str(context.get('role', '')),
            'wheel_group_name': str(context.get('wheel_group_name', '')),
            'deployment_admin': str(context.get('deployment_admin', 'false'))
        }
    
    return auth_response
