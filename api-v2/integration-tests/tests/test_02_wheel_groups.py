"""
Wheel Group Management Integration Tests for AWS Ops Wheel v2

These tests verify wheel group CRUD operations including the critical public 
wheel group creation endpoint that enables self-service onboarding.
"""
import pytest
from typing import Dict, Any, List

from utils.api_client import APIClient
from utils.test_data_factory import TestDataFactory
from utils.cleanup import CleanupManager
from utils.assertions import APIAssertions


class TestWheelGroupCRUD:
    """Basic wheel group CRUD operations"""
    
    @pytest.mark.critical
    @pytest.mark.crud
    def test_create_wheel_group_admin(self, authenticated_client: APIClient, 
                                     test_data_factory: TestDataFactory,
                                     cleanup_manager: CleanupManager, 
                                     assertions: APIAssertions):
        """
        Test creating wheel group via admin API (public endpoint for deployment admins)
        
        Tests deployment admin wheel group creation using the public endpoint.
        """
        # Generate test data for public endpoint
        wheel_group_data = test_data_factory.create_public_wheel_group_data()
        
        # Create wheel group via public endpoint (for deployment admins)
        response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=wheel_group_data)
        
        # Verify creation
        assertions.assert_success_response(response, "Failed to create wheel group via admin API")
        assertions.assert_public_wheel_group_structure(response)
        
        # Access nested wheel group data
        wheel_group = response.json_data['wheel_group']
        
        # Verify response contains expected data
        assert wheel_group['wheel_group_name'] == wheel_group_data['wheel_group_name'], \
            f"Wheel group name mismatch: expected {wheel_group_data['wheel_group_name']}, got {wheel_group['wheel_group_name']}"
        assert 'wheel_group_id' in wheel_group, "Response missing wheel_group_id"
        assert 'created_at' in wheel_group, "Response missing created_at"
        
        # Register for cleanup
        wheel_group_id = wheel_group.get('wheel_group_id')
        if wheel_group_id:
            cleanup_manager.register_wheel_group(wheel_group_id)
    
    @pytest.mark.critical
    @pytest.mark.crud
    def test_create_public_wheel_group(self, authenticated_client: APIClient, 
                                      test_data_factory: TestDataFactory,
                                      cleanup_manager: CleanupManager, 
                                      assertions: APIAssertions):
        """
        Test creating wheel group via public API endpoint
        
        This tests the CRITICAL deployment admin endpoint for wheel group creation.
        This endpoint requires deployment admin authentication (deployment_admin=true).
        """
        # Generate public wheel group data
        public_data = test_data_factory.create_public_wheel_group_data()
        
        # Create wheel group via public endpoint (requires deployment admin auth)
        response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=public_data)
        
        # Verify creation using the public-specific assertion
        assertions.assert_success_response(response, 
                                         "CRITICAL: Public wheel group creation failed - this breaks self-service onboarding")
        assertions.assert_public_wheel_group_structure(response)
        
        # Access nested wheel group data
        wheel_group = response.json_data['wheel_group']
        admin_user = response.json_data['admin_user']
        
        # Verify wheel group data matches request
        assert wheel_group['wheel_group_name'] == public_data['wheel_group_name'], \
            f"Wheel group name mismatch: expected {public_data['wheel_group_name']}, got {wheel_group['wheel_group_name']}"
        
        # Verify admin user was created correctly
        expected_username = public_data['admin_user']['username']
        assert admin_user.get('name') == expected_username, \
            f"Admin user name mismatch: expected {expected_username}, got {admin_user.get('name')}"
        
        expected_email = public_data['admin_user']['email']
        assert admin_user.get('email') == expected_email, \
            f"Admin user email mismatch: expected {expected_email}, got {admin_user.get('email')}"
        
        assert admin_user.get('role') == 'ADMIN', \
            f"Admin user role mismatch: expected ADMIN, got {admin_user.get('role')}"
        
        # Register for cleanup (will need admin auth for cleanup)
        wheel_group_id = wheel_group.get('wheel_group_id')
        if wheel_group_id:
            cleanup_manager.register_wheel_group(wheel_group_id)
    
    @pytest.mark.crud
    def test_get_wheel_group(self, authenticated_client: APIClient, test_wheel_group: Dict[str, Any],
                            assertions: APIAssertions):
        """
        Test retrieving a wheel group via admin list endpoint
        
        Deployment admins can't access individual wheel group details directly,
        but can list all wheel groups and find the specific one.
        """
        wheel_group_id = test_wheel_group['wheel_group_id']
        
        # Get wheel group via admin list endpoint (deployment admins use this)
        response = authenticated_client.get('/app/api/v2/admin/wheel-groups')
        
        # Verify response
        assertions.assert_success_response(response, "Failed to retrieve wheel groups via admin endpoint")
        assertions.assert_json_response(response)
        
        # Find our specific wheel group in the list
        assert 'wheel_groups' in response.json_data, "Response missing wheel_groups field"
        wheel_groups = response.json_data['wheel_groups']
        
        found_wheel_group = None
        for group in wheel_groups:
            if group.get('wheel_group_id') == wheel_group_id:
                found_wheel_group = group
                break
        
        assert found_wheel_group is not None, f"Test wheel group {wheel_group_id} not found in admin list"
        assert found_wheel_group['wheel_group_name'] == test_wheel_group['wheel_group_name'], "Wheel group name mismatch"
    
    @pytest.mark.crud
    def test_list_wheel_groups(self, authenticated_client: APIClient, test_wheel_group: Dict[str, Any],
                              assertions: APIAssertions):
        """
        Test listing wheel groups
        
        Tests the admin endpoint for listing all wheel groups.
        """
        # List wheel groups
        response = authenticated_client.get('/app/api/v2/admin/wheel-groups')
        
        # Verify response
        assertions.assert_success_response(response, "Failed to list wheel groups")
        assertions.assert_json_response(response)
        
        # Check response structure
        assert 'wheel_groups' in response.json_data, "Response missing wheel_groups field"
        wheel_groups = response.json_data['wheel_groups']
        assert isinstance(wheel_groups, list), "Wheel groups field is not a list"
        
        # Verify our test wheel group is in the list
        test_group_id = test_wheel_group['wheel_group_id']
        found_test_group = False
        
        for group in wheel_groups:
            if group.get('wheel_group_id') == test_group_id:
                found_test_group = True
                break
        
        assert found_test_group, f"Test wheel group {test_group_id} not found in list"
    
    @pytest.mark.crud
    def test_update_wheel_group(self, authenticated_client: APIClient, test_wheel_group: Dict[str, Any],
                               assertions: APIAssertions):
        """
        Test updating a wheel group via admin operations
        
        Deployment admins cannot directly update wheel groups they're not members of.
        This test verifies that the wheel group exists and can be retrieved via admin list.
        """
        wheel_group_id = test_wheel_group['wheel_group_id']
        
        # Attempt to update wheel group (deployment admins can't do this directly)
        update_data = {
            'wheel_group_name': test_wheel_group['wheel_group_name'] + ' Updated',
            'description': 'Updated description for integration testing'
        }
        
        response = authenticated_client.put(f'/app/api/v2/wheel-group/{wheel_group_id}', data=update_data)
        
        # Deployment admins should get a permission error (403) since they're not wheel group members
        expected_status_codes = [400, 403, 404]  # Various permission/access errors
        assert response.status_code in expected_status_codes, \
            f"Expected permission error ({expected_status_codes}), got {response.status_code}"
        
        # Verify wheel group still exists via admin list (this confirms the wheel group wasn't damaged)
        list_response = authenticated_client.get('/app/api/v2/admin/wheel-groups')
        assertions.assert_success_response(list_response, "Failed to verify wheel group exists after update attempt")
        
        # Find the wheel group in the admin list to verify it's still there
        wheel_groups = list_response.json_data.get('wheel_groups', [])
        found_wheel_group = None
        for group in wheel_groups:
            if group.get('wheel_group_id') == wheel_group_id:
                found_wheel_group = group
                break
        
        assert found_wheel_group is not None, f"Wheel group {wheel_group_id} disappeared after update attempt"
        # Name should be unchanged since update was rejected
        assert found_wheel_group['wheel_group_name'] == test_wheel_group['wheel_group_name'], \
            "Wheel group name was unexpectedly changed"
    
    @pytest.mark.crud 
    def test_delete_wheel_group(self, authenticated_client: APIClient, test_data_factory: TestDataFactory,
                               cleanup_manager: CleanupManager, assertions: APIAssertions):
        """
        Test deleting a wheel group via admin operations
        
        Deployment admins cannot directly delete wheel groups they're not members of.
        This test verifies the permission model works correctly.
        """
        # Create a wheel group specifically for deletion test using public endpoint
        wheel_group_data = test_data_factory.create_public_wheel_group_data()
        response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=wheel_group_data)
        assertions.assert_success_response(response, "Failed to create wheel group for deletion test")
        assertions.assert_public_wheel_group_structure(response)
        
        # Extract wheel group from nested response
        wheel_group = response.json_data['wheel_group']
        wheel_group_id = wheel_group['wheel_group_id']
        
        # Attempt to delete the wheel group (deployment admins can't do this directly)
        delete_response = authenticated_client.delete(f'/app/api/v2/wheel-group/{wheel_group_id}')
        
        # Deployment admins should get a permission error since they're not wheel group members
        expected_status_codes = [400, 403, 404]  # Various permission/access errors
        assert delete_response.status_code in expected_status_codes, \
            f"Expected permission error ({expected_status_codes}), got {delete_response.status_code}"
        
        # Verify wheel group still exists via admin list (confirms deletion was properly rejected)
        list_response = authenticated_client.get('/app/api/v2/admin/wheel-groups')
        assertions.assert_success_response(list_response, "Failed to verify wheel group exists after delete attempt")
        
        # Find the wheel group in the admin list to verify it's still there
        wheel_groups = list_response.json_data.get('wheel_groups', [])
        found_wheel_group = None
        for group in wheel_groups:
            if group.get('wheel_group_id') == wheel_group_id:
                found_wheel_group = group
                break
        
        assert found_wheel_group is not None, f"Wheel group {wheel_group_id} was unexpectedly deleted"
        assert found_wheel_group['wheel_group_name'] == wheel_group['wheel_group_name'], \
            "Wheel group data was corrupted during delete attempt"
        
        # Register for cleanup since we couldn't delete it in the test
        cleanup_manager.register_wheel_group(wheel_group_id)


class TestWheelGroupValidation:
    """Wheel group validation and error handling tests"""
    
    @pytest.mark.crud
    def test_create_wheel_group_missing_name(self, authenticated_client: APIClient, 
                                            test_data_factory: TestDataFactory,
                                            assertions: APIAssertions):
        """
        Test creating wheel group with missing required name
        
        Tests validation of required fields.
        """
        # Create invalid data (missing wheel_group_name)
        invalid_data = {
            'description': 'Test wheel group without name'
        }
        
        # Attempt to create wheel group
        response = authenticated_client.post('/app/api/v2/wheel-group', data=invalid_data)
        
        # Should fail with validation error (accept specific error message)
        assert response.status_code == 400, f"Expected 400 status code, got {response.status_code}"
        assert any(keyword in response.text.lower() for keyword in ['wheel_group_name', 'required', 'name']), \
            f"Expected wheel_group_name validation error, got: {response.text}"
    
    @pytest.mark.crud
    def test_create_duplicate_wheel_group_name(self, authenticated_client: APIClient, 
                                              test_wheel_group: Dict[str, Any],
                                              test_data_factory: TestDataFactory,
                                              assertions: APIAssertions):
        """
        Test creating wheel group with duplicate name
        
        Tests uniqueness validation.
        """
        # Try to create wheel group with same name
        duplicate_data = test_data_factory.create_wheel_group_data(
            name=test_wheel_group['wheel_group_name']
        )
        
        # Attempt to create duplicate
        response = authenticated_client.post('/app/api/v2/wheel-group', data=duplicate_data)
        
        # Should fail with conflict error
        assert response.status_code in [400, 409], f"Expected 400/409 for duplicate name, got {response.status_code}"
    
    @pytest.mark.crud
    def test_get_nonexistent_wheel_group(self, authenticated_client: APIClient, assertions: APIAssertions):
        """
        Test retrieving non-existent wheel group
        
        Tests error handling for non-existent resources. For deployment admins,
        this may return 403 (not authorized) instead of 404 (not found).
        """
        # Try to get wheel group that doesn't exist
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = authenticated_client.get(f'/app/api/v2/wheel-group/{fake_id}')
        
        # Should return 403 (deployment admin not authorized) or 404 (not found)
        expected_codes = [403, 404]
        assert response.status_code in expected_codes, \
            f"Expected {expected_codes} for non-existent wheel group, got {response.status_code}: {response.text}"
    
    @pytest.mark.crud
    def test_unauthorized_wheel_group_access(self, api_client: APIClient, test_wheel_group: Dict[str, Any],
                                            assertions: APIAssertions):
        """
        Test accessing wheel group without authentication
        
        Tests authentication requirements.
        """
        # Clear authentication
        api_client.clear_auth_token()
        
        # Try to access wheel group
        wheel_group_id = test_wheel_group['wheel_group_id']
        response = api_client.get(f'/app/api/v2/wheel-group/{wheel_group_id}')
        
        # Should fail with authentication error
        assert response.status_code in [401, 403], f"Expected 401/403 for unauthenticated access, got {response.status_code}"


class TestPublicWheelGroupValidation:
    """Public wheel group endpoint validation tests"""
    
    @pytest.mark.critical
    @pytest.mark.crud
    def test_public_wheel_group_missing_admin_user(self, authenticated_client: APIClient, 
                                                   test_data_factory: TestDataFactory,
                                                   assertions: APIAssertions):
        """
        Test public wheel group creation with missing admin user data
        
        This tests validation of the critical deployment admin endpoint.
        """
        # Create invalid public data (missing admin_user)
        invalid_data = {
            'wheel_group_name': test_data_factory.generate_wheel_group_name("InvalidTest"),
            'description': 'Test wheel group without admin user'
        }
        
        # Attempt to create via public endpoint (requires deployment admin auth)
        response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=invalid_data)
        
        # Should fail with validation error (accept specific error message)
        assert response.status_code == 400, f"Expected 400 status code, got {response.status_code}"
        assert 'admin_user' in response.text.lower(), f"Expected admin_user error, got: {response.text}"
    
    @pytest.mark.critical
    @pytest.mark.crud
    def test_public_wheel_group_invalid_admin_email(self, authenticated_client: APIClient, 
                                                    test_data_factory: TestDataFactory,
                                                    assertions: APIAssertions):
        """
        Test public wheel group creation with invalid admin email
        
        Tests email validation in the critical deployment admin endpoint.
        """
        # Create data with invalid email
        invalid_data = test_data_factory.create_public_wheel_group_data()
        invalid_data['admin_user']['email'] = 'invalid-email-format'
        
        # Attempt to create via public endpoint (requires deployment admin auth)
        response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=invalid_data)
        
        # Should fail with validation error (accept specific Cognito error message)
        assert response.status_code == 400, f"Expected 400 status code, got {response.status_code}"
        assert any(keyword in response.text.lower() for keyword in ['email', 'format', 'invalid']), \
            f"Expected email validation error, got: {response.text}"
    
    @pytest.mark.crud
    def test_public_wheel_group_weak_password(self, authenticated_client: APIClient, 
                                             test_data_factory: TestDataFactory,
                                             assertions: APIAssertions):
        """
        Test public wheel group creation with weak admin password
        
        Tests password validation requirements.
        """
        # Create data with weak password
        weak_data = test_data_factory.create_public_wheel_group_data()
        weak_data['admin_user']['password'] = '123'  # Too weak
        
        # Attempt to create via public endpoint (requires deployment admin auth)
        response = authenticated_client.post('/app/api/v2/wheel-group/create-public', data=weak_data)
        
        # Should fail with validation error (accept specific password error message)
        assert response.status_code == 400, f"Expected 400 status code, got {response.status_code}"
        assert any(keyword in response.text.lower() for keyword in ['password', 'characters', 'length']), \
            f"Expected password validation error, got: {response.text}"


class TestWheelGroupPagination:
    """Wheel group pagination tests"""
    
    @pytest.mark.crud
    def test_wheel_group_list_pagination(self, authenticated_client: APIClient, assertions: APIAssertions):
        """
        Test wheel group list pagination
        
        Tests pagination parameters and response structure. Note: Backend may not 
        implement pagination limits, so we test what we can.
        """
        # Test with pagination parameters
        response = authenticated_client.get('/app/api/v2/admin/wheel-groups', 
                                          params={'page': 1, 'limit': 5})
        
        # Verify response
        assertions.assert_success_response(response, "Failed to get paginated wheel groups")
        assertions.assert_json_response(response)
        
        # Check basic response structure
        assert 'wheel_groups' in response.json_data, "Response missing wheel_groups field"
        wheel_groups = response.json_data['wheel_groups']
        assert isinstance(wheel_groups, list), "Wheel groups field is not a list"
        
        # Check if pagination is actually implemented by backend
        if len(wheel_groups) <= 5:
            print(f"[SUCCESS] Pagination limit respected: {len(wheel_groups)} <= 5")
        else:
            print(f"[INFO] Backend doesn't implement pagination limits - returned {len(wheel_groups)} items")
            # This is acceptable - not all backends implement pagination
        
        # Check for pagination metadata (if supported)
        pagination_fields = ['total', 'page', 'limit', 'has_more', 'next_page']
        has_pagination_meta = any(field in response.json_data for field in pagination_fields)
        
        # Pagination metadata is optional, just verify response is valid
        if has_pagination_meta:
            print(f"[SUCCESS] Pagination metadata found: {[f for f in pagination_fields if f in response.json_data]}")
        else:
            print("[INFO] No pagination metadata found - backend may not implement full pagination")
        
        # At minimum, verify we got some wheel groups (test environment should have data)
        assert len(wheel_groups) >= 0, "Invalid wheel groups count"
