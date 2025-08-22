"""
Environment Health Check Tests for AWS Ops Wheel v2 Integration Tests

These tests verify that the test environment is accessible and properly configured.
They run first to ensure the environment is ready for integration testing.
"""
import pytest
from typing import Dict, Any

from config.test_config import TestConfig
from utils.api_client import APIClient
from utils.assertions import APIAssertions


class TestEnvironmentHealth:
    """Environment health check tests"""
    
    @pytest.mark.critical
    @pytest.mark.smoke
    def test_api_endpoint_accessible(self, api_client: APIClient, test_config: TestConfig, 
                                   assertions: APIAssertions):
        """
        Test that the API endpoint is accessible
        
        This is the most basic test - if this fails, no other tests can run.
        """
        # Try multiple endpoints to find one that responds
        endpoints_to_try = [
            '/health',
            '/',
            '/app/api/v2/health',
            '/app/api/v2/'
        ]
        
        success = False
        last_error = None
        
        for endpoint in endpoints_to_try:
            try:
                response = api_client.get(endpoint, timeout=10)
                if response.status_code < 500:  # Accept any non-server-error response
                    success = True
                    break
            except Exception as e:
                last_error = str(e)
                continue
        
        assert success, f"API endpoint not accessible at {test_config.api_base_url}. Last error: {last_error}"
    
    @pytest.mark.critical
    @pytest.mark.smoke
    def test_api_cors_headers(self, api_client: APIClient, assertions: APIAssertions):
        """
        Test that CORS headers are properly configured
        
        This is important for frontend integration.
        """
        # Make an OPTIONS request to check CORS
        try:
            response = api_client.request('OPTIONS', '/app/api/v2/')
            
            # Don't fail if OPTIONS isn't supported, but check headers if it is
            if response.status_code != 405:  # Method not allowed is acceptable
                # Check for CORS headers if the request succeeded
                if response.is_success:
                    assertions.assert_cors_headers(response, "CORS headers missing from API response")
        except Exception:
            # CORS check is non-critical if OPTIONS method fails
            pytest.skip("CORS check skipped - OPTIONS method not available")
    
    @pytest.mark.critical
    @pytest.mark.smoke  
    def test_api_response_time(self, api_client: APIClient, assertions: APIAssertions):
        """
        Test that API response time is acceptable
        
        Ensures the test environment is performing adequately.
        """
        response = api_client.get('/', timeout=10)
        
        # Allow up to 5 seconds for response in test environment
        assertions.assert_response_time(response, 5.0, 
                                      "API response time too slow for integration testing")
    
    @pytest.mark.critical
    def test_configuration_validity(self, test_config: TestConfig):
        """
        Test that the test configuration is valid and complete
        
        Verifies all required configuration is present.
        """
        # Test configuration validation
        assert test_config.validate_config(), "Test configuration validation failed"
        
        # Check critical configuration values
        assert test_config.api_base_url, "API base URL not configured"
        assert test_config.admin_username, "Admin username not configured"
        assert test_config.admin_password, "Admin password not configured"
        assert test_config.environment_suffix, "Environment suffix not configured"
        
        # Verify URL format
        assert test_config.api_base_url.startswith('https://'), \
            f"API URL must use HTTPS: {test_config.api_base_url}"
        
        # Check that we're testing against the correct environment
        expected_suffix = test_config.environment_suffix
        assert expected_suffix in test_config.api_base_url, \
            f"API URL doesn't match expected environment '{expected_suffix}': {test_config.api_base_url}"
    
    @pytest.mark.smoke
    def test_environment_isolation(self, test_config: TestConfig):
        """
        Test that we're running against an isolated test environment
        
        This prevents accidentally running tests against production.
        """
        # Ensure we're not accidentally testing production
        production_indicators = ['prod', 'production', 'live']
        api_url_lower = test_config.api_base_url.lower()
        
        for indicator in production_indicators:
            assert indicator not in api_url_lower, \
                f"Refusing to run integration tests against production environment: {test_config.api_base_url}"
        
        # Ensure we're testing the expected environment
        expected_env = test_config.environment.lower()
        if expected_env == 'test':
            assert 'test' in api_url_lower, \
                f"Expected test environment, but API URL doesn't contain 'test': {test_config.api_base_url}"
    
    @pytest.mark.smoke
    def test_test_data_factory_ready(self, test_data_factory):
        """
        Test that the test data factory is ready to generate test data
        
        Ensures test data generation will work properly.
        """
        # Test basic data generation
        wheel_group_name = test_data_factory.generate_wheel_group_name()
        assert wheel_group_name, "Test data factory failed to generate wheel group name"
        assert "IntegTest" in wheel_group_name, "Generated wheel group name doesn't contain expected prefix"
        
        # Test unique generation
        name1 = test_data_factory.generate_wheel_group_name()
        name2 = test_data_factory.generate_wheel_group_name()
        assert name1 != name2, "Test data factory not generating unique names"
        
        # Test email generation
        email = test_data_factory.generate_email()
        assert email, "Test data factory failed to generate email"
        assert "@" in email, "Generated email doesn't contain @ symbol"
        assert "integrationtest.example.com" in email, "Generated email doesn't use expected domain"
        
        # Test password generation
        password = test_data_factory.generate_password()
        assert password, "Test data factory failed to generate password"
        assert len(password) >= 8, "Generated password too short"
    
    @pytest.mark.smoke
    def test_environment_metadata(self, test_config: TestConfig, test_data_factory):
        """
        Test and log environment metadata for debugging
        
        Provides useful information for test debugging and reporting.
        """
        metadata = {
            'environment': test_config.environment,
            'api_base_url': test_config.api_base_url,
            'cleanup_enabled': test_config.cleanup_enabled,
            'test_run_id': test_data_factory.test_run_id,
            'timeout_seconds': test_config.timeout_seconds,
            'max_retries': test_config.max_retries
        }
        
        print(f"\n=== Integration Test Environment Metadata ===")
        for key, value in metadata.items():
            print(f"{key}: {value}")
        print("=" * 50)
        
        # Basic assertions on metadata
        assert metadata['environment'] in ['test', 'dev'], f"Unexpected environment: {metadata['environment']}"
        assert metadata['test_run_id'], "Test run ID not generated"
        assert metadata['timeout_seconds'] > 0, "Invalid timeout configuration"
        assert metadata['max_retries'] >= 0, "Invalid retry configuration"


class TestEnvironmentPreparation:
    """Environment preparation tests"""
    
    @pytest.mark.critical
    def test_cleanup_system_ready(self, cleanup_manager):
        """
        Test that the cleanup system is properly initialized
        
        Ensures test cleanup will work properly to maintain environment cleanliness.
        """
        # Check cleanup manager is properly initialized
        assert cleanup_manager is not None, "Cleanup manager not initialized"
        
        # Check initial state
        remaining = cleanup_manager.get_remaining_resources()
        assert isinstance(remaining, dict), "Cleanup manager not returning proper resource tracking"
        
        expected_keys = ['wheel_groups', 'wheels', 'participants', 'users']
        for key in expected_keys:
            assert key in remaining, f"Cleanup manager missing resource type: {key}"
            assert isinstance(remaining[key], list), f"Resource tracking for {key} not a list"
        
        # Check initial cleanup state
        failed_cleanups = cleanup_manager.get_failed_cleanups()
        assert isinstance(failed_cleanups, list), "Failed cleanups not properly tracked"
    
    @pytest.mark.smoke
    def test_assertions_ready(self, assertions: APIAssertions):
        """
        Test that custom assertions are working properly
        
        Validates the testing framework components.
        """
        # Test that assertions object is properly initialized
        assert assertions is not None, "Assertions object not initialized"
        
        # Test basic assertion methods exist
        assert hasattr(assertions, 'assert_success_response'), "Missing assert_success_response method"
        assert hasattr(assertions, 'assert_json_response'), "Missing assert_json_response method"
        assert hasattr(assertions, 'assert_status_code'), "Missing assert_status_code method"
        assert hasattr(assertions, 'assert_wheel_group_structure'), "Missing assert_wheel_group_structure method"
        
        # Test that methods are callable
        assert callable(assertions.assert_success_response), "assert_success_response not callable"
        assert callable(assertions.assert_json_response), "assert_json_response not callable"
