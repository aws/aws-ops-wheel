"""
Test Configuration Management for AWS Ops Wheel v2 Integration Tests
Environment Variable-Based Configuration for Dynamic Test Environments
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Try to load dotenv if available (for .env file support)
try:
    from dotenv import load_dotenv
    # Load .env file if it exists in the same directory as this file
    dotenv_path = Path(__file__).parent.parent / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
except ImportError:
    # dotenv not available, continue without it
    pass


class TestConfig:
    """Configuration management for integration tests using environment variables"""
    
    def __init__(self, environment: str = None):
        """
        Initialize test configuration
        
        Args:
            environment: Environment name - kept for backward compatibility but now used as fallback only
        """
        self.environment = environment or os.getenv('TEST_ENVIRONMENT', 'dynamic')
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables with fallback to config.json"""
        
        # Try environment variables first
        env_config = self._load_from_environment()
        if env_config:
            return env_config
            
        # Fallback to config.json for backward compatibility
        return self._load_from_json_file()
    
    def _load_from_environment(self) -> Optional[Dict[str, Any]]:
        """
        Load configuration from environment variables
        
        Returns:
            Configuration dict if all required env vars are present, None otherwise
        """
        # Required environment variables
        required_env_vars = {
            'api_base_url': 'AWS_OPS_WHEEL_API_BASE_URL',
            'frontend_url': 'AWS_OPS_WHEEL_FRONTEND_URL',
            'cognito_user_pool_id': 'AWS_OPS_WHEEL_USER_POOL_ID',
            'cognito_client_id': 'AWS_OPS_WHEEL_CLIENT_ID'
        }
        
        # Check if all required variables are present
        missing_vars = []
        for config_key, env_var in required_env_vars.items():
            if not os.getenv(env_var):
                missing_vars.append(env_var)
        
        # If any required variables are missing, return None to fall back to JSON
        if missing_vars:
            return None
        
        # Build configuration from environment variables
        config = {}
        
        # Required variables
        for config_key, env_var in required_env_vars.items():
            config[config_key] = os.getenv(env_var)
        
        # Optional variables with defaults
        config['aws_region'] = os.getenv('AWS_OPS_WHEEL_AWS_REGION', 'us-west-2')
        config['cleanup_enabled'] = os.getenv('AWS_OPS_WHEEL_CLEANUP_ENABLED', 'true').lower() == 'true'
        config['timeout_seconds'] = int(os.getenv('AWS_OPS_WHEEL_TIMEOUT_SECONDS', '15'))
        config['max_retries'] = int(os.getenv('AWS_OPS_WHEEL_MAX_RETRIES', '3'))
        config['retry_delay'] = float(os.getenv('AWS_OPS_WHEEL_RETRY_DELAY', '1.0'))
        config['request_timeout'] = int(os.getenv('AWS_OPS_WHEEL_REQUEST_TIMEOUT', '15'))
        config['use_dynamic_admin_creation'] = os.getenv('AWS_OPS_WHEEL_USE_DYNAMIC_ADMIN', 'true').lower() == 'true'
        
        # Additional optional variables
        config['parallel_safe'] = os.getenv('AWS_OPS_WHEEL_PARALLEL_SAFE', 'false').lower() == 'true'
        config['aggressive_testing'] = os.getenv('AWS_OPS_WHEEL_AGGRESSIVE_TESTING', 'false').lower() == 'true'
        config['environment_suffix'] = os.getenv('AWS_OPS_WHEEL_ENVIRONMENT_SUFFIX', self.environment)
        
        # Legacy variables (for backward compatibility - not recommended)
        config['admin_username'] = os.getenv('AWS_OPS_WHEEL_ADMIN_USERNAME', 'dynamic-admin')
        config['admin_email'] = os.getenv('AWS_OPS_WHEEL_ADMIN_EMAIL', 'dynamic-admin@example.com')
        config['admin_password'] = os.getenv('AWS_OPS_WHEEL_ADMIN_PASSWORD', 'DynamicAdmin123!')
        
        return config
    
    def _load_from_json_file(self) -> Dict[str, Any]:
        """
        Fallback: Load configuration from config.json (backward compatibility)
        
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file is not found and no env vars are set
            ValueError: If environment not found in config or invalid JSON
        """
        config_path = Path(__file__).parent / 'config.json'
        
        try:
            with open(config_path, 'r') as f:
                all_configs = json.load(f)
                
            if self.environment not in all_configs:
                raise ValueError(f"Environment '{self.environment}' not found in configuration")
                
            return all_configs[self.environment]
            
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please set environment variables or create config.json file.\n"
                f"Required environment variables:\n"
                f"  - AWS_OPS_WHEEL_API_BASE_URL\n"
                f"  - AWS_OPS_WHEEL_FRONTEND_URL\n" 
                f"  - AWS_OPS_WHEEL_USER_POOL_ID\n"
                f"  - AWS_OPS_WHEEL_CLIENT_ID\n"
                f"See .env.template for complete list."
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    @property
    def api_base_url(self) -> str:
        """Get API base URL"""
        return self.config['api_base_url']
    
    @property
    def frontend_url(self) -> str:
        """Get frontend URL"""
        return self.config['frontend_url']
    
    @property
    def cognito_user_pool_id(self) -> Optional[str]:
        """Get Cognito User Pool ID"""
        return self.config.get('cognito_user_pool_id')
    
    @property
    def cognito_client_id(self) -> Optional[str]:
        """Get Cognito Client ID"""
        return self.config.get('cognito_client_id')
    
    @property
    def aws_region(self) -> str:
        """Get AWS region"""
        return self.config.get('aws_region', 'us-west-2')
    
    @property
    def cleanup_enabled(self) -> bool:
        """Check if cleanup is enabled"""
        return self.config.get('cleanup_enabled', False)
    
    @property
    def timeout_seconds(self) -> int:
        """Get timeout in seconds"""
        return self.config.get('timeout_seconds', 30)
    
    @property
    def max_retries(self) -> int:
        """Get maximum retry attempts"""
        return self.config.get('max_retries', 3)
    
    @property
    def retry_delay(self) -> float:
        """Get retry delay in seconds"""
        return self.config.get('retry_delay', 1.0)
    
    @property
    def request_timeout(self) -> int:
        """Get request timeout in seconds"""
        return self.config.get('request_timeout', 15)
    
    @property
    def use_dynamic_admin_creation(self) -> bool:
        """Check if dynamic admin creation is enabled"""
        return self.config.get('use_dynamic_admin_creation', True)
    
    # Legacy properties for backward compatibility - return empty/default values
    # These are maintained to prevent breaking existing code that may reference them
    
    @property
    def admin_username(self) -> str:
        """Get admin username (legacy - not used with dynamic creation)"""
        return self.config.get('admin_username', 'dynamic-admin')
    
    @property
    def admin_email(self) -> str:
        """Get admin email (legacy - not used with dynamic creation)"""
        return self.config.get('admin_email', 'dynamic-admin@example.com')
    
    @property
    def admin_password(self) -> str:
        """Get admin password (legacy - not used with dynamic creation)"""
        return self.config.get('admin_password', 'DynamicAdmin123!')
    
    @property
    def environment_suffix(self) -> str:
        """Get environment suffix"""
        return self.config.get('environment_suffix', self.environment)
    
    @property
    def parallel_safe(self) -> bool:
        """Check if parallel execution is safe"""
        return self.config.get('parallel_safe', False)
    
    @property
    def aggressive_testing(self) -> bool:
        """Check if aggressive testing is enabled"""
        return self.config.get('aggressive_testing', False)
    
    # Deprecated methods that return empty results - maintained for backward compatibility
    
    @property
    def test_users(self) -> Dict[str, Dict[str, Any]]:
        """Get all test user configurations (deprecated - returns empty dict)"""
        return {}
    
    @property
    def test_wheel_groups(self) -> Dict[str, Dict[str, Any]]:
        """Get all test wheel group configurations (deprecated - returns empty dict)"""
        return {}
    
    @property
    def test_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Get all test scenario configurations (deprecated - returns empty dict)"""
        return {}
    
    def get_test_user(self, user_key: str) -> Dict[str, Any]:
        """
        Get specific test user configuration (deprecated - returns empty dict)
        
        Args:
            user_key: User key
            
        Returns:
            Empty dictionary (static users no longer supported)
        """
        return {}
    
    def get_test_wheel_group(self, group_key: str) -> Dict[str, Any]:
        """
        Get specific test wheel group configuration (deprecated - returns empty dict)
        
        Args:
            group_key: Wheel group key
            
        Returns:
            Empty dictionary (static wheel groups no longer supported)
        """
        return {}
    
    def get_test_scenario(self, scenario_key: str) -> Dict[str, Any]:
        """
        Get specific test scenario configuration (deprecated - returns empty dict)
        
        Args:
            scenario_key: Scenario key
            
        Returns:
            Empty dictionary (static scenarios no longer supported)
        """
        return {}
    
    def get_users_by_role(self, role: str) -> list:
        """
        Get all test users with specified role (deprecated - returns empty list)
        
        Args:
            role: User role
            
        Returns:
            Empty list (static users no longer supported)
        """
        return []
    
    def get_users_by_wheel_group(self, wheel_group_key: str) -> list:
        """
        Get all test users assigned to specified wheel group (deprecated - returns empty list)
        
        Args:
            wheel_group_key: Wheel group key
            
        Returns:
            Empty list (static users no longer supported)
        """
        return []
    
    def get_endpoint_url(self, path: str) -> str:
        """
        Build full endpoint URL
        
        Args:
            path: API path (e.g., '/wheel-groups')
            
        Returns:
            Full URL
        """
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
            
        return f"{self.api_base_url}{path}"
    
    def validate_config(self) -> bool:
        """
        Validate configuration completeness
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If required configuration is missing
        """
        required_fields = [
            'api_base_url',
            'frontend_url',
            'cognito_user_pool_id',
            'cognito_client_id'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not self.config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")
        
        # Validate URL formats
        if not self.api_base_url.startswith('https://'):
            raise ValueError(f"API base URL must use HTTPS: {self.api_base_url}")
            
        if not self.frontend_url.startswith('https://'):
            raise ValueError(f"Frontend URL must use HTTPS: {self.frontend_url}")
        
        # Validate Cognito IDs format
        if not self.cognito_user_pool_id or '_' not in self.cognito_user_pool_id:
            raise ValueError(f"Invalid Cognito User Pool ID format: {self.cognito_user_pool_id}")
            
        return True
    
    def is_using_environment_variables(self) -> bool:
        """Check if configuration is loaded from environment variables"""
        return os.getenv('AWS_OPS_WHEEL_API_BASE_URL') is not None
    
    def get_configuration_source(self) -> str:
        """Get the source of the current configuration"""
        if self.is_using_environment_variables():
            return "Environment Variables"
        else:
            return f"config.json (environment: {self.environment})"
    
    def print_configuration_info(self) -> None:
        """Print configuration information for debugging"""
        print(f"Configuration Source: {self.get_configuration_source()}")
        print(f"Environment: {self.environment}")
        print(f"API Base URL: {self.api_base_url}")
        print(f"Frontend URL: {self.frontend_url}")
        print(f"AWS Region: {self.aws_region}")
        print(f"Cleanup Enabled: {self.cleanup_enabled}")
        print(f"Use Dynamic Admin: {self.use_dynamic_admin_creation}")
        if self.is_using_environment_variables():
            print("\n✅ Using environment variables (recommended)")
        else:
            print("\n⚠️  Using config.json (consider migrating to environment variables)")
    
    def __str__(self) -> str:
        """String representation"""
        source = "env" if self.is_using_environment_variables() else "json"
        return f"TestConfig(environment='{self.environment}', source='{source}', api_url='{self.api_base_url}')"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        source = "env" if self.is_using_environment_variables() else "json"
        return (f"TestConfig(environment='{self.environment}', "
                f"source='{source}', "
                f"api_url='{self.api_base_url}', "
                f"cleanup_enabled={self.cleanup_enabled})")
