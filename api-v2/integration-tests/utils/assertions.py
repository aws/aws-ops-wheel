"""
Custom Assertions for AWS Ops Wheel v2 Integration Tests
"""
from typing import Dict, Any, List, Optional, Union
from .api_client import APIResponse


class AssertionError(Exception):
    """Custom assertion error"""
    pass


class APIAssertions:
    """Custom assertions for API testing"""
    
    @staticmethod
    def assert_status_code(response: APIResponse, expected_status: int, 
                          message: Optional[str] = None):
        """
        Assert response status code
        
        Args:
            response: API response
            expected_status: Expected status code
            message: Custom error message
        """
        if response.status_code != expected_status:
            error_msg = message or (
                f"Expected status {expected_status}, got {response.status_code}. "
                f"Response: {response.text[:200]}"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_success_response(response: APIResponse, message: Optional[str] = None):
        """
        Assert response is successful (2xx)
        
        Args:
            response: API response
            message: Custom error message
        """
        if not response.is_success:
            error_msg = message or (
                f"Expected successful response, got {response.status_code}. "
                f"Response: {response.text[:200]}"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_json_response(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains valid JSON
        
        Args:
            response: API response
            message: Custom error message
        """
        if response.json_data is None:
            error_msg = message or (
                f"Expected JSON response, got: {response.text[:200]}"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_response_contains(response: APIResponse, key: str, 
                               message: Optional[str] = None):
        """
        Assert response JSON contains specific key
        
        Args:
            response: API response
            key: Expected key in response
            message: Custom error message
        """
        APIAssertions.assert_json_response(response)
        
        if key not in response.json_data:
            error_msg = message or (
                f"Response missing key '{key}'. Available keys: {list(response.json_data.keys())}"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_response_value(response: APIResponse, key: str, expected_value: Any,
                            message: Optional[str] = None):
        """
        Assert response JSON contains specific key-value pair
        
        Args:
            response: API response
            key: Key to check
            expected_value: Expected value
            message: Custom error message
        """
        APIAssertions.assert_response_contains(response, key)
        
        actual_value = response.json_data[key]
        if actual_value != expected_value:
            error_msg = message or (
                f"Expected {key}='{expected_value}', got '{actual_value}'"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_response_type(response: APIResponse, key: str, expected_type: type,
                           message: Optional[str] = None):
        """
        Assert response JSON value has expected type
        
        Args:
            response: API response
            key: Key to check
            expected_type: Expected type
            message: Custom error message
        """
        APIAssertions.assert_response_contains(response, key)
        
        actual_value = response.json_data[key]
        if not isinstance(actual_value, expected_type):
            error_msg = message or (
                f"Expected {key} to be {expected_type.__name__}, got {type(actual_value).__name__}"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_response_list_length(response: APIResponse, key: str, expected_length: int,
                                  message: Optional[str] = None):
        """
        Assert response JSON list has expected length
        
        Args:
            response: API response
            key: Key containing list
            expected_length: Expected list length
            message: Custom error message
        """
        APIAssertions.assert_response_type(response, key, list)
        
        actual_length = len(response.json_data[key])
        if actual_length != expected_length:
            error_msg = message or (
                f"Expected {key} to have {expected_length} items, got {actual_length}"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_error_response(response: APIResponse, expected_status: int,
                            expected_error_type: Optional[str] = None,
                            message: Optional[str] = None):
        """
        Assert response is an error with expected details
        
        Args:
            response: API response
            expected_status: Expected error status code
            expected_error_type: Expected error type in response
            message: Custom error message
        """
        APIAssertions.assert_status_code(response, expected_status)
        APIAssertions.assert_json_response(response)
        
        if expected_error_type:
            error_field = None
            for field in ['error', 'error_type', 'type', 'message']:
                if field in response.json_data:
                    error_field = field
                    break
            
            if not error_field:
                error_msg = message or "Error response missing error type field"
                raise AssertionError(error_msg)
            
            actual_error = response.json_data[error_field]
            if expected_error_type not in str(actual_error).lower():
                error_msg = message or (
                    f"Expected error type '{expected_error_type}', got '{actual_error}'"
                )
                raise AssertionError(error_msg)
    
    @staticmethod
    def assert_pagination_response(response: APIResponse, expected_page_size: Optional[int] = None,
                                 message: Optional[str] = None):
        """
        Assert response contains pagination metadata
        
        Args:
            response: API response
            expected_page_size: Expected page size
            message: Custom error message
        """
        APIAssertions.assert_success_response(response)
        APIAssertions.assert_json_response(response)
        
        # Check for common pagination fields
        pagination_fields = ['items', 'data', 'results']
        data_field = None
        
        for field in pagination_fields:
            if field in response.json_data:
                data_field = field
                break
        
        if not data_field:
            error_msg = message or f"Response missing data field. Available: {list(response.json_data.keys())}"
            raise AssertionError(error_msg)
        
        # Check pagination metadata
        meta_fields = ['total', 'count', 'page', 'total_pages', 'has_more', 'next_page']
        found_meta = any(field in response.json_data for field in meta_fields)
        
        if not found_meta:
            # Some APIs don't include metadata, just check data is list
            APIAssertions.assert_response_type(response, data_field, list)
        
        if expected_page_size is not None:
            actual_size = len(response.json_data[data_field])
            if actual_size > expected_page_size:
                error_msg = message or (
                    f"Response contains {actual_size} items, expected max {expected_page_size}"
                )
                raise AssertionError(error_msg)
    
    @staticmethod
    def assert_wheel_group_structure(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains valid wheel group structure
        
        Args:
            response: API response
            message: Custom error message
        """
        APIAssertions.assert_success_response(response)
        APIAssertions.assert_json_response(response)
        
        required_fields = ['wheel_group_id', 'wheel_group_name', 'created_at']
        for field in required_fields:
            APIAssertions.assert_response_contains(response, field, 
                message or f"Wheel group missing required field: {field}")
    
    @staticmethod
    def assert_public_wheel_group_structure(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains valid public wheel group creation structure
        
        Expected format:
        {
            "wheel_group": {
                "wheel_group_id": "...",
                "wheel_group_name": "...",
                "created_at": "..."
            },
            "admin_user": {
                "user_id": "...",
                "email": "...", 
                "name": "...",
                "role": "ADMIN"
            },
            "message": "..."
        }
        
        Args:
            response: API response
            message: Custom error message
        """
        APIAssertions.assert_success_response(response)
        APIAssertions.assert_json_response(response)
        
        # Check for main structure
        APIAssertions.assert_response_contains(response, 'wheel_group', 
            message or "Public wheel group response missing 'wheel_group' field")
        APIAssertions.assert_response_contains(response, 'admin_user',
            message or "Public wheel group response missing 'admin_user' field")
        
        # Validate nested wheel group structure
        wheel_group = response.json_data['wheel_group']
        required_wg_fields = ['wheel_group_id', 'wheel_group_name', 'created_at']
        for field in required_wg_fields:
            if field not in wheel_group:
                error_msg = message or f"Public wheel group missing required field in wheel_group: {field}"
                raise AssertionError(error_msg)
        
        # Validate admin user structure
        admin_user = response.json_data['admin_user']
        required_user_fields = ['user_id', 'email', 'name', 'role']
        for field in required_user_fields:
            if field not in admin_user:
                error_msg = message or f"Public wheel group missing required field in admin_user: {field}"
                raise AssertionError(error_msg)
    
    @staticmethod
    def assert_wheel_structure(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains valid wheel structure
        
        Args:
            response: API response
            message: Custom error message
        """
        APIAssertions.assert_success_response(response)
        APIAssertions.assert_json_response(response)
        
        required_fields = ['wheel_id', 'wheel_name', 'wheel_group_id', 'created_at']
        for field in required_fields:
            APIAssertions.assert_response_contains(response, field,
                message or f"Wheel missing required field: {field}")
    
    @staticmethod
    def assert_participant_structure(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains valid participant structure
        
        Args:
            response: API response
            message: Custom error message
        """
        APIAssertions.assert_success_response(response)
        APIAssertions.assert_json_response(response)
        
        required_fields = ['participant_id', 'participant_name', 'wheel_group_wheel_id', 'created_at']
        for field in required_fields:
            APIAssertions.assert_response_contains(response, field,
                message or f"Participant missing required field: {field}")
    
    @staticmethod
    def assert_user_structure(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains valid user structure
        
        Args:
            response: API response  
            message: Custom error message
        """
        APIAssertions.assert_success_response(response)
        APIAssertions.assert_json_response(response)
        
        required_fields = ['user_id', 'username', 'email', 'created_at']
        for field in required_fields:
            APIAssertions.assert_response_contains(response, field,
                message or f"User missing required field: {field}")
    
    @staticmethod
    def assert_jwt_token_structure(token_data: Dict[str, Any], message: Optional[str] = None):
        """
        Assert JWT token data contains required fields
        
        Args:
            token_data: Decoded token data
            message: Custom error message
        """
        required_fields = ['access_token', 'token_type']
        for field in required_fields:
            if field not in token_data:
                error_msg = message or f"Token response missing field: {field}"
                raise AssertionError(error_msg)
        
        # Verify token format
        token = token_data['access_token']
        if not isinstance(token, str) or len(token.split('.')) != 3:
            error_msg = message or f"Invalid JWT token format: {token[:50]}..."
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_response_time(response: APIResponse, max_seconds: float,
                           message: Optional[str] = None):
        """
        Assert response time is within acceptable limits
        
        Args:
            response: API response
            max_seconds: Maximum acceptable response time
            message: Custom error message
        """
        if response.response_time is None:
            error_msg = message or "Response time not available"
            raise AssertionError(error_msg)
        
        if response.response_time > max_seconds:
            error_msg = message or (
                f"Response took {response.response_time:.3f}s, expected max {max_seconds}s"
            )
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_cors_headers(response: APIResponse, message: Optional[str] = None):
        """
        Assert response contains proper CORS headers
        
        Args:
            response: API response
            message: Custom error message
        """
        required_cors_headers = [
            'access-control-allow-origin',
            'access-control-allow-methods',
            'access-control-allow-headers'
        ]
        
        missing_headers = []
        for header in required_cors_headers:
            if header not in [h.lower() for h in response.headers.keys()]:
                missing_headers.append(header)
        
        if missing_headers:
            error_msg = message or f"Missing CORS headers: {missing_headers}"
            raise AssertionError(error_msg)
    
    @staticmethod
    def assert_no_sensitive_data_exposure(response: APIResponse, 
                                        sensitive_fields: Optional[List[str]] = None,
                                        message: Optional[str] = None):
        """
        Assert response doesn't expose sensitive data
        
        Args:
            response: API response
            sensitive_fields: List of sensitive field names to check for
            message: Custom error message
        """
        if not sensitive_fields:
            sensitive_fields = ['password', 'secret', 'key', 'token', 'credential']
        
        if not response.json_data:
            return
        
        response_str = str(response.json_data).lower()
        exposed_fields = []
        
        for field in sensitive_fields:
            if field.lower() in response_str:
                exposed_fields.append(field)
        
        if exposed_fields:
            error_msg = message or f"Response may expose sensitive data: {exposed_fields}"
            raise AssertionError(error_msg)
