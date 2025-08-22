"""
Test Configuration Management for AWS Ops Wheel v2 Integration Tests
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


class TestConfig:
    """Configuration management for integration tests"""
    
    def __init__(self, environment: str = None):
        """
        Initialize test configuration
        
        Args:
            environment: Environment name ('test', 'dev'). Defaults to 'test'
        """
        self.environment = environment or os.getenv('TEST_ENVIRONMENT', 'test')
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environments.json"""
        config_path = Path(__file__).parent / 'environments.json'
        
        try:
            with open(config_path, 'r') as f:
                all_configs = json.load(f)
                
            if self.environment not in all_configs:
                raise ValueError(f"Environment '{self.environment}' not found in configuration")
                
            return all_configs[self.environment]
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
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
    def admin_username(self) -> str:
        """Get admin username"""
        return self.config['admin_username']
    
    @property
    def admin_email(self) -> str:
        """Get admin email"""
        return self.config['admin_email']
    
    @property
    def admin_password(self) -> str:
        """Get admin password"""
        return self.config['admin_password']
    
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
    def aggressive_testing(self) -> bool:
        """Check if aggressive testing is enabled"""
        return self.config.get('aggressive_testing', False)
    
    @property
    def timeout_seconds(self) -> int:
        """Get timeout in seconds"""
        return self.config.get('timeout_seconds', 30)
    
    @property
    def parallel_safe(self) -> bool:
        """Check if parallel execution is safe"""
        return self.config.get('parallel_safe', False)
    
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
    def environment_suffix(self) -> str:
        """Get environment suffix"""
        return self.config.get('environment_suffix', self.environment)
    
    def get_endpoint_url(self, path: str) -> str:
        """
        Build full endpoint URL
        
        Args:
            path: API path (e.g., '/app/api/v2/wheel-groups')
            
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
            'admin_username',
            'admin_password'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not self.config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")
        
        # Validate URL format
        if not self.api_base_url.startswith('https://'):
            raise ValueError(f"API base URL must use HTTPS: {self.api_base_url}")
        
        return True
    
    def __str__(self) -> str:
        """String representation"""
        return f"TestConfig(environment='{self.environment}', api_url='{self.api_base_url}')"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (f"TestConfig(environment='{self.environment}', "
                f"api_url='{self.api_base_url}', "
                f"cleanup_enabled={self.cleanup_enabled})")
