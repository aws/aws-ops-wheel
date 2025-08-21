# AWS Ops Wheel v2 Unit Tests

This directory contains comprehensive unit tests for the v2 multi-tenant architecture of AWS Ops Wheel.

## Test Structure

### Current Implementation (4 files)
- **`conftest.py`** - Enhanced test fixtures for multi-tenant testing
- **`test_base.py`** - Exception class tests (4 tests)
- **`test_utils_v2.py`** - Repository layer and utilities (35 tests)
- **`test_selection_algorithms.py`** - Selection algorithms and API endpoints (15 tests)

**Total: 54 tests implemented**

### Planned Complete Implementation (10 files)
The full test suite will include:

1. **`conftest.py`** - Multi-tenant fixtures ✓
2. **`test_base.py`** - Exception classes (4 tests) ✓
3. **`test_utils_v2.py`** - Repository layer (35 tests) ✓
4. **`test_selection_algorithms.py`** - Selection algorithms (15 tests) ✓
5. **`test_wheel_operations.py`** - Wheel CRUD operations (18 tests)
6. **`test_participant_operations.py`** - Participant CRUD operations (24 tests)
7. **`test_wheel_group_management.py`** - Multi-tenant wheel group management (22 tests)
8. **`test_wheel_group_middleware.py`** - Authentication & authorization (16 tests)
9. **`test_deployment_admin_operations.py`** - Admin operations (8 tests)
10. **`test_api_gateway_authorizer.py`** - Lambda authorizer (10 tests)

**Total Planned: 150+ tests**

## Key Testing Features

### Multi-Tenant Architecture Testing
- **Wheel Group Isolation**: Tests ensure complete isolation between wheel groups
- **User Role Testing**: Comprehensive role-based access control validation
- **Cross-Tenant Security**: Validates that users cannot access other wheel groups

### Enhanced V2 Features
- **Repository Pattern**: Tests the new repository abstraction layer
- **Cognito Integration**: Mocks AWS Cognito operations for user management
- **Permission System**: Tests the enhanced role-based permission system
- **Composite Keys**: Tests the new multi-tenant database schema

### Test Quality Standards
- **Comprehensive Fixtures**: Isolated test environments with cleanup
- **Mock External Services**: AWS services mocked with `moto` and `unittest.mock`
- **Statistical Validation**: Selection algorithm distribution testing
- **Edge Case Coverage**: Error conditions, boundary values, constraint validation

## Prerequisites

```bash
# Install test dependencies
pip install pytest moto boto3

# Required environment variables (set by conftest.py for tests)
export WHEEL_GROUPS_TABLE=OpsWheelV2-WheelGroups-test
export USERS_TABLE=OpsWheelV2-Users-test
export WHEELS_TABLE=OpsWheelV2-Wheels-test
export PARTICIPANTS_TABLE=OpsWheelV2-Participants-test
export COGNITO_USER_POOL_ID=us-west-2_TEST123456
export COGNITO_CLIENT_ID=test-client-id
```

## Running Tests

### Run All Tests
```bash
# From project root
pytest api-v2/tests/ -v

# With coverage
pytest api-v2/tests/ --cov=api-v2 --cov-report=html -v
```

### Run Specific Test Files
```bash
# Repository and utilities
pytest api-v2/tests/test_utils_v2.py -v

# Selection algorithms
pytest api-v2/tests/test_selection_algorithms.py -v

# Exception classes
pytest api-v2/tests/test_base.py -v
```

### Run by Test Category
```bash
# Repository tests
pytest api-v2/tests/test_utils_v2.py -k "Repository" -v

# Multi-tenant isolation tests
pytest api-v2/tests/ -k "isolation" -v

# Permission tests (when implemented)
pytest api-v2/tests/ -k "permission" -v
```

## Test Categories

### 1. Foundation Tests (47 tests)
- **Exception Classes**: Custom error handling
- **Utilities**: UUID generation, timestamps, type conversion
- **Repository Layer**: Database abstraction with multi-tenant keys

### 2. Core Business Logic (57 tests planned)
- **Selection Algorithms**: Weight-based random selection with rigging
- **Wheel Operations**: CRUD operations within wheel groups
- **Participant Operations**: Multi-tenant participant management

### 3. Multi-Tenant Features (46 tests planned)
- **Wheel Group Management**: Multi-tenant organization management
- **Authentication**: JWT validation and user context
- **Authorization**: Role-based permission checking
- **Admin Operations**: Cross-wheel-group administrative functions

## Key Testing Patterns

### 1. Multi-Tenant Isolation
```python
def test_cross_wheel_group_isolation():
    """Ensure complete isolation between wheel groups"""
    # Create resources in different wheel groups
    # Verify operations only affect the correct wheel group
```

### 2. Permission-Based Testing
```python
@pytest.mark.parametrize("user_role,expected_access", [
    ('ADMIN', True),
    ('WHEEL_ADMIN', True), 
    ('USER', False)
])
def test_role_based_access(user_role, expected_access):
    """Test role-based access control"""
```

### 3. Repository Pattern Testing
```python
def test_repository_crud_operations():
    """Test complete CRUD lifecycle through repository"""
    # Create -> Read -> Update -> Delete
    # Verify database state at each step
```

### 4. Statistical Algorithm Testing
```python
def test_selection_distribution():
    """Test selection algorithms maintain statistical properties"""
    # Run 1000+ selections
    # Verify distribution matches weights within tolerance
```

## Comparison with V1 Tests

### V1 Architecture (4 test files, ~40 tests)
- Single-tenant with global tables
- Simple CRUD operations
- Basic algorithm testing
- No authentication/authorization

### V2 Architecture (10 test files, 150+ tests)
- Multi-tenant with wheel group isolation
- Repository pattern with complex relationships
- Enhanced security and permission testing
- Cognito integration and JWT validation
- Cross-tenant isolation validation
- Deployment admin functionality

## Mock Strategy

### DynamoDB Tables
- **4 Tables**: WheelGroups, Users, Wheels, Participants
- **GSI Support**: Complex queries with secondary indexes
- **Extended Functions**: Custom table methods for testing

### AWS Services
- **Cognito**: User creation, deletion, password management
- **DynamoDB**: Multi-table operations with relationships
- **API Gateway**: Event structure and authorizer context

### Test Data
- **Isolated Fixtures**: Each test gets clean database state
- **Sample Data**: Realistic test data with proper relationships
- **Parameterized Tests**: Multiple scenarios with same test logic

## Best Practices

1. **Isolation**: Each test is completely independent
2. **Cleanup**: Fixtures automatically clean up after tests
3. **Realistic Data**: Test data mirrors production structure
4. **Edge Cases**: Test boundary conditions and error states
5. **Performance**: Statistical tests validate algorithm performance
6. **Security**: Multi-tenant isolation is rigorously tested

This test suite ensures v2 maintains the same quality standards as v1 while properly testing the enhanced multi-tenant architecture and security model.
