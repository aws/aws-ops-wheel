"""
Pytest Configuration and Fixtures for AWS Ops Wheel v2 Integration Tests
"""
import os
import pytest
import time
import subprocess
import sys
from typing import Generator, Dict, Any, List

from config.test_config import TestConfig
from utils.api_client import APIClient
from utils.auth_manager import AuthManager, AuthenticationError
from utils.test_data_factory import TestDataFactory
from utils.cleanup import CleanupManager
from utils.assertions import APIAssertions


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--environment",
        action="store",
        default="test",
        help="Test environment (test, dev)"
    )
    parser.addoption(
        "--no-cleanup",
        action="store_true",
        default=False,
        help="Disable cleanup of test data"
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
    parser.addoption(
        "--comprehensive-cleanup",
        action="store_true",
        default=True,
        help="Use comprehensive cleanup script after tests (default: True)"
    )
    parser.addoption(
        "--cleanup-dry-run",
        action="store_true",
        default=False,
        help="Run cleanup in dry-run mode (show what would be deleted)"
    )


def pytest_configure(config):
    """Configure pytest environment"""
    # Set environment variable for test configuration
    environment = config.getoption("--environment")
    os.environ['TEST_ENVIRONMENT'] = environment
    
    # Register custom markers
    markers = [
        "smoke: quick smoke tests for critical functionality",
        "auth: authentication and authorization tests",
        "crud: create, read, update, delete operation tests",
        "admin: admin-only functionality tests",
        "slow: tests that take longer to execute",
        "critical: critical path tests that must pass",
        "role_based: role-based access tests",
        "permissions: permission enforcement tests",
        "spinning: wheel spinning functionality tests",
        "workflow: workflow integration tests",
        "cross_role: cross-role interaction tests"
    ]
    
    for marker in markers:
        config.addinivalue_line("markers", marker)


# ============================================================================
# CORE CONFIGURATION FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_config(request) -> TestConfig:
    """Test configuration fixture"""
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
    return not request.config.getoption("--no-cleanup")


@pytest.fixture(scope="session")
def comprehensive_cleanup_enabled(request) -> bool:
    """Comprehensive cleanup flag fixture"""
    return request.config.getoption("--comprehensive-cleanup")


@pytest.fixture(scope="session")
def cleanup_dry_run(request) -> bool:
    """Cleanup dry run flag fixture"""
    return request.config.getoption("--cleanup-dry-run")


@pytest.fixture(scope="session")
def test_run_id() -> str:
    """Unique test run identifier"""
    return str(int(time.time()))


# ============================================================================
# COMPREHENSIVE CLEANUP FUNCTIONS
# ============================================================================

def _run_comprehensive_cleanup(debug_enabled: bool, dry_run: bool) -> bool:
    """
    Run the comprehensive cleanup script
    
    Args:
        debug_enabled: Whether to enable debug logging
        dry_run: Whether to run in dry-run mode
        
    Returns:
        True if cleanup successful, False otherwise
    """
    try:
        script_path = os.path.join(os.path.dirname(__file__), "clear_test_data.py")
        
        # Build command arguments
        cmd = [sys.executable, script_path]
        
        if dry_run:
            cmd.append("--dry-run")
        
        # Always auto-confirm when running from pytest (no stdin available)
        cmd.append("--auto-confirm")
        
        if debug_enabled:
            print(f"\n[COMPREHENSIVE-CLEANUP] Running comprehensive cleanup script...")
            print(f"[COMPREHENSIVE-CLEANUP] Command: {' '.join(cmd)}")
        
        # Run the cleanup script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=os.path.dirname(__file__)
        )
        
        # Log output if debug is enabled
        if debug_enabled:
            if result.stdout:
                print(f"[COMPREHENSIVE-CLEANUP] STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"[COMPREHENSIVE-CLEANUP] STDERR:\n{result.stderr}")
        
        success = result.returncode == 0
        
        if debug_enabled:
            if success:
                print(f"[COMPREHENSIVE-CLEANUP] ✅ Comprehensive cleanup completed successfully")
            else:
                print(f"[COMPREHENSIVE-CLEANUP] ❌ Comprehensive cleanup failed with exit code: {result.returncode}")
        
        return success
        
    except subprocess.TimeoutExpired:
        if debug_enabled:
            print(f"[COMPREHENSIVE-CLEANUP] ❌ Comprehensive cleanup timed out after 5 minutes")
        return False
    except Exception as e:
        if debug_enabled:
            print(f"[COMPREHENSIVE-CLEANUP] ❌ Comprehensive cleanup failed: {e}")
        return False


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _create_cognito_authenticator(test_config: TestConfig, debug_enabled: bool):
    """Helper function to create CognitoAuthenticator with consistent parameters"""
    from utils.cognito_authenticator import CognitoAuthenticator
    
    return CognitoAuthenticator(
        user_pool_id=test_config.cognito_user_pool_id,
        client_id=test_config.cognito_client_id,
        region=test_config.aws_region,
        debug=debug_enabled
    )


def _create_authenticated_client(base_client: APIClient, auth_data: Dict[str, Any]) -> APIClient:
    """Helper to create authenticated API client"""
    client = APIClient(
        base_url=base_client.base_url,
        timeout=base_client.timeout,
        max_retries=base_client.max_retries,
        retry_delay=base_client.retry_delay,
        debug=base_client.debug
    )
    
    # Use id_token if available, otherwise fall back to access_token
    token = auth_data.get('id_token') or auth_data.get('access_token')
    if token:
        client.set_auth_token(token)
    
    return client


def _create_dynamic_admin_user(api_client: APIClient, test_data_factory: TestDataFactory, 
                              test_config: TestConfig, group_name: str, 
                              debug_enabled: bool, cleanup_manager=None) -> Dict[str, Any]:
    """Helper to create dynamic admin user via wheel group creation"""
    if debug_enabled:
        print(f"\n[DYNAMIC-ADMIN] Creating dynamic admin user with group: {group_name}")
    
    try:
        # Step 1: Create wheel group with admin user (no auth required)
        wheel_group_data = test_data_factory.create_public_wheel_group_data(name=group_name)
        
        response = api_client.post('/wheel-group/create-public', data=wheel_group_data)
        if not response.is_success:
            raise AuthenticationError(f"Failed to create admin wheel group: {response.status_code} - {response.text}")
        
        admin_user = response.json_data['admin_user']
        wheel_group = response.json_data['wheel_group']
        admin_username = wheel_group_data['admin_user']['username']
        admin_password = wheel_group_data['admin_user']['password']
        admin_email = wheel_group_data['admin_user']['email']
        
        if debug_enabled:
            print(f"[DYNAMIC-ADMIN] Created admin user: {admin_user['user_id']} in wheel group: {wheel_group['wheel_group_id']}")
        
        # Register resources for cleanup if cleanup_manager is provided
        if cleanup_manager:
            cleanup_manager.register_wheel_group(wheel_group['wheel_group_id'])
            cleanup_manager.register_user(admin_user['user_id'])
            cleanup_manager.register_cognito_user(admin_username, admin_email)
            
            if debug_enabled:
                print(f"[DYNAMIC-ADMIN] Registered resources for cleanup")
        
        # Step 2: Wait for DynamoDB consistency (critical for authorizer)
        time.sleep(2.0)
        
        # Step 3: Authenticate as the created admin user
        cognito_auth = _create_cognito_authenticator(test_config, debug_enabled)
        auth_result = cognito_auth.authenticate_user(admin_username, admin_password)
        
        if debug_enabled:
            print(f"[DYNAMIC-ADMIN] Authentication successful for: {admin_username}")
        
        # Return standardized auth data structure
        return {
            'access_token': auth_result['id_token'],  # Use ID token for API Gateway
            'id_token': auth_result.get('id_token'),
            'refresh_token': auth_result.get('refresh_token'),
            'user': auth_result.get('user', {}),
            'username': admin_username,
            'password': admin_password,
            'email': admin_email,
            'wheel_group_id': wheel_group['wheel_group_id'],
            'admin_user_id': admin_user['user_id'],
            'expires_in': auth_result.get('expires_in', 3600),
            'is_wheel_group_admin': True,
            'cleanup_wheel_group_id': wheel_group['wheel_group_id']  # For cleanup
        }
        
    except Exception as e:
        if debug_enabled:
            print(f"[DYNAMIC-ADMIN] Setup failed: {e}")
        raise AuthenticationError(f"Dynamic admin authentication setup failed: {e}")


def _authenticate_user_with_cognito(test_config: TestConfig, username: str, password: str, 
                                   role: str, debug_enabled: bool) -> Dict[str, Any]:
    """Helper function for user authentication with standardized return format"""
    if debug_enabled:
        print(f"\n[AUTH] Authenticating {role}: {username}")
    
    try:
        cognito_auth = _create_cognito_authenticator(test_config, debug_enabled)
        auth_result = cognito_auth.authenticate_user(username, password)
        
        if debug_enabled:
            print(f"[AUTH] Authentication successful for {role}: {username}")
        
        return {
            'access_token': auth_result['access_token'],
            'id_token': auth_result.get('id_token'),
            'refresh_token': auth_result.get('refresh_token'),
            'username': username,
            'role': role,
            'expires_in': auth_result.get('expires_in', 3600)
        }
        
    except Exception as e:
        if debug_enabled:
            print(f"[AUTH] Authentication failed for {role} {username}: {e}")
        pytest.skip(f"{role} authentication failed: {e}")


# ============================================================================
# CORE API AND AUTH FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def api_client(test_config: TestConfig, debug_enabled: bool) -> Generator[APIClient, None, None]:
    """API client fixture"""
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
def cognito_authenticator(test_config: TestConfig, debug_enabled: bool):
    """Shared Cognito authenticator instance"""
    return _create_cognito_authenticator(test_config, debug_enabled)


@pytest.fixture(scope="session")
def auth_manager(api_client: APIClient, cognito_authenticator, debug_enabled: bool) -> AuthManager:
    """Authentication manager fixture with Cognito support"""
    auth_manager = AuthManager(api_client, debug=debug_enabled)
    auth_manager.cognito_authenticator = cognito_authenticator
    return auth_manager


# ============================================================================
# DYNAMIC ADMIN AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def admin_auth(api_client: APIClient, test_config: TestConfig, 
               test_data_factory: TestDataFactory, debug_enabled: bool, 
               cleanup_manager: CleanupManager) -> Dict[str, Any]:
    """
    Admin authentication fixture - creates dynamic admin via wheel group creation
    
    Since deployment admin users require special Cognito setup, this fixture:
    1. Creates a wheel group using the public endpoint (no auth required)
    2. Uses the created admin user credentials for authentication
    3. This gives us a working admin user with proper JWT claims
    """
    return _create_dynamic_admin_user(
        api_client=api_client,
        test_data_factory=test_data_factory,
        test_config=test_config,
        group_name="IntegTestAdminGroup",
        debug_enabled=debug_enabled,
        cleanup_manager=cleanup_manager
    )


@pytest.fixture(scope="session")
def test_data_factory(test_run_id: str) -> TestDataFactory:
    """Test data factory fixture"""
    return TestDataFactory(test_run_id)


@pytest.fixture(scope="session")
def cleanup_manager(cleanup_enabled: bool, debug_enabled: bool, comprehensive_cleanup_enabled: bool, cleanup_dry_run: bool) -> Generator[CleanupManager, None, None]:
    """Cleanup manager fixture - handles resource cleanup using AWS SDK and comprehensive cleanup"""
    manager = CleanupManager(
        cleanup_enabled=cleanup_enabled,
        debug=debug_enabled,
        dry_run=False  # Ensure actual cleanup, not dry run
    )
    
    try:
        yield manager
    finally:
        # Perform final cleanup at end of session
        if cleanup_enabled:
            try:
                # Phase 1: AWS SDK cleanup of registered resources
                successful, failed = manager.cleanup_all_registered_resources()
                if debug_enabled:
                    print(f"\n[CLEANUP] Phase 1 - AWS SDK cleanup: {successful} successful, {failed} failed")
                
                # Phase 2: Comprehensive cleanup using the cleanup script
                if comprehensive_cleanup_enabled:
                    comprehensive_success = _run_comprehensive_cleanup(debug_enabled, cleanup_dry_run)
                    if debug_enabled:
                        if comprehensive_success:
                            print(f"[CLEANUP] Phase 2 - Comprehensive cleanup: SUCCESS")
                        else:
                            print(f"[CLEANUP] Phase 2 - Comprehensive cleanup: FAILED")
                else:
                    if debug_enabled:
                        print(f"[CLEANUP] Phase 2 - Comprehensive cleanup: SKIPPED (disabled)")
                
                # Summary
                if debug_enabled:
                    print(f"[CLEANUP] ===== FINAL CLEANUP SUMMARY =====")
                    print(f"[CLEANUP] AWS SDK: {successful} successful, {failed} failed")
                    if comprehensive_cleanup_enabled:
                        print(f"[CLEANUP] Comprehensive: {'✅ SUCCESS' if comprehensive_success else '❌ FAILED'}")
                    if failed > 0 or (comprehensive_cleanup_enabled and not comprehensive_success):
                        print(f"[CLEANUP] ⚠️  Some cleanup issues detected. Consider manual cleanup if needed.")
                        print(f"[CLEANUP] Manual cleanup: python clear_test_data.py")
                    else:
                        print(f"[CLEANUP] 🎉 All cleanup completed successfully!")
                
            except Exception as e:
                if debug_enabled:
                    print(f"[CLEANUP] ❌ Cleanup process failed: {e}")
                    print(f"[CLEANUP] Manual cleanup recommended: python clear_test_data.py")


@pytest.fixture
def assertions() -> APIAssertions:
    """API assertions fixture"""
    return APIAssertions()


@pytest.fixture
def authenticated_client(api_client: APIClient, admin_auth: Dict[str, Any]) -> APIClient:
    """
    Pre-authenticated API client fixture using dynamic wheel group admin authentication
    
    Uses the working admin_auth fixture which creates wheel group admins dynamically.
    This bypasses the broken deployment admin authentication pattern.
    """
    # Use the working token from admin_auth fixture
    access_token = admin_auth.get('access_token')
    if not access_token:
        raise RuntimeError("No access token available from admin_auth fixture")
    
    # Set the working token in API client
    api_client.set_auth_token(access_token)
    
    print(f"[AUTH-CLIENT] Using working wheel group admin token for API client")
    print(f"[AUTH-CLIENT] Wheel group ID: {admin_auth.get('wheel_group_id')}")
    
    return api_client


@pytest.fixture
def logout_test_auth_manager(test_config: TestConfig, test_data_factory: TestDataFactory, 
                           debug_enabled: bool) -> AuthManager:
    """
    Isolated authentication manager for logout testing using dynamic admin creation
    
    This fixture creates a separate auth manager and uses the working dynamic 
    authentication pattern to prevent logout tests from affecting shared session.
    """
    # Create separate API client for isolation
    isolated_client = APIClient(
        base_url=test_config.api_base_url,
        timeout=test_config.request_timeout,
        max_retries=test_config.max_retries,
        retry_delay=test_config.retry_delay,
        debug=debug_enabled
    )
    
    try:
        # Create dynamic admin user for logout testing
        auth_data = _create_dynamic_admin_user(
            api_client=isolated_client,
            test_data_factory=test_data_factory,
            test_config=test_config,
            group_name="LogoutTestAdminGroup",
            debug_enabled=debug_enabled
        )
        
        # Create auth manager with working credentials
        cognito_auth = _create_cognito_authenticator(test_config, debug_enabled)
        isolated_auth_manager = AuthManager(isolated_client, debug=debug_enabled)
        isolated_auth_manager.cognito_authenticator = cognito_auth
        
        # Authenticate using the created admin credentials
        isolated_auth_manager.login(auth_data['username'], auth_data['password'])
        
        if debug_enabled:
            print(f"[LOGOUT-TEST] Isolated auth manager ready for logout testing")
        
        return isolated_auth_manager
        
    except Exception as e:
        if debug_enabled:
            print(f"[LOGOUT-TEST] Setup failed: {e}")
        pytest.fail(f"Isolated auth manager setup failed: {e}")


@pytest.fixture  
def logout_test_client(logout_test_auth_manager: AuthManager) -> APIClient:
    """Isolated API client for logout testing"""
    return logout_test_auth_manager.api_client


# ============================================================================
# ROLE-BASED AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def deployment_admin_auth(api_client: APIClient, test_config: TestConfig, 
                         test_data_factory: TestDataFactory, debug_enabled: bool,
                         cleanup_manager: CleanupManager) -> Dict[str, Any]:
    """Deployment admin authentication fixture using dynamic admin creation"""
    return _create_dynamic_admin_user(
        api_client=api_client,
        test_data_factory=test_data_factory,
        test_config=test_config,
        group_name="DeploymentAdminGroup",
        debug_enabled=debug_enabled,
        cleanup_manager=cleanup_manager
    )


@pytest.fixture(scope="session")  
def wheel_group_admin_auth(api_client: APIClient, test_config: TestConfig, 
                          test_data_factory: TestDataFactory, debug_enabled: bool,
                          cleanup_manager: CleanupManager) -> Dict[str, Any]:
    """Wheel group admin authentication using dynamic creation"""
    return _create_dynamic_admin_user(
        api_client=api_client,
        test_data_factory=test_data_factory,
        test_config=test_config,
        group_name="WheelGroupAdminGroup",
        debug_enabled=debug_enabled,
        cleanup_manager=cleanup_manager
    )


@pytest.fixture(scope="session")
def wheel_admin_auth_session(api_client: APIClient, test_config: TestConfig, 
                            test_data_factory: TestDataFactory, debug_enabled: bool,
                            cleanup_manager: CleanupManager) -> Dict[str, Any]:
    """Wheel admin authentication using dynamic creation"""
    return _create_dynamic_admin_user(
        api_client=api_client,
        test_data_factory=test_data_factory,
        test_config=test_config,
        group_name="WheelAdminGroup",
        debug_enabled=debug_enabled,
        cleanup_manager=cleanup_manager
    )


@pytest.fixture(scope="session")
def regular_user_auth_session(api_client: APIClient, test_config: TestConfig, 
                             test_data_factory: TestDataFactory, debug_enabled: bool,
                             cleanup_manager: CleanupManager) -> Dict[str, Any]:
    """Regular user authentication using dynamic creation"""
    return _create_dynamic_admin_user(
        api_client=api_client,
        test_data_factory=test_data_factory,
        test_config=test_config,
        group_name="RegularUserGroup",
        debug_enabled=debug_enabled,
        cleanup_manager=cleanup_manager
    )


# ============================================================================
# AUTHENTICATED CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def deployment_admin_client(api_client: APIClient, deployment_admin_auth: Dict[str, Any]) -> APIClient:
    """Pre-authenticated deployment admin API client"""
    return _create_authenticated_client(api_client, deployment_admin_auth)


@pytest.fixture
def admin_client(api_client: APIClient, wheel_group_admin_auth: Dict[str, Any]) -> APIClient:
    """Pre-authenticated wheel group admin API client"""
    return _create_authenticated_client(api_client, wheel_group_admin_auth)


@pytest.fixture
def wheel_admin_client(api_client: APIClient, wheel_admin_auth_session: Dict[str, Any]) -> APIClient:
    """Pre-authenticated wheel admin API client"""
    return _create_authenticated_client(api_client, wheel_admin_auth_session)


@pytest.fixture
def user_client(api_client: APIClient, regular_user_auth_session: Dict[str, Any]) -> APIClient:
    """Pre-authenticated regular user API client"""
    return _create_authenticated_client(api_client, regular_user_auth_session)


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def test_wheel_group(authenticated_client: APIClient, test_data_factory: TestDataFactory,
                    cleanup_manager: CleanupManager, assertions: APIAssertions) -> Dict[str, Any]:
    """Test wheel group fixture - creates a wheel group for testing"""
    # Create wheel group using public endpoint (for deployment admin users)
    wheel_group_data = test_data_factory.create_public_wheel_group_data()
    
    response = authenticated_client.post('/wheel-group/create-public', data=wheel_group_data)
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
    """Test wheel fixture - creates a wheel for testing"""
    wheel_group_id = test_wheel_group['wheel_group_id']
    wheel_data = test_data_factory.create_wheel_data()
    
    response = authenticated_client.post('/wheels', data=wheel_data)
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
    """Test participants fixture - creates participants for testing"""
    wheel_id = test_wheel['wheel_id']
    participants_data = test_data_factory.create_multiple_participants(3)
    
    created_participants = []
    
    for participant_data in participants_data:
        response = authenticated_client.post(f'/wheels/{wheel_id}/participants',
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


# ============================================================================
# TEST ENVIRONMENT SETUP
# ============================================================================

@pytest.fixture(scope="session")
def role_based_test_environment(test_config: TestConfig, api_client: APIClient, 
                               test_data_factory: TestDataFactory, cleanup_manager: CleanupManager,
                               debug_enabled: bool) -> Dict[str, Any]:
    """Set up test environment with dynamically created wheel groups for role-based testing"""
    if debug_enabled:
        print("\n[ROLE-TEST-ENV] Setting up role-based test environment with dynamic wheel groups...")
    
    created_resources = {
        'wheel_groups': {},
        'test_scenarios': {}
    }
    
    try:
        # Define dynamic test wheel groups (replacing static configuration)
        dynamic_test_groups = [
            {'key': 'isolated_group_1', 'name': 'IsolatedTestGroup1', 'description': 'Isolated test group for role testing - Group 1'},
            {'key': 'isolated_group_2', 'name': 'IsolatedTestGroup2', 'description': 'Second isolated group for cross-access testing'},
            {'key': 'shared_group', 'name': 'SharedTestGroup', 'description': 'Shared group with multiple roles for collaboration testing'}
        ]
        
        for group_config in dynamic_test_groups:
            if debug_enabled:
                print(f"[ROLE-TEST-ENV] Creating wheel group: {group_config['name']}")
            
            # Create wheel group using self-service endpoint
            wheel_group_data = test_data_factory.create_public_wheel_group_data(
                name=group_config['name']
            )
            
            response = api_client.post('/wheel-group/create-public',
                                     data=wheel_group_data)
            
            if response.is_success:
                wheel_group = response.json_data['wheel_group']
                admin_user = response.json_data['admin_user']
                
                created_resources['wheel_groups'][group_config['key']] = {
                    **wheel_group,
                    'admin_user': admin_user,
                    'description': group_config.get('description', '')
                }
                
                # Register for cleanup
                cleanup_manager.register_wheel_group(wheel_group['wheel_group_id'])
                
                if debug_enabled:
                    print(f"[ROLE-TEST-ENV] Created wheel group: {wheel_group['wheel_group_id']}")
                
                # Wait for DynamoDB consistency
                time.sleep(1.0)
            else:
                if debug_enabled:
                    print(f"[ROLE-TEST-ENV] Failed to create wheel group {group_config['key']}: {response.status_code}")
        
        # Define dynamic test scenarios (replacing static configuration)
        dynamic_test_scenarios = {
            'isolated': {
                'description': 'Each role in separate wheel groups',
                'primary_group': 'isolated_group_1',
                'secondary_group': 'isolated_group_2'
            },
            'shared': {
                'description': 'Multiple roles in same wheel group',
                'group': 'shared_group'
            },
            'cross_group': {
                'description': 'Users blocked from other wheel groups',
                'test_access_denial': True
            }
        }
        
        created_resources['test_scenarios'] = dynamic_test_scenarios
        
        if debug_enabled:
            print(f"[ROLE-TEST-ENV] Created {len(created_resources['wheel_groups'])} wheel groups")
            print(f"[ROLE-TEST-ENV] Configured {len(created_resources['test_scenarios'])} test scenarios")
        
        return created_resources
        
    except Exception as e:
        if debug_enabled:
            print(f"[ROLE-TEST-ENV] Setup failed: {e}")
        raise RuntimeError(f"Role-based test environment setup failed: {e}")


# ============================================================================
# ENVIRONMENT HEALTH CHECK FIXTURES
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def verify_test_environment(test_config: TestConfig, api_client: APIClient, debug_enabled: bool):
    """Verify test environment is accessible before running tests"""
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
    """Ensure test isolation by adding small delay between tests"""
    # Small delay to prevent rate limiting and ensure test isolation
    time.sleep(0.1)
    
    yield
    
    # Additional cleanup/verification could go here


# ============================================================================
# PYTEST HOOKS
# ============================================================================

def pytest_runtest_setup(item):
    """Setup for each test"""
    # Add any per-test setup here
    pass


def pytest_runtest_teardown(item):
    """Teardown for each test"""
    # Add any per-test teardown here
    pass


def pytest_sessionfinish(session, exitstatus):
    """Session cleanup - ensures comprehensive cleanup runs even if other cleanup fails"""
    debug_enabled = hasattr(session.config, 'getoption') and session.config.getoption("--integration-debug")
    
    if debug_enabled:
        print(f"\n[SESSION] Tests completed with exit status: {exitstatus}")
    
    # Final safety net - run comprehensive cleanup if enabled and cleanup wasn't disabled
    try:
        cleanup_enabled = not session.config.getoption("--no-cleanup")
        comprehensive_cleanup_enabled = session.config.getoption("--comprehensive-cleanup")
        cleanup_dry_run = session.config.getoption("--cleanup-dry-run")
        
        # Only run if both cleanup and comprehensive cleanup are enabled
        if cleanup_enabled and comprehensive_cleanup_enabled:
            if debug_enabled:
                print(f"\n[SESSION-CLEANUP] Running final comprehensive cleanup...")
            
            success = _run_comprehensive_cleanup(debug_enabled, cleanup_dry_run)
            
            if debug_enabled:
                if success:
                    print(f"[SESSION-CLEANUP] ✅ Final comprehensive cleanup successful")
                else:
                    print(f"[SESSION-CLEANUP] ⚠️  Final comprehensive cleanup had issues")
                    print(f"[SESSION-CLEANUP] 💡 Manual cleanup: python clear_test_data.py")
        elif debug_enabled:
            if not cleanup_enabled:
                print(f"[SESSION-CLEANUP] Skipped - cleanup disabled (--no-cleanup)")
            elif not comprehensive_cleanup_enabled:
                print(f"[SESSION-CLEANUP] Skipped - comprehensive cleanup disabled")
    
    except Exception as e:
        if debug_enabled:
            print(f"[SESSION-CLEANUP] ❌ Session cleanup failed: {e}")


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection - auto-mark tests based on their names"""
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
        
        # Auto-mark role-based tests
        if any(word in item.name.lower() for word in ["wheel_group_admin", "wheel_admin", "regular_user", "deployment_admin"]):
            item.add_marker(pytest.mark.role_based)
        
        # Auto-mark permission tests
        if any(word in item.name.lower() for word in ["permission", "access", "forbidden", "unauthorized"]):
            item.add_marker(pytest.mark.permissions)
        
        # Auto-mark spinning tests
        if any(word in item.name.lower() for word in ["spin", "select", "rigg", "weight"]):
            item.add_marker(pytest.mark.spinning)
        
        # Auto-mark workflow tests
        if "workflow" in item.name.lower():
            item.add_marker(pytest.mark.workflow)
        
        # Auto-mark cross-role tests
        if "cross_role" in item.name.lower():
            item.add_marker(pytest.mark.cross_role)
