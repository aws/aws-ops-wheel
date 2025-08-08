"""
AWS Ops Wheel v2 - Selection Algorithms Lambda Function Wrapper
Routes requests to the appropriate handler functions from the layer
"""

import sys
import json
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/api-v2')

# Import the specific functions from the layer
from selection_algorithms import suggest_participant, get_selection_probabilities

# Define the route mapping
ROUTE_MAP = {
    ('POST', '/app/api/v2/wheels/{wheel_id}/suggest'): suggest_participant,
    ('GET', '/app/api/v2/wheels/{wheel_id}/probabilities'): get_selection_probabilities
}

def lambda_handler(event, context):
    """
    Routes requests to the appropriate selection algorithm functions
    """
    try:
        method = event.get('httpMethod')
        path = event.get('resource')
        handler = ROUTE_MAP.get((method, path))
        
        if not handler:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Route not found: {method} {path}'})
            }
        
        return handler(event, context)
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }
