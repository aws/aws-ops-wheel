"""
Pytest Configuration and Fixtures for AWS Ops Wheel v2 Integration Tests
"""
import os
import pytest
import time
from typing import Generator, Dict, Any, List

from config.test_config import TestConfig
from utils.api_client import APIClient
from utils.auth_manager import AuthManager, AuthenticationError
from utils.test_data_factory import TestDataFactory
from utils.cleanup import CleanupManager
from utils.assertions import APIAssertions


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--environment",
        action="store",
        default="test",
        help="Test environment (test, dev)"
    )
    parser.addoption(
        "--cleanup",
        action="store_true",
        default=True,
        help="Enable cleanup of test data"
    )
    parser.addoption(
        "--integration-debug",
        action="store_true",
        default=False,
        help="Enable integration test debug logging"
    )
    parser.addoption(
        "--admin-password",
        action="store",
        default=None,
        help="Override admin password for testing"
    )


def pytest_configure(config):
    """Configure pytest environment"""
    # Set environment variable for test configuration
    environment = config.getoption("--environment")
    os.environ['TEST_ENVIRONMENT'] = environment
    
    # Register custom markers
    config.addinivalue_line(
        "markers", "smoke: quick smoke tests for critical functionality"
    )
    config.addinivalue_line(
        "markers", "auth: authentication and authorization tests"
    )
    config.addinivalue_line(
        "markers", "crud: create, read, update, delete operation tests"
    )
    config.addinivalue_line(
        "markers", "admin: admin-only functionality tests"
    )
    config.addinivalue_line(
        "markers", "slow: tests that take longer to execute"
    )
    config.addinivalue_line(
        "markers", "critical: critical path tests that must pass"
    )


@pytest.fixture(scope="session")
def test_config(request) -> TestConfig:
    """
    Test configuration fixture
    
    Returns:
        TestConfig instance
    """
    environment = request.config.getoption("--environment")
    config = TestConfig(environment)
    
    # Override admin password if provided
    admin_password = request.config.getoption("--admin-password")
    if admin_password:
        config.config['admin_password'] = admin_password
    
    # Validate configuration
    config.validate_config()
    
    return config


@pytest.fixture(scope="session")
def debug_enabled(request) -> bool:
    """Debug flag fixture"""
    return request.config.getoption("--integration-debug")


@pytest.fixture(scope="session")
def cleanup_enabled(request) -> bool:
    """Cleanup flag fixture"""
    return request.config.getoption("--cleanup")


@pytest.fixture(scope="session")
def test_run_id() -> str:
    """Unique test run identifier"""
    return str(int(time.time()))


@pytest.fixture(scope="session")
def api_client(test_config: TestConfig, debug_enabled: bool) -> Generator[APIClient, None, None]:
    """
    API client fixture
    
    Args:
        test_config: Test configuration
        debug_enabled: Debug flag
        
    Yields:
        APIClient instance
    """
    client = APIClient(
        base_url=test_config.api_base_url,
        timeout=test_config.request_timeout,
        max_retries=test_config.max_retries,
        retry_delay=test_config.retry_delay,
        debug=debug_enabled
    )
    
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def auth_manager(api_client: APIClient, test_config: TestConfig, debug_enabled: bool) -> AuthManager:
    """
    Authentication manager fixture with Cognito support
    
    Args:
        api_client: API client instance
        test_config: Test configuration
        debug_enabled: Debug flag
        
    Returns:
        AuthManager instance with CognitoAuthenticator
    """
    from utils.cognito_authenticator import CognitoAuthenticator
    
    # Create Cognito authenticator
    cognito_auth = CognitoAuthenticator(
        user_pool_id=test_config.cognito_user_pool_id,
        client_id=test_config.cognito_client_id,
        region=test_config.aws_region,
        debug=debug_enabled
    )
    
    # Create auth manager and inject Cognito authenticator
    auth_manager = AuthManager(api_client, debug=debug_enabled)
    auth_manager.cognito_authenticator = cognito_auth
    
    return auth_manager


@pytest.fixture(scope="session")
def admin_auth(auth_manager: AuthManager, test_config: TestConfig) -> Dict[str, Any]:
    """
    Admin authentication fixture - logs in as admin once per session
    
    Args:
        auth_manager: Authentication manager
        test_config: Test configuration
        
    Returns:
        Admin login response
        
    Raises:
        AuthenticationError: If admin login fails
    """
    try:
        result = auth_manager.admin_login(
            test_config.admin_username,
            test_config.admin_password
        )
        
        if not auth_manager.is_authenticated():
            raise AuthenticationError("Admin authentication failed - no valid token")
        
        if not auth_manager.is_admin():
            raise AuthenticationError("Admin authentication failed - no admin privileges")
        
        return result
        
    except Exception as e:
        pytest.fail(f"Admin authentication failed: {e}")


@pytest.fixture(scope="session")
def test_data_factory(test_run_id: str) -> TestDataFactory:
    """
    Test data factory fixture
    
    Args:
        test_run_id: Unique test run identifier
        
    Returns:
        TestDataFactory instance
    """
    return TestDataFactory(test_run_id)


@pytest.fixture(scope="session")
def cleanup_manager(api_client: APIClient, auth_manager: AuthManager, 
                   cleanup_enabled: bool, debug_enabled: bool) -> Generator[CleanupManager, None, None]:
    """
    Cleanup manager fixture - handles resource cleanup
    
    Args:
        api_client: API client instance
        auth_manager: Authentication manager
        cleanup_enabled: Whether cleanup is enabled
        debug_enabled: Debug flag
        
    Yields:
        CleanupManager instance
    """
    manager = CleanupManager(
        api_client=api_client,
        auth_manager=auth_manager,
        cleanup_enabled=cleanup_enabled,
        debug=debug_enabled
    )
    
    try:
        yield manager
    finally:
        # Perform final cleanup at end of session
        if cleanup_enabled:
            try:
                successful, failed = manager.cleanup_all_registered_resources()
                if debug_enabled:
                    print(f"\n[CLEANUP] Final cleanup: {successful} successful, {failed} failed")
                
                if failed > 0:
                    # Try force cleanup if regular cleanup failed
                    force_successful, force_failed = manager.force_cleanup_by_admin()
                    if debug_enabled:
                        print(f"[CLEANUP] Force cleanup: {force_successful} successful, {force_failed} failed")
                
            except Exception as e:
                if debug_enabled:
                    print(f"[CLEANUP] Final cleanup failed: {e}")


@pytest.fixture
def assertions() -> APIAssertions:
    """API assertions fixture"""
    return APIAssertions()


@pytest.fixture
def authenticated_client(api_client: APIClient, auth_manager: AuthManager, 
                        admin_auth: Dict[str, Any]) -> APIClient:
    """
    Pre-authenticated API client fixture with token validation and state recovery
    
    Args:
        api_client: API client instance  
        auth_manager: Authentication manager
        admin_auth: Admin authentication result
        
    Returns:
        Authenticated API client
    """
    # Always ensure we have valid authentication before each test
    # This fixes authentication state loss between test classes
    if not auth_manager.is_authenticated():
        print("[AUTH-FIX] Authentication state lost - re-authenticating...")
        auth_manager.ensure_authenticated()
        
        # Verify we now have admin privileges
        if not auth_manager.is_admin():
            print("[AUTH-FIX] Admin privileges missing after re-authentication")
            raise RuntimeError("Failed to restore admin authentication state")
        
        print(f"[AUTH-FIX] Authentication restored - admin: {auth_manager.is_admin()}")
    
    # Double-check token is set in API client
    if not api_client._auth_token:
        print("[AUTH-FIX] API client missing auth token - setting from auth manager")
        token = auth_manager.get_current_token()
        if token:
            api_client.set_auth_token(token, auth_manager._token_expiry)
        else:
            print("[AUTH-FIX] No token available from auth manager")
            raise RuntimeError("No authentication token available")
    
    return api_client


@pytest.fixture
def logout_test_auth_manager(test_config: TestConfig, debug_enabled: bool) -> AuthManager:
    """
    Isolated authentication manager for logout testing
    
    This fixture creates a separate auth manager and API client to prevent
    logout tests from affecting the shared session authentication.
    
    Args:
        test_config: Test configuration
        debug_enabled: Debug flag
        
    Returns:
        Isolated AuthManager instance
    """
    from utils.cognito_authenticator import CognitoAuthenticator
    
    # Create separate API client for isolation
    isolated_client = APIClient(
        base_url=test_config.api_base_url,
        timeout=test_config.request_timeout,
        max_retries=test_config.max_retries,
        retry_delay=test_config.retry_delay,
        debug=debug_enabled
    )
    
    # Create Cognito authenticator
    cognito_auth = CognitoAuthenticator(
        user_pool_id=test_config.cognito_user_pool_id,
        client_id=test_config.cognito_client_id,
        region=test_config.aws_region,
        debug=debug_enabled
    )
    
    # Create isolated auth manager
    isolated_auth_manager = AuthManager(isolated_client, debug=debug_enabled)
    isolated_auth_manager.cognito_authenticator = cognito_auth
    
    # Perform authentication for this isolated instance
    try:
        isolated_auth_manager.admin_login(
            test_config.admin_username,
            test_config.admin_password
        )
    except Exception as e:
        pytest.fail(f"Isolated auth manager login failed: {e}")
    
    return isolated_auth_manager


@pytest.fixture  
def logout_test_client(logout_test_auth_manager: AuthManager) -> APIClient:
    """
    Isolated API client for logout testing
    
    Args:
        logout_test_auth_manager: Isolated authentication manager
        
    Returns:
        Isolated authenticated API client
    """
    return logout_test_auth_manager.api_client


@pytest.fixture
def test_wheel_group(authenticated_client: APIClient, test_data_factory: TestDataFactory,
                    cleanup_manager: CleanupManager, assertions: APIAssertions) -> Dict[str, Any]:
    """
    Test wheel group fixture - creates a wheel group for testing
    
    Uses the public endpoint since deployment admins should use that endpoint.
    
    Args:
        authenticated_client: Authenticated API client
        test_data_factory: Test data factory
        cleanup_manager: Cleanup manager
        assertions: API assertions
        
    Returns:
        Created wheel group data
    """
    # Create wheel group using public endpoint (for deployment admin users)
    wheel_group_data = test_data_factory.create_public_wheel_group_data()
    
    response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=wheel_group_data)
    assertions.assert_success_response(response, "Failed to create test wheel group")
    assertions.assert_public_wheel_group_structure(response)
    
    # Extract wheel group from nested response
    wheel_group = response.json_data['wheel_group']
    wheel_group_id = wheel_group.get('wheel_group_id')
    
    # Register for cleanup
    if wheel_group_id:
        cleanup_manager.register_wheel_group(wheel_group_id)
    
    return wheel_group


@pytest.fixture
def test_wheel(authenticated_client: APIClient, test_wheel_group: Dict[str, Any],
              test_data_factory: TestDataFactory, cleanup_manager: CleanupManager,
              assertions: APIAssertions) -> Dict[str, Any]:
    """
    Test wheel fixture - creates a wheel for testing
    
    Args:
        authenticated_client: Authenticated API client
        test_wheel_group: Test wheel group
        test_data_factory: Test data factory
        cleanup_manager: Cleanup manager
        assertions: API assertions
        
    Returns:
        Created wheel data
    """
    wheel_group_id = test_wheel_group['wheel_group_id']
    wheel_data = test_data_factory.create_wheel_data()
    
    response = authenticated_client.post(f'/app/api/v2/wheel-groups/{wheel_group_id}/wheels', 
                                       data=wheel_data)
    assertions.assert_success_response(response, "Failed to create test wheel")
    assertions.assert_wheel_structure(response)
    
    wheel = response.json_data
    wheel_id = wheel.get('wheel_id')
    
    # Register for cleanup
    if wheel_id:
        cleanup_manager.register_wheel(wheel_id)
    
    return wheel


@pytest.fixture
def test_participants(authenticated_client: APIClient, test_wheel: Dict[str, Any],
                     test_data_factory: TestDataFactory, cleanup_manager: CleanupManager,
                     assertions: APIAssertions) -> List[Dict[str, Any]]:
    """
    Test participants fixture - creates participants for testing
    
    Args:
        authenticated_client: Authenticated API client
        test_wheel: Test wheel
        test_data_factory: Test data factory
        cleanup_manager: Cleanup manager
        assertions: API assertions
        
    Returns:
        List of created participant data
    """
    wheel_id = test_wheel['wheel_id']
    participants_data = test_data_factory.create_multiple_participants(3)
    
    created_participants = []
    
    for participant_data in participants_data:
        response = authenticated_client.post(f'/app/api/v2/wheels/{wheel_id}/participants',
                                           data=participant_data)
        assertions.assert_success_response(response, "Failed to create test participant")
        assertions.assert_participant_structure(response)
        
        participant = response.json_data
        participant_id = participant.get('participant_id')
        
        # Register for cleanup
        if participant_id:
            cleanup_manager.register_participant(participant_id)
        
        created_participants.append(participant)
    
    return created_participants


# Test environment health check fixtures

@pytest.fixture(scope="session", autouse=True)
def verify_test_environment(test_config: TestConfig, api_client: APIClient, debug_enabled: bool):
    """
    Verify test environment is accessible before running tests
    
    Args:
        test_config: Test configuration
        api_client: API client
        debug_enabled: Debug flag
    """
    if debug_enabled:
        print(f"\n[SETUP] Verifying test environment: {test_config.environment}")
        print(f"[SETUP] API URL: {test_config.api_base_url}")
    
    # Check if API is accessible
    try:
        # Try a simple health check or options call
        response = api_client.get('/health', timeout=10)
        if not response.is_success:
            # If /health doesn't exist, try root
            response = api_client.get('/', timeout=10)
        
        if debug_enabled:
            print(f"[SETUP] Environment check: {response.status_code}")
            
    except Exception as e:
        pytest.fail(f"Test environment not accessible: {test_config.api_base_url} - {e}")


@pytest.fixture(autouse=True)
def test_isolation():
    """
    Ensure test isolation by adding small delay between tests
    """
    # Small delay to prevent rate limiting and ensure test isolation
    time.sleep(0.1)
    
    yield
    
    # Additional cleanup/verification could go here


# Pytest hooks

def pytest_runtest_setup(item):
    """Setup for each test"""
    # Add any per-test setup here
    pass


def pytest_runtest_teardown(item):
    """Teardown for each test"""
    # Add any per-test teardown here
    pass


def pytest_sessionfinish(session, exitstatus):
    """Session cleanup"""
    # Final cleanup logging
    if hasattr(session.config, 'getoption') and session.config.getoption("--integration-debug"):
        print(f"\n[SESSION] Tests completed with exit status: {exitstatus}")


# Custom pytest markers for test categorization

def pytest_collection_modifyitems(config, items):
    """Modify test items during collection"""
    # Auto-mark tests based on their names
    for item in items:
        # Auto-mark admin tests
        if "admin" in item.name.lower():
            item.add_marker(pytest.mark.admin)
        
        # Auto-mark CRUD tests
        if any(word in item.name.lower() for word in ["create", "read", "update", "delete", "get", "post", "put", "patch"]):
            item.add_marker(pytest.mark.crud)
        
        # Auto-mark auth tests
        if any(word in item.name.lower() for word in ["auth", "login", "token", "permission"]):
            item.add_marker(pytest.mark.auth)
        
        # Auto-mark critical tests
        if any(word in item.name.lower() for word in ["critical", "smoke", "health"]):
            item.add_marker(pytest.mark.critical)
