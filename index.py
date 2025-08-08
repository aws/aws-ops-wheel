"""
Index file for participant operations Lambda function
Imports and exposes the main lambda handler
"""

from api_v2.lambda_function import lambda_handler

# Export the handler for Lambda runtime
__all__ = ['lambda_handler']
