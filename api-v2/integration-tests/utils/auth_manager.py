"""
Authentication Manager for AWS Ops Wheel v2 Integration Tests
"""
import json
import base64
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from utils.api_client import APIClient
from utils.cognito_authenticator import CognitoAuthenticator, AuthenticationError


class AuthManager:
    """
    Authentication manager for integration tests
    
    Handles user authentication, token management, and session state.
    Now uses direct AWS Cognito authentication instead of API endpoints.
    """
    
    def __init__(self, api_client: APIClient, debug: bool = False):
        """
        Initialize AuthManager
        
        Args:
            api_client: API client instance for making requests
            debug: Enable debug logging
        """
        self.api_client = api_client
        self.debug = debug
        self._current_token = None
        self._token_expiry = None
        self._user_info = None
        self.cognito_authenticator = None  # Will be injected by conftest.py
        
        # Store credentials for re-authentication (session persistence)
        self._stored_credentials = None
        
    def _log(self, message: str):
        """Log debug message if debug is enabled"""
        if self.debug:
            print(f"[AUTH] {message}")
    
    def _decode_jwt_payload(self, token: str) -> Dict[str, Any]:
        """
        Decode JWT payload without verification (for inspection only)
        
        Args:
            token: JWT token
            
        Returns:
            Decoded payload
        """
        try:
            # Split token into parts
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            
            # Decode payload (second part)
            payload = parts[1]
            
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            # Decode base64
            decoded_bytes = base64.urlsafe_b64decode(payload)
            payload_dict = json.loads(decoded_bytes)
            
            return payload_dict
            
        except Exception as e:
            self._log(f"Failed to decode JWT payload: {e}")
            return {}
    
    def _extract_token_info(self, token: str) -> Tuple[Optional[float], Optional[Dict]]:
        """
        Extract expiry time and user info from JWT token
        
        Args:
            token: JWT token
            
        Returns:
            Tuple of (expiry_timestamp, user_info)
        """
        payload = self._decode_jwt_payload(token)
        
        # Extract expiry time
        expiry = payload.get('exp')
        if expiry:
            expiry = float(expiry)
        
        # Extract user info
        user_info = {
            'username': payload.get('cognito:username'),
            'email': payload.get('email'),
            'email_verified': payload.get('email_verified'),
            'deployment_admin': payload.get('custom:deployment_admin'),
            'user_id': payload.get('sub'),
            'token_use': payload.get('token_use'),
            'issued_at': payload.get('iat'),
            'expires_at': payload.get('exp')
        }
        
        return expiry, user_info
    
    def login(self, username: str, password: str, new_password: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform login using AWS Cognito SDK
        
        Args:
            username: Username
            password: Current password
            new_password: New password (if password change is required)
            
        Returns:
            Login response data
            
        Raises:
            AuthenticationError: If login fails
        """
        self._log(f"Authenticating with Cognito: {username}")
        
        if not self.cognito_authenticator:
            raise AuthenticationError("Cognito authenticator not configured")
        
        try:
            # Use CognitoAuthenticator for direct auth
            tokens = self.cognito_authenticator.authenticate_user(username, password)
            
            # Extract ID token for API Gateway (contains required aud, iss claims)
            id_token = tokens['id_token']
            expiry, _ = self._extract_token_info(id_token)
            
            # Use user info from CognitoAuthenticator (parsed from ID token)
            # This includes custom attributes like deployment_admin
            user_info = tokens.get('user', {})
            
            # Set ID token in API client (API Gateway authorizer expects ID tokens)
            self.api_client.set_auth_token(id_token, expiry)
            
            # Store authentication state
            self._current_token = id_token
            self._token_expiry = expiry
            self._user_info = user_info
            
            self._log(f"Authentication successful for: {username}")
            self._log(f"User info: {user_info}")
            return {
                'access_token': id_token,  # Return ID token as access_token for compatibility
                'user': user_info,
                'expires_in': tokens.get('expires_in', 3600),
                'password_changed': tokens.get('password_changed', False)
            }
            
        except Exception as e:
            raise AuthenticationError(f"Login failed: {str(e)}")
    
    def admin_login(self, admin_username: str, admin_password: str) -> Dict[str, Any]:
        """
        Perform admin login with automatic password change handling
        
        Args:
            admin_username: Admin username
            admin_password: Admin password
            
        Returns:
            Login response data
            
        Raises:
            AuthenticationError: If admin login fails
        """
        self._log(f"Performing admin login for: {admin_username}")
        
        try:
            # Store credentials for re-authentication
            self._stored_credentials = {
                'username': admin_username,
                'password': admin_password
            }
            
            # Try login with potential password change
            result = self.login(admin_username, admin_password)
            
            # Verify admin privileges
            if self.is_admin():
                self._log("Admin login successful - deployment admin privileges confirmed")
                return result
            else:
                self._log("Warning: User does not have deployment admin privileges")
                return result
                
        except AuthenticationError as e:
            self._log(f"Admin login failed: {e}")
            raise AuthenticationError(f"Admin login failed: {e}")
    
    def logout(self) -> bool:
        """
        Perform logout using Cognito (if available) or local cleanup
        
        Returns:
            True if logout successful
        """
        self._log("Performing logout")
        
        try:
            # Try Cognito sign out if authenticator and token are available
            if self.cognito_authenticator and self._current_token:
                try:
                    self.cognito_authenticator.sign_out_user(self._current_token)
                    self._log("Cognito sign out successful")
                except Exception as e:
                    self._log(f"Cognito sign out failed: {e}")
                    # Continue with local cleanup even if Cognito sign out fails
            
            # Clear local authentication state
            self._current_token = None
            self._token_expiry = None
            self._user_info = None
            
            # Clear token from API client
            self.api_client.clear_auth_token()
            
            self._log("Logout completed")
            return True
            
        except Exception as e:
            self._log(f"Logout failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated with valid token
        
        Returns:
            True if authenticated
        """
        if not self._current_token:
            return False
        
        if self._token_expiry and time.time() >= self._token_expiry:
            self._log("Token has expired")
            return False
        
        return True
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current user information
        
        Returns:
            User info dictionary or None
        """
        return self._user_info.copy() if self._user_info else None
    
    def get_current_token(self) -> Optional[str]:
        """
        Get current authentication token
        
        Returns:
            JWT token or None
        """
        return self._current_token
    
    def is_admin(self) -> bool:
        """
        Check if current user has admin privileges
        
        Returns:
            True if user is admin
        """
        if not self._user_info:
            return False
        
        # Check for both boolean True and string 'true'
        deployment_admin = self._user_info.get('deployment_admin')
        return deployment_admin is True or deployment_admin == 'true'
    
    def refresh_token_if_needed(self, buffer_seconds: int = 300) -> bool:
        """
        Refresh token if it's expiring soon
        
        Args:
            buffer_seconds: Refresh if token expires within this many seconds
            
        Returns:
            True if token is valid (refreshed if needed)
        """
        if not self._token_expiry:
            return self.is_authenticated()
        
        # Check if token needs refresh
        if time.time() + buffer_seconds >= self._token_expiry:
            self._log("Token expiring soon - refresh not implemented")
            # Note: Token refresh would need to be implemented based on your auth system
            return self.is_authenticated()
        
        return True
    
    def ensure_authenticated(self) -> bool:
        """
        Ensure valid authentication, re-authenticate if needed
        
        Returns:
            True if authenticated (after re-authentication if needed)
        """
        if self.is_authenticated():
            return True
        
        if self._stored_credentials:
            self._log("Token missing/expired - attempting re-authentication")
            try:
                self.admin_login(
                    self._stored_credentials['username'],
                    self._stored_credentials['password']
                )
                return self.is_authenticated()
            except AuthenticationError as e:
                self._log(f"Re-authentication failed: {e}")
                return False
        else:
            self._log("No stored credentials available for re-authentication")
            return False
    
    def _restore_authentication(self) -> bool:
        """
        Restore authentication using stored credentials
        
        Returns:
            True if authentication restored successfully
        """
        return self.ensure_authenticated()
    
    def create_test_user(self, username: str, email: str, password: str, 
                        wheel_group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a test user (requires admin authentication)
        
        Args:
            username: Username for new user
            email: Email for new user
            password: Password for new user
            wheel_group_id: Optional wheel group ID to associate user with
            
        Returns:
            User creation response
            
        Raises:
            AuthenticationError: If not authenticated as admin
        """
        if not self.is_admin():
            raise AuthenticationError("Admin authentication required to create users")
        
        self._log(f"Creating test user: {username}")
        
        user_data = {
            'username': username,
            'email': email,
            'password': password
        }
        
        if wheel_group_id:
            user_data['wheel_group_id'] = wheel_group_id
        
        try:
            response = self.api_client.post('/app/api/v2/admin/users', data=user_data)
            
            if response.is_success:
                self._log(f"Test user created successfully: {username}")
                return response.json_data
            else:
                raise AuthenticationError(f"Failed to create user: {response.text}")
                
        except Exception as e:
            self._log(f"User creation failed: {e}")
            raise AuthenticationError(f"User creation failed: {e}")
    
    def delete_test_user(self, user_id: str) -> bool:
        """
        Delete a test user (requires admin authentication)
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if deletion successful
            
        Raises:
            AuthenticationError: If not authenticated as admin
        """
        if not self.is_admin():
            raise AuthenticationError("Admin authentication required to delete users")
        
        self._log(f"Deleting test user: {user_id}")
        
        try:
            response = self.api_client.delete(f'/app/api/v2/admin/users/{user_id}')
            
            if response.is_success:
                self._log(f"Test user deleted successfully: {user_id}")
                return True
            else:
                self._log(f"Failed to delete user: {response.text}")
                return False
                
        except Exception as e:
            self._log(f"User deletion failed: {e}")
            return False
