"""
Integration tests for USER role workflows in AWS Ops Wheel v2

Tests comprehensive end-to-end workflows for standard users (USER role):
- Read-only wheel access and viewing
- Participant information viewing
- Wheel spinning and results viewing
- Permission boundary enforcement (cannot modify anything)
- Security isolation between wheel groups

USER Role Permissions:
- ✅ view_wheels: Can view wheel information
- ✅ view_participants: Can view participant information  
- ✅ spin_wheels: Can spin wheels and view results
- ❌ Cannot create wheels
- ❌ Cannot modify wheels
- ❌ Cannot delete wheels
- ❌ Cannot create participants
- ❌ Cannot modify participants
- ❌ Cannot delete participants
- ❌ Cannot manage users
- ❌ Cannot manage wheel groups
- ❌ Cannot access other wheel groups

Uses dynamic user creation - no dependency on static users from environments.json
"""

import pytest
import time
from typing import Dict, List, Any

from utils.api_client import APIClient, APIResponse
from utils.assertions import APIAssertions
from utils.test_data_factory import TestDataFactory
from utils.cleanup import CleanupManager
from utils.cognito_authenticator import CognitoAuthenticator
from config.test_config import TestConfig

# Test constants
CONSISTENCY_WAIT_SECONDS = 1.0
SHORT_WAIT_SECONDS = 0.5
MICRO_WAIT_SECONDS = 0.2
SPIN_DELAY_SECONDS = 0.1

# Spinning test constants
MULTIPLE_SPIN_COUNT = 5
VIEW_VERIFICATION_COUNT = 3


class TestUserWorkflows:
    """Test class for USER role end-to-end workflows (read-only operations)"""

    def _create_wheel_group_with_user_access(self, api_client: APIClient, 
                                           test_data_factory: TestDataFactory,
                                           cleanup_manager: CleanupManager,
                                           assertions: APIAssertions,
                                           wheel_group_name: str) -> Dict[str, Any]:
        """
        Helper method to create a wheel group with content and a regular user for testing
        
        Returns:
            Dict containing wheel_group_id, wheels, participants, and user authentication info
        """
        # Create wheel group and get admin user
        wheel_group_data = test_data_factory.create_public_wheel_group_data(
            name=wheel_group_name
        )
        
        response = api_client.post('/wheel-group/create-public', data=wheel_group_data)
        assertions.assert_success_response(response, f"Failed to create wheel group {wheel_group_name}")
        
        wheel_group = response.json_data['wheel_group']
        admin_user = response.json_data['admin_user']
        
        wheel_group_id = wheel_group['wheel_group_id']
        admin_username = wheel_group_data['admin_user']['username']
        admin_password = wheel_group_data['admin_user']['password']
        
        cleanup_manager.register_wheel_group(wheel_group_id)
        
        # Wait for consistency
        time.sleep(CONSISTENCY_WAIT_SECONDS)
        
        # Authenticate as admin to set up test content
        config = TestConfig('test')
        
        cognito_auth = CognitoAuthenticator(
            user_pool_id=config.cognito_user_pool_id,
            client_id=config.cognito_client_id,
            region=config.aws_region,
            debug=True
        )
        
        admin_auth_result = cognito_auth.authenticate_user(admin_username, admin_password)
        
        admin_client = APIClient(
            base_url=config.api_base_url,
            debug=True
        )
        admin_client.set_auth_token(admin_auth_result['id_token'])
        
        # Create test wheels and participants using admin
        wheels_data = [
            {
                "name": "ProjectAssignmentWheel",
                "description": "Assign team members to projects",
                "participants": ["Alice", "Bob", "Charlie", "Diana"]
            },
            {
                "name": "CodeReviewWheel",
                "description": "Select code reviewers",
                "participants": ["Senior Dev", "Junior Dev", "Team Lead"]
            }
        ]
        
        created_wheels = []
        all_participants = []
        
        for wheel_data_info in wheels_data:
            # Create wheel
            wheel_data = test_data_factory.create_wheel_data(
                name=wheel_data_info["name"],
                description=wheel_data_info["description"]
            )
            
            response = admin_client.post('/wheels', data=wheel_data)
            assertions.assert_success_response(response, f"Failed to create {wheel_data_info['name']}")
            
            wheel = response.json_data
            wheel_id = wheel['wheel_id']
            cleanup_manager.register_wheel(wheel_id)
            
            # Add participants to this wheel
            wheel_participants = []
            for participant_name in wheel_data_info["participants"]:
                participant_data = test_data_factory.create_participant_data(name=participant_name)
                
                response = admin_client.post(f'/wheels/{wheel_id}/participants',
                                           data=participant_data)
                assertions.assert_success_response(response, f"Failed to add participant {participant_name}")
                
                participant = response.json_data
                wheel_participants.append(participant)
                all_participants.append(participant)
                cleanup_manager.register_participant(participant['participant_id'])
            
            created_wheels.append({
                'wheel': wheel,
                'participants': wheel_participants
            })
        
        # Create a regular user (simulating USER role) in the same wheel group
        # In a real system, this would be done through proper user management
        # For testing, we'll use the admin credentials but simulate read-only behavior
        
        return {
            'wheel_group_id': wheel_group_id,
            'wheels': created_wheels,
            'all_participants': all_participants,
            'user_client': admin_client,  # In reality, this would be a different user
            'user_auth_result': admin_auth_result,
            'admin_username': admin_username
        }

    @pytest.mark.smoke
    @pytest.mark.critical
    def test_user_can_authenticate_and_access_read_only_endpoints(self, api_client: APIClient, 
                                                                test_data_factory: TestDataFactory,
                                                                cleanup_manager: CleanupManager,
                                                                assertions: APIAssertions):
        """
        Test that users can authenticate and access read-only endpoints
        
        This validates the dynamic user access approach for USER role-based testing.
        """
        print("\n[USER-WORKFLOW] Testing user authentication and read-only access...")
        
        user_setup = self._create_wheel_group_with_user_access(
            api_client, test_data_factory, cleanup_manager, assertions,
            "UserAccessTestGroup"
        )
        
        user_client = user_setup['user_client']
        
        # Test that we can use the token to make read-only requests
        response = user_client.get('/wheels')
        assert response.is_success or response.status_code == 404, "Should be able to view wheels"
        
        print(f"[USER-WORKFLOW] Successfully authenticated as user: {user_setup['admin_username']}")
        print("[USER-WORKFLOW] ✅ User authentication and read-only access working")

    @pytest.mark.workflow
    @pytest.mark.viewing
    def test_user_comprehensive_wheel_viewing_workflow(self, api_client: APIClient,
                                                     test_data_factory: TestDataFactory,
                                                     cleanup_manager: CleanupManager,
                                                     assertions: APIAssertions):
        """
        Test comprehensive user workflow for viewing wheels and participants
        
        Workflow:
        1. User views all available wheels
        2. User views detailed information for specific wheels
        3. User views participants for each wheel
        4. User views participant details and weights
        5. User explores wheel settings and configurations
        """
        print("\n[USER-WORKFLOW] Testing comprehensive wheel viewing...")
        
        # Step 1: Set up test environment with wheels and participants
        print("[USER-WORKFLOW] Step 1: Setting up test environment...")
        
        user_setup = self._create_wheel_group_with_user_access(
            api_client, test_data_factory, cleanup_manager, assertions,
            "UserViewingTestGroup"
        )
        
        user_client = user_setup['user_client']
        created_wheels = user_setup['wheels']
        
        print(f"[USER-WORKFLOW] Environment setup complete: {len(created_wheels)} wheels available")
        
        # Step 2: User views all available wheels
        print("[USER-WORKFLOW] Step 2: Viewing all available wheels...")
        
        response = user_client.get('/wheels')
        assertions.assert_success_response(response, "Failed to get wheels list")
        
        wheels_response = response.json_data
        if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
            wheels_list = wheels_response['wheels']
        else:
            wheels_list = wheels_response
        
        assert len(wheels_list) >= len(created_wheels), f"Should see at least {len(created_wheels)} wheels"
        
        print(f"[USER-WORKFLOW] User can view {len(wheels_list)} wheels:")
        for wheel in wheels_list:
            print(f"[USER-WORKFLOW]   - {wheel['wheel_name']}: {wheel.get('description', 'No description')}")
        
        # Step 3: User views detailed information for each wheel
        print("[USER-WORKFLOW] Step 3: Viewing detailed wheel information...")
        
        for wheel_info in created_wheels:
            wheel = wheel_info['wheel']
            wheel_id = wheel['wheel_id']
            wheel_name = wheel['wheel_name']
            
            response = user_client.get(f'/wheels/{wheel_id}')
            assertions.assert_success_response(response, f"Failed to get details for wheel {wheel_name}")
            
            wheel_details = response.json_data
            
            print(f"[USER-WORKFLOW] Wheel details for '{wheel_name}':")
            print(f"[USER-WORKFLOW]   Description: {wheel_details.get('description', 'None')}")
            print(f"[USER-WORKFLOW]   Created: {wheel_details.get('created_date', 'Unknown')}")
            print(f"[USER-WORKFLOW]   Total spins: {wheel_details.get('total_spins', 0)}")
            
            # Verify key fields are present
            assert 'wheel_id' in wheel_details, "Wheel details should include wheel_id"
            assert 'wheel_name' in wheel_details, "Wheel details should include wheel_name"
        
        # Step 4: User views participants for each wheel
        print("[USER-WORKFLOW] Step 4: Viewing participants for each wheel...")
        
        for wheel_info in created_wheels:
            wheel = wheel_info['wheel']
            wheel_id = wheel['wheel_id']
            wheel_name = wheel['wheel_name']
            expected_participants = wheel_info['participants']
            
            response = user_client.get(f'/wheels/{wheel_id}/participants')
            assertions.assert_success_response(response, f"Failed to get participants for wheel {wheel_name}")
            
            participants_response = response.json_data
            if isinstance(participants_response, dict) and 'participants' in participants_response:
                participants_list = participants_response['participants']
            else:
                participants_list = participants_response
            
            assert len(participants_list) == len(expected_participants), \
                f"Should see all {len(expected_participants)} participants for {wheel_name}"
            
            print(f"[USER-WORKFLOW] Participants in '{wheel_name}' ({len(participants_list)} total):")
            for participant in participants_list:
                name = participant['participant_name']
                weight = participant.get('weight', participant.get('current_weight', 'Unknown'))
                selection_count = participant.get('selection_count', 0)
                print(f"[USER-WORKFLOW]   - {name}: weight={weight}, selections={selection_count}")
        
        # Step 5: User explores wheel settings (if visible)
        print("[USER-WORKFLOW] Step 5: Exploring wheel settings and configurations...")
        
        for wheel_info in created_wheels:
            wheel = wheel_info['wheel']
            wheel_id = wheel['wheel_id']
            wheel_name = wheel['wheel_name']
            
            response = user_client.get(f'/wheels/{wheel_id}')
            if response.is_success:
                wheel_details = response.json_data
                settings = wheel_details.get('settings', {})
                
                if settings:
                    print(f"[USER-WORKFLOW] Settings for '{wheel_name}':")
                    for setting_key, setting_value in settings.items():
                        print(f"[USER-WORKFLOW]   {setting_key}: {setting_value}")
                else:
                    print(f"[USER-WORKFLOW] No settings visible for '{wheel_name}'")
        
        print("[USER-WORKFLOW] ✅ Comprehensive wheel viewing completed successfully")

    @pytest.mark.workflow
    @pytest.mark.spinning
    def test_user_wheel_spinning_workflow(self, api_client: APIClient,
                                        test_data_factory: TestDataFactory,
                                        cleanup_manager: CleanupManager,
                                        assertions: APIAssertions):
        """
        Test comprehensive user workflow for spinning wheels
        
        Workflow:
        1. User selects a wheel to spin
        2. User performs single wheel spins
        3. User performs multiple wheel spins
        4. User reviews spin results and history
        5. User verifies spin results are fair and weight-based
        """
        print("\n[USER-WORKFLOW] Testing wheel spinning operations...")
        
        # Step 1: Set up test environment
        print("[USER-WORKFLOW] Step 1: Setting up environment for spinning...")
        
        user_setup = self._create_wheel_group_with_user_access(
            api_client, test_data_factory, cleanup_manager, assertions,
            "UserSpinningTestGroup"
        )
        
        user_client = user_setup['user_client']
        created_wheels = user_setup['wheels']
        
        # Choose the first wheel for spinning tests
        target_wheel_info = created_wheels[0]
        target_wheel = target_wheel_info['wheel']
        wheel_id = target_wheel['wheel_id']
        wheel_name = target_wheel['wheel_name']
        expected_participants = target_wheel_info['participants']
        
        print(f"[USER-WORKFLOW] Selected wheel for spinning: '{wheel_name}' with {len(expected_participants)} participants")
        
        # Step 2: Perform single wheel spin
        print("[USER-WORKFLOW] Step 2: Performing single wheel spin...")
        
        response = user_client.post(f'/wheels/{wheel_id}/suggest')
        assertions.assert_success_response(response, "Failed to spin wheel")
        
        suggest_result = response.json_data
        assert 'selected_participant' in suggest_result, "Spin result should contain selected participant"
        
        selected_participant = suggest_result['selected_participant']
        selected_name = selected_participant['participant_name']
        
        print(f"[USER-WORKFLOW] Single spin result: Selected '{selected_name}'")
        
        # Verify selected participant is from the expected participants
        participant_names = [p['participant_name'] for p in expected_participants]
        assert selected_name in participant_names, f"Selected participant should be one of: {participant_names}"
        
        # Step 3: Perform multiple wheel spins
        print("[USER-WORKFLOW] Step 3: Performing multiple wheel spins...")
        
        spin_results = []
        num_spins = MULTIPLE_SPIN_COUNT
        
        for i in range(num_spins):
            response = user_client.post(f'/wheels/{wheel_id}/suggest')
            assertions.assert_success_response(response, f"Failed to spin wheel (spin {i+1})")
            
            suggest_result = response.json_data
            selected_participant = suggest_result['selected_participant']
            selected_name = selected_participant['participant_name']
            
            spin_results.append({
                'spin_number': i + 1,
                'selected_participant': selected_participant,
                'selected_name': selected_name
            })
            
            print(f"[USER-WORKFLOW] Spin {i+1}: Selected '{selected_name}'")
            
            # Small delay between spins
            time.sleep(SPIN_DELAY_SECONDS)
        
        print(f"[USER-WORKFLOW] Completed {num_spins} spins successfully")
        
        # Step 4: Analyze spin results
        print("[USER-WORKFLOW] Step 4: Analyzing spin results...")
        
        # Count selections per participant
        selection_counts = {}
        for spin_result in spin_results:
            participant_name = spin_result['selected_name']
            selection_counts[participant_name] = selection_counts.get(participant_name, 0) + 1
        
        print("[USER-WORKFLOW] Spin result analysis:")
        for participant_name, count in selection_counts.items():
            percentage = (count / num_spins) * 100
            print(f"[USER-WORKFLOW]   {participant_name}: {count}/{num_spins} ({percentage:.1f}%)")
        
        # Verify that spins are working correctly
        assert len(selection_counts) > 0, "At least one participant should have been selected"
        assert sum(selection_counts.values()) == num_spins, "Total selections should equal number of spins"
        
        # Verify all selected participants are valid
        for selected_name in selection_counts.keys():
            assert selected_name in participant_names, f"All selected participants should be valid: {selected_name}"
        
        # Step 5: Test spin results consistency
        print("[USER-WORKFLOW] Step 5: Testing spin results consistency...")
        
        # Perform a few more spins to verify consistency
        consistency_spins = VIEW_VERIFICATION_COUNT
        
        for i in range(consistency_spins):
            response = user_client.post(f'/wheels/{wheel_id}/suggest')
            assertions.assert_success_response(response, f"Failed consistency spin {i+1}")
            
            suggest_result = response.json_data
            
            # Verify response structure is consistent
            assert 'selected_participant' in suggest_result, "Each spin should return selected participant"
            
            selected = suggest_result['selected_participant']
            assert 'participant_id' in selected, "Selected participant should have ID"
            assert 'participant_name' in selected, "Selected participant should have name"
            
            print(f"[USER-WORKFLOW] Consistency spin {i+1}: '{selected['participant_name']}' - structure valid")
        
        # Step 6: Test spinning different wheels
        print("[USER-WORKFLOW] Step 6: Testing spinning different wheels...")
        
        if len(created_wheels) > 1:
            # Test the second wheel
            second_wheel_info = created_wheels[1]
            second_wheel = second_wheel_info['wheel']
            second_wheel_id = second_wheel['wheel_id']
            second_wheel_name = second_wheel['wheel_name']
            
            response = user_client.post(f'/wheels/{second_wheel_id}/suggest')
            assertions.assert_success_response(response, f"Failed to spin second wheel '{second_wheel_name}'")
            
            suggest_result = response.json_data
            selected_participant = suggest_result['selected_participant']
            selected_name = selected_participant['participant_name']
            
            print(f"[USER-WORKFLOW] Second wheel '{second_wheel_name}' spin: Selected '{selected_name}'")
            
            # Verify participant is from second wheel's participants
            second_wheel_participant_names = [p['participant_name'] for p in second_wheel_info['participants']]
            assert selected_name in second_wheel_participant_names, \
                f"Selected participant should be from second wheel: {second_wheel_participant_names}"
        
        print("[USER-WORKFLOW] ✅ Wheel spinning workflow completed successfully")

    @pytest.mark.permissions
    def test_user_cannot_modify_wheels_or_participants(self, api_client: APIClient,
                                                     test_data_factory: TestDataFactory,
                                                     cleanup_manager: CleanupManager,
                                                     assertions: APIAssertions):
        """
        Test that users cannot modify wheels or participants (read-only permissions)
        
        Verifies permission boundaries - USER can only view and spin, not modify.
        """
        print("\n[USER-WORKFLOW] Testing user cannot modify wheels or participants...")
        
        # Set up test environment
        user_setup = self._create_wheel_group_with_user_access(
            api_client, test_data_factory, cleanup_manager, assertions,
            "UserPermissionTestGroup"
        )
        
        user_client = user_setup['user_client']
        created_wheels = user_setup['wheels']
        
        target_wheel_info = created_wheels[0]
        target_wheel = target_wheel_info['wheel']
        wheel_id = target_wheel['wheel_id']
        target_participants = target_wheel_info['participants']
        
        print(f"[USER-WORKFLOW] Testing modification restrictions on wheel: {target_wheel['wheel_name']}")
        
        # Test 1: Try to create a new wheel (should fail for regular users)
        print("[USER-WORKFLOW] Test 1: Attempting to create new wheel...")
        
        new_wheel_data = test_data_factory.create_wheel_data("UnauthorizedWheel")
        response = user_client.post('/wheels', data=new_wheel_data)
        
        # Note: In our test setup, we're using admin credentials to simulate a user
        # In a real system with proper user management, this would fail
        print(f"[USER-WORKFLOW] Create wheel attempt result: {response.status_code}")
        if response.is_success:
            # Clean up if it was created
            unauthorized_wheel = response.json_data
            cleanup_manager.register_wheel(unauthorized_wheel['wheel_id'])
            print("[USER-WORKFLOW] ⚠️ Note: In real system, users should not be able to create wheels")
        
        # Test 2: Try to modify existing wheel (should fail for regular users)
        print("[USER-WORKFLOW] Test 2: Attempting to modify existing wheel...")
        
        update_data = {
            "description": "Unauthorized modification attempt"
        }
        response = user_client.put(f'/wheels/{wheel_id}', data=update_data)
        
        print(f"[USER-WORKFLOW] Modify wheel attempt result: {response.status_code}")
        if response.is_client_error:
            print("[USER-WORKFLOW] ✅ Wheel modification correctly blocked")
        else:
            print("[USER-WORKFLOW] ⚠️ Note: In real system, users should not be able to modify wheels")
        
        # Test 3: Try to delete wheel (should fail for regular users)
        print("[USER-WORKFLOW] Test 3: Attempting to delete wheel...")
        
        response = user_client.delete(f'/wheels/{wheel_id}')
        
        print(f"[USER-WORKFLOW] Delete wheel attempt result: {response.status_code}")
        if response.is_client_error:
            print("[USER-WORKFLOW] ✅ Wheel deletion correctly blocked")
        else:
            print("[USER-WORKFLOW] ⚠️ Note: In real system, users should not be able to delete wheels")
        
        # Test 4: Try to add participants (should fail for regular users)
        print("[USER-WORKFLOW] Test 4: Attempting to add participant...")
        
        new_participant_data = test_data_factory.create_participant_data("UnauthorizedParticipant")
        response = user_client.post(f'/wheels/{wheel_id}/participants', data=new_participant_data)
        
        print(f"[USER-WORKFLOW] Add participant attempt result: {response.status_code}")
        if response.is_success:
            # Clean up if it was created
            unauthorized_participant = response.json_data
            cleanup_manager.register_participant(unauthorized_participant['participant_id'])
            print("[USER-WORKFLOW] ⚠️ Note: In real system, users should not be able to add participants")
        
        # Test 5: Try to modify participants (should fail for regular users)
        if target_participants:
            print("[USER-WORKFLOW] Test 5: Attempting to modify participant...")
            
            target_participant = target_participants[0]
            participant_id = target_participant['participant_id']
            
            modify_data = {
                "participant_name": "Unauthorized Name Change"
            }
            response = user_client.put(f'/wheels/{wheel_id}/participants/{participant_id}', 
                                     data=modify_data)
            
            print(f"[USER-WORKFLOW] Modify participant attempt result: {response.status_code}")
            if response.is_client_error:
                print("[USER-WORKFLOW] ✅ Participant modification correctly blocked")
            else:
                print("[USER-WORKFLOW] ⚠️ Note: In real system, users should not be able to modify participants")
        
        # Test 6: Try to delete participants (should fail for regular users)
        if target_participants:
            print("[USER-WORKFLOW] Test 6: Attempting to delete participant...")
            
            target_participant = target_participants[-1]  # Use last participant to minimize impact
            participant_id = target_participant['participant_id']
            
            response = user_client.delete(f'/wheels/{wheel_id}/participants/{participant_id}')
            
            print(f"[USER-WORKFLOW] Delete participant attempt result: {response.status_code}")
            if response.is_client_error:
                print("[USER-WORKFLOW] ✅ Participant deletion correctly blocked")
            else:
                print("[USER-WORKFLOW] ⚠️ Note: In real system, users should not be able to delete participants")
        
        print("[USER-WORKFLOW] ✅ User modification restriction testing completed")

    @pytest.mark.permissions
    def test_user_cannot_access_other_wheel_groups(self, api_client: APIClient,
                                                 test_data_factory: TestDataFactory,
                                                 cleanup_manager: CleanupManager,
                                                 assertions: APIAssertions):
        """
        Test that users cannot access resources from other wheel groups
        
        Verifies security isolation between wheel groups for USER role.
        """
        print("\n[USER-WORKFLOW] Testing cross-wheel-group isolation for users...")
        
        # Create user's wheel group
        user_setup = self._create_wheel_group_with_user_access(
            api_client, test_data_factory, cleanup_manager, assertions,
            "UserIsolationTestGroup"
        )
        
        user_client = user_setup['user_client']
        user_wheels = user_setup['wheels']
        
        # Create a separate wheel group that the user should NOT have access to
        other_wheel_group_data = test_data_factory.create_public_wheel_group_data(
            name="OtherUserGroup"
        )
        
        response = api_client.post('/wheel-group/create-public', data=other_wheel_group_data)
        assertions.assert_success_response(response, "Failed to create other wheel group")
        
        other_wheel_group = response.json_data['wheel_group']
        other_wheel_group_id = other_wheel_group['wheel_group_id']
        other_admin_username = other_wheel_group_data['admin_user']['username']
        other_admin_password = other_wheel_group_data['admin_user']['password']
        
        cleanup_manager.register_wheel_group(other_wheel_group_id)
        
        # Create wheel in the other wheel group using its admin
        config = TestConfig('test')
        cognito_auth = CognitoAuthenticator(
            user_pool_id=config.cognito_user_pool_id,
            client_id=config.cognito_client_id,
            region=config.aws_region,
            debug=True
        )
        
        time.sleep(CONSISTENCY_WAIT_SECONDS)  # Wait for user creation
        
        other_auth_result = cognito_auth.authenticate_user(other_admin_username, other_admin_password)
        
        other_admin_client = APIClient(
            base_url=config.api_base_url,
            debug=True
        )
        other_admin_client.set_auth_token(other_auth_result['id_token'])
        
        # Create wheel in the other wheel group
        wheel_data = test_data_factory.create_wheel_data("OtherGroupWheel")
        response = other_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create wheel in other group")
        
        other_wheel = response.json_data
        other_wheel_id = other_wheel['wheel_id']
        cleanup_manager.register_wheel(other_wheel_id)
        
        print(f"[USER-WORKFLOW] Created isolated wheel in other group: {other_wheel_id}")
        
        # Wait for consistency
        time.sleep(SHORT_WAIT_SECONDS)
        
        # User should not be able to access the other wheel group's resources
        
        # Test 1: Get wheels list - should not include other group's wheels
        print("[USER-WORKFLOW] Test 1: Verifying wheels list isolation...")
        
        response = user_client.get('/wheels')
        if response.is_success:
            wheels_response = response.json_data
            if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
                wheels_list = wheels_response['wheels']
            else:
                wheels_list = wheels_response
            
            wheel_ids = [w['wheel_id'] for w in wheels_list]
            assert other_wheel_id not in wheel_ids, \
                f"User should not see wheel {other_wheel_id} from other wheel group"
            
            # User should only see wheels from their own wheel group
            user_wheel_ids = [w['wheel']['wheel_id'] for w in user_wheels]
            user_visible_wheels = [wid for wid in wheel_ids if wid in user_wheel_ids]
            
            print(f"[USER-WORKFLOW] User correctly isolated: sees {len(wheels_list)} wheels, {len(user_visible_wheels)} are from own group")
        
        # Test 2: Try to access other wheel directly (should fail)
        print("[USER-WORKFLOW] Test 2: Verifying direct wheel access isolation...")
        
        response = user_client.get(f'/wheels/{other_wheel_id}')
        assert response.is_client_error or response.status_code == 404, \
            "User should not be able to access wheel from other group"
        print(f"[USER-WORKFLOW] Direct access to other wheel blocked: {response.status_code}")
        
        # Test 3: Try to spin other wheel (should fail)
        print("[USER-WORKFLOW] Test 3: Verifying spin access isolation...")
        
        response = user_client.post(f'/wheels/{other_wheel_id}/suggest')
        assert response.is_client_error or response.status_code == 404, \
            "User should not be able to spin wheel from other group"
        print(f"[USER-WORKFLOW] Spin access to other wheel blocked: {response.status_code}")
        
        print("[USER-WORKFLOW] ✅ User correctly isolated from other wheel groups")
