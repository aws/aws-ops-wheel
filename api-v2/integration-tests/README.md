# AWS Ops Wheel v2 Integration Tests

This directory contains comprehensive integration tests for the AWS Ops Wheel v2 API. These tests validate critical functionality including authentication, wheel group management, and the public self-service onboarding endpoint.

## Overview

The integration test suite is designed to:
- Test critical v2 functionality, especially the public wheel group creation endpoint
- Validate authentication flows including admin login and password changes
- Ensure API reliability through comprehensive CRUD testing
- Maintain test environment cleanliness through automatic cleanup
- Support multiple test environments (test, dev)

## Test Structure

### Test Files (run in order)
- `test_00_environment.py` - Environment health and configuration validation
- `test_01_authentication.py` - Authentication flows and JWT token validation
- `test_02_wheel_groups.py` - **Critical** wheel group CRUD and public endpoint testing

### Core Components
- `config/` - Environment-specific configuration management
- `utils/` - HTTP client, authentication, test data generation, and cleanup utilities
- `conftest.py` - Pytest fixtures and session management

## Quick Start

### Prerequisites
1. Python 3.8+ installed
2. Access to a test environment deployment of AWS Ops Wheel v2
3. Admin credentials for the test environment

### Installation
```bash
# Navigate to integration tests directory
cd api-v2/integration-tests

# Install dependencies
pip install -r requirements.txt
```

### Configuration
Edit `config/environments.json` to match your test environment:

```json
{
  "test": {
    "api_base_url": "https://your-test-api.execute-api.region.amazonaws.com/test",
    "admin_username": "admin",
    "admin_password": "your-admin-password",
    "cleanup_enabled": true
  }
}
```

### Running Tests

#### Run All Tests
```bash
pytest --environment=test --debug
```

#### Run Critical Tests Only
```bash
pytest -m critical --environment=test --debug
```

#### Run Specific Test Categories
```bash
# Authentication tests
pytest -m auth --environment=test

# CRUD operation tests
pytest -m crud --environment=test

# Admin-only functionality tests
pytest -m admin --environment=test

# Smoke tests for quick validation
pytest -m smoke --environment=test
```

#### Environment-Specific Testing
```bash
# Test against 'test' environment
pytest --environment=test

# Test against 'dev' environment  
pytest --environment=dev
```

#### Cleanup Management
```bash
# Run with cleanup disabled (leaves test data for debugging)
pytest --no-cleanup --environment=test

# Override admin password
pytest --admin-password="NewPassword123!" --environment=test
```

### Test Reports
HTML reports are automatically generated in `reports/integration_test_report.html`.

## Critical Tests

### Public Wheel Group Creation (`test_02_wheel_groups.py`)
This tests the **CRITICAL** public endpoint `/app/api/v2/public/wheel-groups` that enables:
- Self-service wheel group creation without authentication
- Automatic admin user creation for new wheel groups
- Validation of required fields and business rules

**Why Critical**: This endpoint enables self-service onboarding and is essential for the v2 system's usability.

### Admin Authentication (`test_01_authentication.py`)
Tests the recently fixed admin login flow including:
- Automatic password change handling
- JWT token validation
- Admin privilege verification

**Why Critical**: Admin access is required for system management and many test operations.

## Environment Requirements

### Test Environment
- Must be a non-production environment (safety check included)
- Admin user must exist with known credentials
- API must be accessible via HTTPS
- Database must be clean or cleanable

### Required Endpoints
The tests validate these critical endpoints:
- `POST /app/api/v2/auth/login` - Admin authentication
- `POST /app/api/v2/public/wheel-groups` - **CRITICAL** public wheel group creation
- `GET /app/api/v2/admin/wheel-groups` - Admin wheel group management
- Full CRUD operations for wheel groups, wheels, and participants

## Test Configuration

### Pytest Markers
- `@pytest.mark.critical` - Must-pass tests for core functionality  
- `@pytest.mark.smoke` - Quick validation tests
- `@pytest.mark.auth` - Authentication and authorization tests
- `@pytest.mark.crud` - Create, Read, Update, Delete operation tests
- `@pytest.mark.admin` - Admin-only functionality tests
- `@pytest.mark.slow` - Tests that take longer to execute

### Command Line Options
- `--environment` - Test environment (test, dev)
- `--cleanup` - Enable/disable test data cleanup (default: enabled)
- `--debug` - Enable debug logging
- `--admin-password` - Override admin password

## Test Data Management

### Automatic Cleanup
- All created resources are automatically tracked and cleaned up
- Cleanup runs at the end of the test session
- Failed cleanups are logged for manual review
- Force cleanup available for stubborn test data

### Test Data Generation
- Unique names using timestamps prevent conflicts
- Realistic data follows business validation rules
- Test isolation through unique identifiers
- Consistent data structure across test runs

### Manual Cleanup
If automatic cleanup fails:
```bash
# Check for remaining test resources in the admin interface
# Look for resources with names containing:
# - "IntegTest"
# - "PublicTest" 
# - Current timestamp from test run
```

## Common Issues

### Authentication Errors
- Verify admin credentials in `config/environments.json`
- Check if admin password needs to be changed (auto-handled)
- Ensure admin user has `deployment_admin` privileges

### Environment Access
- Verify API URL is correct and accessible
- Check network connectivity to test environment
- Ensure HTTPS is configured properly

### Test Data Conflicts
- Enable cleanup or manually clean test environment
- Check for leftover resources from previous test runs
- Verify unique test run IDs are being generated

## Development

### Adding New Tests
1. Use existing fixtures from `conftest.py`
2. Follow naming conventions for auto-marking
3. Include proper cleanup registration
4. Add comprehensive assertions

### Test Structure Best Practices
```python
def test_new_functionality(authenticated_client, test_data_factory, 
                          cleanup_manager, assertions):
    # Generate test data
    data = test_data_factory.create_test_data()
    
    # Execute operation
    response = authenticated_client.post('/endpoint', data=data)
    
    # Validate response
    assertions.assert_success_response(response)
    
    # Register for cleanup
    cleanup_manager.register_resource(response.json_data['id'])
```

### Environment Configuration
Add new environments in `config/environments.json`:
```json
{
  "new_env": {
    "api_base_url": "https://new-env.example.com/api",
    "admin_username": "admin",
    "admin_password": "password",
    "cleanup_enabled": true,
    "timeout_seconds": 30
  }
}
```

## Troubleshooting

### Debug Mode
Enable debug logging to see detailed HTTP requests/responses:
```bash
pytest --debug --environment=test -v
```

### Individual Test Execution
Run specific tests for focused debugging:
```bash
pytest tests/test_02_wheel_groups.py::TestWheelGroupCRUD::test_create_public_wheel_group --debug
```

### Cleanup Verification
Check if cleanup completed successfully:
```bash
pytest --debug 2>&1 | grep CLEANUP
```

## Contributing

When adding new integration tests:
1. Follow the existing patterns and structure
2. Include appropriate pytest markers
3. Ensure proper cleanup registration
4. Test both success and failure scenarios
5. Update this README if adding new critical functionality

## Support

For issues with the integration test suite:
1. Check the HTML test report for detailed failure information
2. Run with `--debug` flag for detailed logging
3. Verify environment configuration and connectivity
4. Check for test data conflicts or cleanup issues
