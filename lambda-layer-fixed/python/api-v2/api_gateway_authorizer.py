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

from tenant_middleware import decode_jwt_payload_only, validate_token_basic, lookup_user_tenant_info
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
            
            # Look up tenant information from DynamoDB
            tenant_info = lookup_user_tenant_info(user_email)
            
            logger.info(f"Token validated for user: {user_email}, tenant: {tenant_info['tenant_id']}")
            
            # Add permissions to context (they should already be there from lookup_user_tenant_info)
            if 'permissions' not in tenant_info:
                from tenant_middleware import get_role_permissions
                tenant_info['permissions'] = get_role_permissions(tenant_info['role'])
            
            # Generate Allow policy
            policy = generate_policy(user_email, 'Allow', event['methodArn'], tenant_info)
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
    
    # Pass tenant context to downstream Lambda
    if context:
        auth_response['context'] = {
            'tenant_id': context.get('tenant_id', ''),
            'user_id': context.get('user_id', ''),
            'role': context.get('role', ''),
            'permissions': ','.join(context.get('permissions', []))
        }
    
    return auth_response
