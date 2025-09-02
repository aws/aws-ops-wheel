"""
HTTP API Client for AWS Ops Wheel v2 Integration Tests
"""
import json
import os
import time
import requests
from typing import Dict, Any, Optional, Union, List
from urllib3.exceptions import InsecureRequestWarning
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# CRITICAL FIX: Disable AWS request signing globally
# This prevents boto3/botocore from automatically signing HTTP requests
# which conflicts with Bearer token authentication to API Gateway
os.environ['AWS_SDK_LOAD_CONFIG'] = '0'  # Disable AWS config loading
os.environ['AWS_DEFAULT_REGION'] = ''    # Clear default region
if 'AWS_PROFILE' in os.environ:
    del os.environ['AWS_PROFILE']        # Remove AWS profile

# AGGRESSIVE FIX: Temporarily remove AWS credentials to prevent auto-signing
_original_aws_access_key = os.environ.pop('AWS_ACCESS_KEY_ID', None)
_original_aws_secret_key = os.environ.pop('AWS_SECRET_ACCESS_KEY', None)
_original_aws_session_token = os.environ.pop('AWS_SESSION_TOKEN', None)

# Store originals for potential restoration
if _original_aws_access_key:
    os.environ['_ORIGINAL_AWS_ACCESS_KEY_ID'] = _original_aws_access_key
if _original_aws_secret_key:
    os.environ['_ORIGINAL_AWS_SECRET_ACCESS_KEY'] = _original_aws_secret_key
if _original_aws_session_token:
    os.environ['_ORIGINAL_AWS_SESSION_TOKEN'] = _original_aws_session_token

# Monkey-patch to prevent botocore from signing requests
try:
    import botocore.auth
    import botocore.awsrequest
    
    # Store original methods
    _original_add_auth = getattr(botocore.auth.SigV4Auth, 'add_auth', None)
    _original_sign = getattr(botocore.awsrequest.AWSRequest, '__init__', None)
    
    # Disable SigV4 signing
    def disabled_add_auth(self, request):
        """Disabled AWS SigV4 signing to prevent conflicts with Bearer tokens"""
        pass
        
    if _original_add_auth:
        botocore.auth.SigV4Auth.add_auth = disabled_add_auth
        
except ImportError:
    # botocore not installed, which is fine
    pass

# Suppress SSL warnings for development
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class APIResponse:
    """Wrapper for API response data"""
    
    def __init__(self, response: requests.Response):
        self.response = response
        self.status_code = response.status_code
        self.headers = dict(response.headers)
        self.url = response.url
        
        # Parse JSON response
        try:
            self.json_data = response.json()
        except (json.JSONDecodeError, ValueError):
            self.json_data = None
            
        # Get text content
        self.text = response.text
        
        # Calculate response time
        self.response_time = getattr(response, 'elapsed', None)
        if self.response_time:
            self.response_time = self.response_time.total_seconds()
    
    @property
    def is_success(self) -> bool:
        """Check if response is successful (2xx)"""
        return 200 <= self.status_code < 300
    
    @property
    def is_client_error(self) -> bool:
        """Check if response is client error (4xx)"""
        return 400 <= self.status_code < 500
    
    @property
    def is_server_error(self) -> bool:
        """Check if response is server error (5xx)"""
        return 500 <= self.status_code < 600
    
    def __str__(self) -> str:
        return f"APIResponse(status={self.status_code}, url={self.url})"
    
    def __repr__(self) -> str:
        return f"APIResponse(status={self.status_code}, response_time={self.response_time}s)"


class APIClient:
    """HTTP client for AWS Ops Wheel v2 API integration testing"""
    
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3, 
                 retry_delay: float = 1.0, debug: bool = False):
        """
        Initialize API client
        
        Args:
            base_url: Base URL for API endpoints
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Delay between retries in seconds
            debug: Enable debug logging
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.debug = debug
        
        # CRITICAL FIX: Create a completely fresh session to avoid AWS signing
        # Use a new session class that bypasses any potential AWS request signing
        self.session = self._create_clean_session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            backoff_factor=retry_delay
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'AWS-Ops-Wheel-Integration-Tests/1.0'
        })
        
        # Authentication token storage
        self._auth_token = None
        self._token_expiry = None
    
    def _create_clean_session(self):
        """
        Create a completely clean requests session that bypasses AWS signing
        """
        # Create a new session instance
        session = requests.Session()
        
        # CRITICAL: Completely clear all hooks and auth mechanisms
        session.hooks.clear()
        session.auth = None
        
        # Override the request method to prevent any potential AWS signing
        original_request = session.request
        
        def clean_request(method, url, **kwargs):
            """Request wrapper that ensures no AWS auth is applied"""
            
            # Remove any auth parameter that might be added by other libraries
            kwargs.pop('auth', None)
            
            # Ensure we don't have any AWS-related headers
            headers = kwargs.get('headers', {})
            if isinstance(headers, dict):
                # Remove any potential AWS signing headers
                aws_headers = [k for k in headers.keys() if k.lower().startswith(('x-amz', 'aws-'))]
                for header in aws_headers:
                    headers.pop(header, None)
            
            # Call original request method
            return original_request(method, url, **kwargs)
        
        # Replace the request method
        session.request = clean_request
        
        if self.debug:
            print("[API_CLIENT] Created clean session to prevent AWS request signing")
        
        return session
        
    def set_auth_token(self, token: str, expiry_time: Optional[float] = None):
        """
        Set authentication token
        
        Args:
            token: JWT token
            expiry_time: Token expiry time (Unix timestamp)
        """
        self._auth_token = token
        self._token_expiry = expiry_time
        
        if token:
            auth_header = f'Bearer {token}'
            self.session.headers['Authorization'] = auth_header
            if self.debug:
                print(f"[API_CLIENT] Setting Authorization header: Bearer {token[:20]}...")
                print(f"[API_CLIENT] Full header length: {len(auth_header)}")
                print(f"[API_CLIENT] Token length: {len(token)}")
                print(f"[API_CLIENT] Token starts with: {token[:10]}")
        else:
            self.session.headers.pop('Authorization', None)
    
    def clear_auth_token(self):
        """Clear authentication token"""
        self.set_auth_token(None)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client has valid authentication token"""
        if not self._auth_token:
            return False
            
        if self._token_expiry and time.time() >= self._token_expiry:
            return False
            
        return True
    
    def _build_url(self, path: str) -> str:
        """
        Build full URL from path
        
        Args:
            path: API path
            
        Returns:
            Full URL
        """
        if not path.startswith('/'):
            path = '/' + path
        return f"{self.base_url}{path}"
    
    def _log_request(self, method: str, url: str, **kwargs):
        """Log request details if debug is enabled"""
        if self.debug:
            print(f"[API] {method.upper()} {url}")
            if 'json' in kwargs:
                print(f"[API] Request Body: {json.dumps(kwargs['json'], indent=2)}")
            if 'headers' in kwargs:
                headers = {k: v for k, v in kwargs['headers'].items() 
                          if k.lower() not in ['authorization']}
                print(f"[API] Headers: {headers}")
    
    def _log_response(self, response: APIResponse):
        """Log response details if debug is enabled"""
        if self.debug:
            print(f"[API] Response: {response.status_code} ({response.response_time:.3f}s)")
            if response.json_data:
                print(f"[API] Response Body: {json.dumps(response.json_data, indent=2)}")
            elif response.text and len(response.text) < 500:
                print(f"[API] Response Text: {response.text}")
    
    def request(self, method: str, path: str, **kwargs) -> APIResponse:
        """
        Make HTTP request
        
        Args:
            method: HTTP method
            path: API path
            **kwargs: Additional request parameters
            
        Returns:
            APIResponse object
        """
        url = self._build_url(path)
        
        # Set default timeout
        kwargs.setdefault('timeout', self.timeout)
        
        # Log request
        self._log_request(method, url, **kwargs)
        
        # CRITICAL FIX: Use curl subprocess to bypass AWS signing
        # This is a last resort to avoid AWS SDK/CLI automatic request signing
        if url.endswith('.execute-api.us-west-2.amazonaws.com/test') or '.execute-api.' in url:
            return self._curl_request(method, url, **kwargs)
        
        try:
            response = self.session.request(method, url, **kwargs)
            api_response = APIResponse(response)
            
            # Log response
            self._log_response(api_response)
            
            return api_response
            
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"[API] Request failed: {e}")
            raise
    
    def _curl_request(self, method: str, url: str, **kwargs) -> APIResponse:
        """
        Use curl subprocess to make request and bypass AWS signing
        """
        import subprocess
        import tempfile
        import json
        import time
        
        if self.debug:
            print(f"[API_CLIENT] Using curl to bypass AWS signing for: {method} {url}")
        
        # Build curl command
        curl_cmd = ['curl', '-s', '-w', '%{http_code}\\n%{time_total}\\n']
        
        # Add method
        curl_cmd.extend(['-X', method.upper()])
        
        # Add headers
        headers = kwargs.get('headers', {})
        # Merge session headers
        all_headers = {**self.session.headers, **headers}
        
        for key, value in all_headers.items():
            curl_cmd.extend(['-H', f'{key}: {value}'])
        
        # Add data for POST/PUT/PATCH
        data_file = None
        if 'json' in kwargs and kwargs['json']:
            data_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
            json.dump(kwargs['json'], data_file)
            data_file.close()
            curl_cmd.extend(['--data', f'@{data_file.name}'])
        
        # Add timeout
        timeout = kwargs.get('timeout', self.timeout)
        curl_cmd.extend(['--max-time', str(timeout)])
        
        # Add URL
        curl_cmd.append(url)
        
        try:
            start_time = time.time()
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=timeout+5)
            elapsed = time.time() - start_time
            
            if self.debug:
                print(f"[CURL] Command: {' '.join(curl_cmd[:10])}... (truncated)")
                print(f"[CURL] Return code: {result.returncode}")
                print(f"[CURL] Stdout length: {len(result.stdout)}")
                print(f"[CURL] Stderr: {result.stderr}")
            
            # Parse curl output - curl -w format gives: body + status_code + time
            output = result.stdout.strip()
            
            # The format is: <response_body><status_code>\n<time>
            # Split by newlines and extract the last line as time
            lines = output.split('\n')
            
            if len(lines) >= 2:
                # Last line is time
                response_time = float(lines[-1])
                
                # Everything except last line forms the body + status
                body_and_status = '\n'.join(lines[:-1])
                
                # Extract status code (last 3 digits) and body
                if len(body_and_status) >= 3 and body_and_status[-3:].isdigit():
                    status_code = int(body_and_status[-3:])
                    response_body = body_and_status[:-3]
                else:
                    # Fallback parsing
                    status_code = 500
                    response_body = body_and_status
            else:
                # Fallback for unexpected format
                status_code = 500
                response_time = elapsed
                response_body = output
            
            # Create mock response object
            class MockResponse:
                def __init__(self, status_code, text, elapsed):
                    self.status_code = status_code
                    self.text = text
                    self.headers = {}
                    self.url = url
                    self.elapsed = type('elapsed', (), {'total_seconds': lambda s: elapsed})()
                
                def json(self):
                    return json.loads(self.text) if self.text else {}
            
            mock_response = MockResponse(status_code, response_body, response_time)
            api_response = APIResponse(mock_response)
            
            # Log response
            self._log_response(api_response)
            
            return api_response
            
        except subprocess.TimeoutExpired:
            if self.debug:
                print(f"[CURL] Request timed out after {timeout}s")
            raise requests.exceptions.Timeout("Curl request timed out")
        except Exception as e:
            if self.debug:
                print(f"[CURL] Request failed: {e}")
            raise requests.exceptions.RequestException(f"Curl request failed: {e}")
        finally:
            # Clean up temp file
            if data_file:
                try:
                    import os
                    os.unlink(data_file.name)
                except:
                    pass
    
    def get(self, path: str, params: Optional[Dict] = None, **kwargs) -> APIResponse:
        """Make GET request"""
        if params:
            kwargs['params'] = params
        return self.request('GET', path, **kwargs)
    
    def post(self, path: str, data: Optional[Union[Dict, List]] = None, **kwargs) -> APIResponse:
        """Make POST request"""
        if data is not None:
            kwargs['json'] = data
        return self.request('POST', path, **kwargs)
    
    def put(self, path: str, data: Optional[Union[Dict, List]] = None, **kwargs) -> APIResponse:
        """Make PUT request"""
        if data is not None:
            kwargs['json'] = data
        return self.request('PUT', path, **kwargs)
    
    def patch(self, path: str, data: Optional[Union[Dict, List]] = None, **kwargs) -> APIResponse:
        """Make PATCH request"""
        if data is not None:
            kwargs['json'] = data
        return self.request('PATCH', path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> APIResponse:
        """Make DELETE request"""
        return self.request('DELETE', path, **kwargs)
    
    def health_check(self, timeout: int = 5) -> bool:
        """
        Perform basic health check
        
        Args:
            timeout: Request timeout
            
        Returns:
            True if API is healthy
        """
        try:
            response = self.get('/health', timeout=timeout)
            return response.is_success
        except:
            return False
    
    def close(self):
        """Close the session"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
