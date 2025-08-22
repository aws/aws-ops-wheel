"""
AWS Cognito Authenticator for Integration Tests

Direct authentication with AWS Cognito User Pool using boto3 SDK.
This replaces fake API login endpoints with real Cognito authentication.
"""

import boto3
import time
import json
import base64
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError


class AuthenticationError(Exception):
    """Authentication-related errors"""
    pass


class CognitoAuthenticator:
    """Direct AWS Cognito authentication for integration tests"""
    
    def __init__(self, user_pool_id: str, client_id: str, region: str = 'us-west-2', debug: bool = False):
        """
        Initialize Cognito authenticator
        
        Args:
            user_pool_id: Cognito User Pool ID
            client_id: Cognito Client ID
            region: AWS region
            debug: Enable debug logging
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
        self.debug = debug
        self.cognito_client = boto3.client('cognito-idp', region_name=region)
        
    def _log(self, message: str):
        """Log debug message if debug is enabled"""
        if self.debug:
            print(f"[COGNITO_AUTH] {message}")
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with Cognito and return tokens
        
        Args:
            username: Username for authentication
            password: Password for authentication
            
        Returns:
            Dictionary containing tokens and user info
            
        Raises:
            AuthenticationError: If authentication fails
        """
        self._log(f"Authenticating user: {username}")
        
        try:
            # Use USER_PASSWORD_AUTH flow (requires client to be configured for this)
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            # Handle challenges (like password change requirements)
            if 'ChallengeName' in response:
                self._log(f"Challenge required: {response['ChallengeName']}")
                
                if response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
                    return self._handle_new_password_challenge(
                        response['Session'], username, password
                    )
                else:
                    raise AuthenticationError(f"Unsupported challenge: {response['ChallengeName']}")
            
            # Extract tokens from successful authentication
            auth_result = response['AuthenticationResult']
            access_token = auth_result['AccessToken']
            
            # Parse user info from ID token
            user_info = self._parse_id_token(auth_result.get('IdToken'))
            
            self._log(f"Authentication successful for user: {username}")
            
            return {
                'access_token': access_token,
                'id_token': auth_result.get('IdToken'),
                'refresh_token': auth_result.get('RefreshToken'),
                'token_type': auth_result.get('TokenType', 'Bearer'),
                'expires_in': auth_result.get('ExpiresIn', 3600),
                'user': user_info
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            self._log(f"Cognito authentication failed: {error_code} - {error_message}")
            
            if error_code == 'NotAuthorizedException':
                raise AuthenticationError("Invalid username or password")
            elif error_code == 'UserNotFoundException':
                raise AuthenticationError("User not found")
            elif error_code == 'UserNotConfirmedException':
                raise AuthenticationError("User account not confirmed")
            elif error_code == 'PasswordResetRequiredException':
                raise AuthenticationError("Password reset required")
            elif error_code == 'TooManyRequestsException':
                raise AuthenticationError("Too many authentication attempts, please try again later")
            else:
                raise AuthenticationError(f"Authentication failed: {error_message}")
        
        except Exception as e:
            self._log(f"Unexpected authentication error: {str(e)}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    def _handle_new_password_challenge(self, session: str, username: str, 
                                     new_password: str) -> Dict[str, Any]:
        """
        Handle NEW_PASSWORD_REQUIRED challenge
        
        Args:
            session: Challenge session from Cognito
            username: Username
            new_password: New password to set
            
        Returns:
            Authentication result with tokens
        """
        self._log(f"Handling NEW_PASSWORD_REQUIRED challenge for: {username}")
        
        try:
            response = self.cognito_client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName='NEW_PASSWORD_REQUIRED',
                Session=session,
                ChallengeResponses={
                    'USERNAME': username,
                    'NEW_PASSWORD': new_password
                }
            )
            
            auth_result = response['AuthenticationResult']
            access_token = auth_result['AccessToken']
            
            # Parse user info from ID token
            user_info = self._parse_id_token(auth_result.get('IdToken'))
            
            self._log(f"Password change successful for user: {username}")
            
            return {
                'access_token': access_token,
                'id_token': auth_result.get('IdToken'),
                'refresh_token': auth_result.get('RefreshToken'),
                'token_type': auth_result.get('TokenType', 'Bearer'),
                'expires_in': auth_result.get('ExpiresIn', 3600),
                'user': user_info,
                'password_changed': True
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            self._log(f"Password change failed: {error_code} - {error_message}")
            raise AuthenticationError(f"Password change failed: {error_message}")
    
    def _parse_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Parse user information from ID token (without signature verification)
        
        Args:
            id_token: JWT ID token from Cognito
            
        Returns:
            User information dictionary
        """
        if not id_token:
            return None
            
        try:
            # Split token into parts
            parts = id_token.split('.')
            if len(parts) != 3:
                self._log("Invalid JWT format in ID token")
                return None
            
            # Decode payload (middle part)
            payload_encoded = parts[1]
            # Add padding if necessary
            payload_encoded += '=' * (4 - len(payload_encoded) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_encoded)
            payload = json.loads(payload_bytes.decode('utf-8'))
            
            # Extract user information
            user_info = {
                'user_id': payload.get('sub'),
                'email': payload.get('email'),
                'name': payload.get('name'),
                'username': payload.get('cognito:username'),
                'email_verified': payload.get('email_verified'),
                'deployment_admin': payload.get('custom:deployment_admin') == 'true',
                'wheel_group_id': payload.get('custom:wheel_group_id'),
                'exp': payload.get('exp'),
                'iat': payload.get('iat')
            }
            
            self._log(f"Parsed user info: {user_info['email']} (ID: {user_info['user_id']})")
            return user_info
            
        except Exception as e:
            self._log(f"Failed to parse ID token: {str(e)}")
            return None
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token from previous authentication
            
        Returns:
            New tokens
            
        Raises:
            AuthenticationError: If token refresh fails
        """
        self._log("Refreshing access token")
        
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            
            auth_result = response['AuthenticationResult']
            access_token = auth_result['AccessToken']
            
            # Parse user info from new ID token
            user_info = self._parse_id_token(auth_result.get('IdToken'))
            
            self._log("Token refresh successful")
            
            return {
                'access_token': access_token,
                'id_token': auth_result.get('IdToken'),
                'token_type': auth_result.get('TokenType', 'Bearer'),
                'expires_in': auth_result.get('ExpiresIn', 3600),
                'user': user_info
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            self._log(f"Token refresh failed: {error_code} - {error_message}")
            raise AuthenticationError(f"Token refresh failed: {error_message}")
    
    def sign_out_user(self, access_token: str) -> bool:
        """
        Sign out user (invalidate token)
        
        Args:
            access_token: Current access token
            
        Returns:
            True if successful, False otherwise
        """
        self._log("Signing out user")
        
        try:
            self.cognito_client.global_sign_out(
                AccessToken=access_token
            )
            
            self._log("User signed out successfully")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            self._log(f"Sign out failed: {error_code} - {error_message}")
            return False
        
        except Exception as e:
            self._log(f"Sign out error: {str(e)}")
            return False
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information using access token
        
        Args:
            access_token: Valid access token
            
        Returns:
            User information
            
        Raises:
            AuthenticationError: If token is invalid
        """
        self._log("Getting user info from access token")
        
        try:
            response = self.cognito_client.get_user(
                AccessToken=access_token
            )
            
            # Convert attributes to dictionary
            user_info = {'username': response['Username']}
            for attr in response['UserAttributes']:
                name = attr['Name']
                value = attr['Value']
                
                # Convert custom: attributes to readable names
                if name.startswith('custom:'):
                    name = name[7:]  # Remove 'custom:' prefix
                
                user_info[name] = value
            
            self._log(f"Retrieved user info for: {user_info.get('email', 'unknown')}")
            return user_info
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            self._log(f"Get user info failed: {error_code} - {error_message}")
            raise AuthenticationError(f"Failed to get user info: {error_message}")
