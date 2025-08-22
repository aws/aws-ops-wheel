"""
AWS Ops Wheel v2 - API Gateway Authorizer Entry Point
This is the entry point for the Lambda authorizer function
"""

import sys
import os
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/api-v2')

def lambda_handler(event, context):
    """
    Authorizer Lambda handler - delegates to the layer implementation
    """
    try:
        # Import the module using importlib to handle hyphenated directory names
        import importlib.util
        
        # Try to load from the layer first
        module_path = '/opt/python/api-v2/api_gateway_authorizer.py'
        if os.path.exists(module_path):
            spec = importlib.util.spec_from_file_location("api_gateway_authorizer", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.lambda_handler(event, context)
        else:
            # Fallback: try direct import (for local testing)
            from api_gateway_authorizer import lambda_handler as authorizer_handler
            return authorizer_handler(event, context)
            
    except Exception as e:
        return {
            'principalId': 'user',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [{
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Deny',
                    'Resource': event['methodArn']
                }]
            }
        }
