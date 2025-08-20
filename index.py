"""
AWS Ops Wheel v2 - Lambda Function Handler
Refactored for better maintainability and cleaner architecture
"""

import json
import logging
import os
import sys
from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add Lambda layer paths
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/api-v2')

# Import handlers
from wheel_group_middleware import wheel_group_middleware
from wheel_group_management import lambda_handlers as wheel_group_handlers
from wheel_operations import lambda_handlers as wheel_handlers
from participant_operations import lambda_handlers as participant_handlers
from selection_algorithms import lambda_handlers as selection_handlers
from deployment_admin_operations import lambda_handlers as admin_handlers


class HttpMethod(Enum):
    """HTTP method enumeration"""
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    OPTIONS = 'OPTIONS'


class StatusCode(Enum):
    """HTTP status code enumeration"""
    OK = 200
    NOT_FOUND = 404
    INTERNAL_ERROR = 500


@dataclass
class Route:
    """Route configuration"""
    patterns: list
    handler: Callable
    methods: list
    auth_required: bool = True


class CorsHelper:
    """Helper class for CORS handling"""
    
    DEFAULT_HEADERS = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }
    
    OPTIONS_HEADERS = {
        **DEFAULT_HEADERS,
        'Access-Control-Max-Age': '86400'
    }
    
    @classmethod
    def create_response(cls, status_code: int, body: Any, additional_headers: Dict = None) -> Dict:
        """Create standardized CORS response"""
        headers = cls.DEFAULT_HEADERS.copy()
        if additional_headers:
            headers.update(additional_headers)
        
        return {
            'statusCode': status_code,
            'headers': headers,
            'body': json.dumps(body) if isinstance(body, (dict, list)) else body
        }
    
    @classmethod
    def create_options_response(cls) -> Dict:
        """Create standardized OPTIONS response for CORS preflight"""
        return {
            'statusCode': StatusCode.OK.value,
            'headers': cls.OPTIONS_HEADERS,
            'body': ''
        }


class RequestParser:
    """Helper class for parsing requests"""
    
    @staticmethod
    def parse_body(event: Dict) -> None:
        """Parse request body, handling both string and dict formats"""
        if 'body' not in event:
            event['body'] = {}
            return
        
        body = event['body']
        if isinstance(body, str):
            try:
                event['body'] = json.loads(body) if body.strip() else {}
            except (json.JSONDecodeError, TypeError, ValueError):
                event['body'] = {}
    
    @staticmethod
    def get_request_info(event: Dict) -> Tuple[str, str, str]:
        """Extract and normalize request information from event"""
        http_method = event.get('httpMethod', HttpMethod.GET.value)
        resource_path = event.get('resource', '')
        path_info = event.get('path', '')
        request_path = path_info if path_info else resource_path
        
        return http_method, resource_path, request_path


class AuthenticationManager:
    """Handles authentication logic"""
    
    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = [
        '/v2/config', 
        '/app/api/v2/config', 
        '/v2/wheel-group/create-public', 
        '/app/api/v2/wheel-group/create-public'
    ]
    
    @classmethod
    def is_public_endpoint(cls, request_path: str) -> bool:
        """Check if the endpoint is public and doesn't require authentication"""
        # Strip stage prefix (e.g., /dev/) from request path for comparison
        path_without_stage = request_path
        if request_path.startswith(('/dev/', '/prod/', '/staging/')):
            path_without_stage = '/' + '/'.join(request_path.split('/')[2:])
        
        # Check for public endpoints
        public_checks = [
            '/config' in path_without_stage,
            '/wheel-group/create-public' in path_without_stage,
            'create-public' in path_without_stage,
            path_without_stage.endswith('/config'),
            path_without_stage.endswith('/create-public')
        ]
        
        return any(public_checks)
    
    @classmethod
    def authenticate_request(cls, event: Dict, context: Any, request_path: str) -> Any:
        """Apply authentication middleware for protected endpoints"""
        if cls.is_public_endpoint(request_path):
            logger.info(f"Path {request_path} is public, skipping authentication")
            return event
        
        logger.info(f"Path {request_path} requires authentication")
        auth_result = wheel_group_middleware(event, context)
        
        if isinstance(auth_result, dict) and 'statusCode' in auth_result:
            logger.warning(f"Authentication failed for path {request_path}")
            return auth_result
        
        logger.info("Authentication succeeded")
        return auth_result


class RouteRegistry:
    """Central registry for all API routes"""
    
    def __init__(self):
        self.routes = []
        self._register_routes()
    
    def _register_routes(self):
        """Register all application routes"""
        
        # Config and auth routes
        self.register_route(['/config', '/v2/config', '/app/api/v2/config'], wheel_group_handlers['get_config'], [HttpMethod.GET], auth_required=False)
        self.register_route(['/auth/me', '/v2/auth/me', '/app/api/v2/auth/me'], wheel_group_handlers['get_current_user'], [HttpMethod.GET])
        
        # Admin routes - MUST be registered BEFORE general wheel-group routes to avoid conflicts
        # Admin routes use custom authentication logic and don't require wheel group middleware
        self.register_route(
            ['/admin/wheel-groups', '/v2/admin/wheel-groups', '/app/api/v2/admin/wheel-groups'], 
            admin_handlers['list_all_wheel_groups'], 
            [HttpMethod.GET],
            auth_required=False  # Admin routes handle their own authentication
        )
        self.register_route(
            ['/admin/wheel-groups/{wheel_group_id}', '/v2/admin/wheel-groups/{wheel_group_id}', '/app/api/v2/admin/wheel-groups/{wheel_group_id}'], 
            admin_handlers['delete_wheel_group'], 
            [HttpMethod.DELETE],
            auth_required=False  # Admin routes handle their own authentication
        )
        
        # Wheel group routes
        self.register_route(
            ['/wheel-group/create-public', '/v2/wheel-group/create-public', '/app/api/v2/wheel-group/create-public'], 
            wheel_group_handlers['create_wheel_group_public'], 
            [HttpMethod.POST], 
            auth_required=False
        )
        self.register_route(
            ['/wheel-group/delete-recursive', '/v2/wheel-group/delete-recursive', '/app/api/v2/wheel-group/delete-recursive'], 
            wheel_group_handlers['delete_wheel_group_recursive'], 
            [HttpMethod.DELETE]
        )
        self.register_route(
            ['/wheel-group', '/v2/wheel-group', '/app/api/v2/wheel-group'], 
            self._create_wheel_group_handler(), 
            [HttpMethod.GET, HttpMethod.POST, HttpMethod.PUT]
        )
        self.register_route(
            ['/app/api/v2/wheel-group/users', '/v2/wheel-group/users'], 
            self._create_wheel_group_users_handler(), 
            [HttpMethod.GET, HttpMethod.POST]
        )
        self.register_route(
            ['/app/api/v2/wheel-group/users/{user_id}', '/v2/wheel-group/users/{user_id}'], 
            wheel_group_handlers['delete_wheel_group_user'], 
            [HttpMethod.DELETE]
        )
        self.register_route(
            ['/app/api/v2/wheel-group/users/{user_id}/role', '/v2/wheel-group/users/{user_id}/role'], 
            wheel_group_handlers['update_user_role'], 
            [HttpMethod.PUT]
        )
        
        # Wheel routes
        self.register_route(
            ['/v2/wheels', '/app/api/v2/wheels'], 
            self._create_wheels_handler(), 
            [HttpMethod.GET, HttpMethod.POST]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}', '/app/api/v2/wheels/{wheel_id}'], 
            self._create_wheel_by_id_handler(), 
            [HttpMethod.GET, HttpMethod.PUT, HttpMethod.DELETE]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}/reset', '/app/api/v2/wheels/{wheel_id}/reset'], 
            wheel_handlers['reset_wheel_weights'], 
            [HttpMethod.POST]
        )
        
        # Participant routes
        self.register_route(
            ['/v2/wheels/{wheel_id}/participants', '/app/api/v2/wheels/{wheel_id}/participants'], 
            self._create_participants_handler(), 
            [HttpMethod.GET, HttpMethod.POST]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}/participants/{participant_id}', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}'], 
            self._create_participant_by_id_handler(), 
            [HttpMethod.GET, HttpMethod.PUT, HttpMethod.DELETE]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}/participants/{participant_id}/rig', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}/rig'], 
            participant_handlers['rig_participant'], 
            [HttpMethod.POST]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}/participants/{participant_id}/select', '/app/api/v2/wheels/{wheel_id}/participants/{participant_id}/select'], 
            participant_handlers['select_participant'], 
            [HttpMethod.POST]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}/unrig', '/app/api/v2/wheels/{wheel_id}/unrig'], 
            participant_handlers['remove_rigging'], 
            [HttpMethod.DELETE]
        )
        
        # Selection algorithm routes
        self.register_route(
            ['/v2/wheels/{wheel_id}/suggest', '/app/api/v2/wheels/{wheel_id}/suggest'], 
            selection_handlers['suggest_participant'], 
            [HttpMethod.POST]
        )
        self.register_route(
            ['/v2/wheels/{wheel_id}/probabilities', '/app/api/v2/wheels/{wheel_id}/probabilities'], 
            selection_handlers['get_selection_probabilities'], 
            [HttpMethod.GET]
        )
    
    def register_route(self, patterns: list, handler: Callable, methods: list, auth_required: bool = True):
        """Register a new route"""
        route = Route(patterns, handler, methods, auth_required)
        self.routes.append(route)
    
    def find_route(self, request_path: str, method: str) -> Optional[Route]:
        """Find matching route for request"""
        # Strip stage prefix (e.g., /dev1/, /prod/, /staging/) from request path for routing
        path_without_stage = request_path
        if request_path.startswith(('/dev/', '/dev1/', '/dev2/', '/prod/', '/staging/')):
            path_parts = request_path.split('/')
            if len(path_parts) > 2:
                path_without_stage = '/' + '/'.join(path_parts[2:])
        
        logger.info(f"[ROUTING DEBUG] Original path: {request_path}, Path without stage: {path_without_stage}")
        
        for route in self.routes:
            if self._matches_pattern(path_without_stage, route.patterns) and HttpMethod(method) in route.methods:
                return route
        return None
    
    def _matches_pattern(self, request_path: str, patterns: list) -> bool:
        """Check if request path matches any of the route patterns"""
        for pattern in patterns:
            if self._match_single_pattern(request_path, pattern):
                return True
        return False
    
    def _match_single_pattern(self, request_path: str, pattern: str) -> bool:
        """Check if request path matches a single pattern"""
        logger.info(f"[ROUTING DEBUG] Matching pattern '{pattern}' against path '{request_path}'")
        
        # Handle exact matches first
        if pattern == request_path:
            logger.info(f"[ROUTING DEBUG] Exact match: {pattern} == {request_path}")
            return True
        
        # Handle patterns with path variables (e.g., {wheel_id})
        if '{' in pattern and '}' in pattern:
            pattern_parts = pattern.split('/')
            path_parts = request_path.split('/')
            
            if len(pattern_parts) != len(path_parts):
                logger.info(f"[ROUTING DEBUG] Path variable pattern length mismatch: {len(pattern_parts)} != {len(path_parts)}")
                return False
            
            for pattern_part, path_part in zip(pattern_parts, path_parts):
                if pattern_part.startswith('{') and pattern_part.endswith('}'):
                    continue  # Skip path variables
                elif pattern_part != path_part:
                    logger.info(f"[ROUTING DEBUG] Path variable pattern part mismatch: {pattern_part} != {path_part}")
                    return False
            logger.info(f"[ROUTING DEBUG] Path variable pattern matched!")
            return True
        
        # Handle special endpoint matching (but be precise to avoid conflicts)
        # Only use contains matching for very specific cases
        if pattern == '/config' and request_path.endswith('/config'):
            logger.info(f"[ROUTING DEBUG] Config pattern matched")
            return True
        if pattern == '/auth/me' and request_path.endswith('/auth/me'):
            logger.info(f"[ROUTING DEBUG] Auth/me pattern matched")
            return True
        
        # For wheel-group patterns, be more specific to avoid conflicts with admin routes
        if pattern == '/wheel-group':
            # Only match if it ends with /wheel-group (not /admin/wheel-groups)
            match = (request_path.endswith('/wheel-group') and 
                    '/admin/wheel-group' not in request_path and
                    '/admin/wheel-groups' not in request_path)
            logger.info(f"[ROUTING DEBUG] Wheel-group pattern check: ends with /wheel-group: {request_path.endswith('/wheel-group')}, has admin: {'/admin/wheel-group' in request_path or '/admin/wheel-groups' in request_path}, match: {match}")
            return match
        
        logger.info(f"[ROUTING DEBUG] No pattern match for '{pattern}' against '{request_path}'")
        return False
    
    # Handler creation methods for multi-method routes
    def _create_wheel_group_handler(self):
        def handler(event, context):
            method = event.get('httpMethod')
            if method == HttpMethod.GET.value:
                return wheel_group_handlers['get_wheel_group'](event, context)
            elif method == HttpMethod.POST.value:
                return wheel_group_handlers['create_wheel_group'](event, context)
            elif method == HttpMethod.PUT.value:
                return wheel_group_handlers['update_wheel_group'](event, context)
            return CorsHelper.create_response(StatusCode.NOT_FOUND.value, {'error': 'Method not allowed'})
        return handler
    
    def _create_wheel_group_users_handler(self):
        def handler(event, context):
            method = event.get('httpMethod')
            if method == HttpMethod.GET.value:
                return wheel_group_handlers['get_wheel_group_users'](event, context)
            elif method == HttpMethod.POST.value:
                return wheel_group_handlers['create_wheel_group_user'](event, context)
            return CorsHelper.create_response(StatusCode.NOT_FOUND.value, {'error': 'Method not allowed'})
        return handler
    
    def _create_wheels_handler(self):
        def handler(event, context):
            method = event.get('httpMethod')
            if method == HttpMethod.GET.value:
                return wheel_handlers['list_wheel_group_wheels'](event, context)
            elif method == HttpMethod.POST.value:
                return wheel_handlers['create_wheel'](event, context)
            return CorsHelper.create_response(StatusCode.NOT_FOUND.value, {'error': 'Method not allowed'})
        return handler
    
    def _create_wheel_by_id_handler(self):
        def handler(event, context):
            method = event.get('httpMethod')
            if method == HttpMethod.GET.value:
                return wheel_handlers['get_wheel'](event, context)
            elif method == HttpMethod.PUT.value:
                return wheel_handlers['update_wheel'](event, context)
            elif method == HttpMethod.DELETE.value:
                return wheel_handlers['delete_wheel'](event, context)
            return CorsHelper.create_response(StatusCode.NOT_FOUND.value, {'error': 'Method not allowed'})
        return handler
    
    def _create_participants_handler(self):
        def handler(event, context):
            method = event.get('httpMethod')
            if method == HttpMethod.GET.value:
                return participant_handlers['list_wheel_participants'](event, context)
            elif method == HttpMethod.POST.value:
                return participant_handlers['create_participant'](event, context)
            return CorsHelper.create_response(StatusCode.NOT_FOUND.value, {'error': 'Method not allowed'})
        return handler
    
    def _create_participant_by_id_handler(self):
        def handler(event, context):
            method = event.get('httpMethod')
            if method == HttpMethod.GET.value:
                return participant_handlers['get_participant'](event, context)
            elif method == HttpMethod.PUT.value:
                return participant_handlers['update_participant'](event, context)
            elif method == HttpMethod.DELETE.value:
                return participant_handlers['delete_participant'](event, context)
            return CorsHelper.create_response(StatusCode.NOT_FOUND.value, {'error': 'Method not allowed'})
        return handler


class LambdaHandler:
    """Main Lambda handler class"""
    
    def __init__(self):
        self.route_registry = RouteRegistry()
        self.auth_manager = AuthenticationManager()
        self.request_parser = RequestParser()
    
    def handle_request(self, event: Dict, context: Any) -> Dict:
        """Handle incoming Lambda request"""
        try:
            logger.info("Lambda handler started")
            
            # Parse request body
            self.request_parser.parse_body(event)
            
            # Extract request information
            http_method, resource_path, request_path = self.request_parser.get_request_info(event)
            logger.info(f"Processing {http_method} {request_path}")
            
            # Handle OPTIONS requests for CORS preflight
            if http_method == HttpMethod.OPTIONS.value:
                return CorsHelper.create_options_response()
            
            # Find matching route
            route = self.route_registry.find_route(request_path, http_method)
            if not route:
                logger.warning(f"No route found for {http_method} {request_path}")
                return CorsHelper.create_response(
                    StatusCode.NOT_FOUND.value, 
                    {'error': f'Route not found: {http_method} {request_path}'}
                )
            
            # Authenticate request if needed
            if route.auth_required:
                auth_result = self.auth_manager.authenticate_request(event, context, request_path)
                if isinstance(auth_result, dict) and 'statusCode' in auth_result:
                    return auth_result  # Authentication failed
                event = auth_result  # Use authenticated event
            
            # Execute route handler
            logger.info(f"Executing handler for {http_method} {request_path}")
            return route.handler(event, context)
            
        except Exception as e:
            logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
            return CorsHelper.create_response(
                StatusCode.INTERNAL_ERROR.value, 
                {'error': f'Internal server error: {str(e)}'}
            )


# Global handler instance
_handler = LambdaHandler()


def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    Main Lambda handler entry point
    """
    return _handler.handle_request(event, context)
