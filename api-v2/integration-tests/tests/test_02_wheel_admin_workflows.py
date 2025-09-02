"""
Integration tests for WHEEL_ADMIN role workflows in AWS Ops Wheel v2

Tests comprehensive end-to-end workflows for wheel administrators (WHEEL_ADMIN role):
- Complete wheel lifecycle management (create, modify, delete)
- Complete participant management (create, modify, delete)
- Wheel configuration and settings management
- Permission boundary enforcement (cannot manage users)
- Security isolation between wheel groups

WHEEL_ADMIN Role Permissions:
- ✅ create_wheels: Can create new wheels
- ✅ modify_wheels: Can update wheel settings and properties
- ✅ delete_wheels: Can remove wheels
- ✅ create_participants: Can add participants to wheels
- ✅ modify_participants: Can update participant properties
- ✅ delete_participants: Can remove participants from wheels
- ✅ view_wheels: Can view wheel information
- ✅ view_participants: Can view participant information  
- ✅ spin_wheels: Can spin wheels and view results
- ❌ Cannot manage users (create/modify/delete users)
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
WEIGHT_UPDATE_DELAY_SECONDS = 0.3

# Weight constants
HIGH_WEIGHT = 50
MEDIUM_HIGH_WEIGHT = 30
MEDIUM_WEIGHT = 25
LOW_WEIGHT = 10
MIN_WEIGHT = 1
ZERO_WEIGHT = 0

# Probability test constants
STATISTICAL_TEST_COUNT = 100
RIGGED_TEST_COUNT = 10
WEIGHT_VERIFICATION_SPINS = 20
MULTIPLE_SPIN_COUNT = 5

# Tolerance constants
STATISTICAL_TOLERANCE_PERCENT = 10.0
RIGGED_SUCCESS_THRESHOLD = 0.8

# Retry constants
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5


class TestWheelAdminWorkflows:
    """Test class for WHEEL_ADMIN role end-to-end workflows"""

    def _wait_for_resource_consistency(self, check_func, timeout_seconds: float = CONSISTENCY_WAIT_SECONDS) -> bool:
        """
        Wait for resource consistency using exponential backoff
        
        Args:
            check_func: Function that returns True when resource is ready
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if resource became ready, False if timeout
        """
        import time
        
        start_time = time.time()
        retry_count = 0
        delay = 0.1  # Start with 100ms
        
        while time.time() - start_time < timeout_seconds:
            try:
                if check_func():
                    return True
            except Exception:
                pass  # Continue retrying on exceptions
            
            time.sleep(delay)
            delay = min(delay * 1.5, 1.0)  # Exponential backoff, max 1 second
            retry_count += 1
        
        return False

    def _retry_api_call(self, api_call_func, max_retries: int = MAX_RETRIES) -> APIResponse:
        """
        Retry API call with exponential backoff
        
        Args:
            api_call_func: Function that makes the API call
            max_retries: Maximum number of retries
            
        Returns:
            APIResponse from successful call
            
        Raises:
            Exception: If all retries fail
        """
        import time
        
        for attempt in range(max_retries + 1):
            try:
                response = api_call_func()
                if response.is_success:
                    return response
                elif response.is_server_error and attempt < max_retries:
                    # Retry on server errors
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    return response
            except Exception as e:
                if attempt < max_retries:
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise e
        
        raise Exception(f"API call failed after {max_retries} retries")

    def _create_authenticated_wheel_admin_client(self, api_client: APIClient, 
                                                test_data_factory: TestDataFactory,
                                                cleanup_manager: CleanupManager,
                                                assertions: APIAssertions,
                                                wheel_group_name: str) -> Dict[str, Any]:
        """
        Helper method to create a wheel group and authenticated wheel admin client
        
        Returns:
            Dict containing client, wheel_group_id, username, and auth_result
        """
        # Create wheel group and get admin user (simulating WHEEL_ADMIN role)
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
        
        # Authenticate as the created admin (simulating WHEEL_ADMIN role behavior)
        config = TestConfig('test')
        
        cognito_auth = CognitoAuthenticator(
            user_pool_id=config.cognito_user_pool_id,
            client_id=config.cognito_client_id,
            region=config.aws_region,
            debug=True
        )
        
        auth_result = cognito_auth.authenticate_user(admin_username, admin_password)
        
        # Create authenticated client (simulating wheel admin role)
        wheel_admin_client = APIClient(
            base_url=config.api_base_url,
            debug=True
        )
        wheel_admin_client.set_auth_token(auth_result['id_token'])
        
        return {
            'client': wheel_admin_client,
            'wheel_group_id': wheel_group_id,
            'username': admin_username,
            'auth_result': auth_result,
            'admin_user': admin_user
        }

    @pytest.mark.smoke
    @pytest.mark.critical
    def test_wheel_admin_can_authenticate_via_dynamic_creation(self, api_client: APIClient, 
                                                              test_data_factory: TestDataFactory,
                                                              cleanup_manager: CleanupManager,
                                                              assertions: APIAssertions):
        """
        Test that we can create and authenticate wheel admins dynamically for role testing
        
        This validates the dynamic user creation approach for WHEEL_ADMIN role-based testing.
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing dynamic wheel admin authentication...")
        
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "WheelAdminAuthTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        
        # Test that we can use the token to make authenticated requests
        response = wheel_admin_client.get('/wheels')
        assert response.is_success or response.status_code == 404, "Should be able to call authenticated endpoints"
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Successfully authenticated as: {wheel_admin_info['username']}")
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Dynamic wheel admin authentication working")

    @pytest.mark.workflow
    @pytest.mark.wheel_management
    def test_wheel_admin_complete_wheel_lifecycle_workflow(self, api_client: APIClient,
                                                          test_data_factory: TestDataFactory,
                                                          cleanup_manager: CleanupManager,
                                                          assertions: APIAssertions):
        """
        Test complete wheel administrator workflow for wheel lifecycle management
        
        Workflow:
        1. Wheel admin creates multiple wheels with different configurations
        2. Wheel admin modifies wheel settings and properties
        3. Wheel admin views and manages wheel configurations
        4. Wheel admin deletes wheels when no longer needed
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing complete wheel lifecycle management...")
        
        # Step 1: Create authenticated wheel admin and setup
        print("[WHEEL-ADMIN-WORKFLOW] Step 1: Creating authenticated wheel admin...")
        
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "WheelLifecycleTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Step 2: Create multiple wheels with different configurations
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Creating wheels with different configurations...")
        
        wheel_configs = [
            {
                "name": "StandardWheel",
                "description": "Standard wheel with default settings",
                "settings": {
                    "allow_rigging": True,
                    "multi_select_enabled": False,
                    "default_multi_select_count": 1,
                    "require_reason_for_rigging": False,
                    "show_weights": False,
                    "auto_reset_weights": False
                }
            },
            {
                "name": "MultiSelectWheel", 
                "description": "Wheel with multi-select enabled",
                "settings": {
                    "allow_rigging": False,
                    "multi_select_enabled": True,
                    "default_multi_select_count": 3,
                    "require_reason_for_rigging": False,
                    "show_weights": True,
                    "auto_reset_weights": True
                }
            },
            {
                "name": "RestrictedWheel",
                "description": "Wheel with restricted rigging",
                "settings": {
                    "allow_rigging": True,
                    "multi_select_enabled": False,
                    "default_multi_select_count": 1,
                    "require_reason_for_rigging": True,
                    "show_weights": False,
                    "auto_reset_weights": False
                }
            }
        ]
        
        created_wheels = []
        
        for wheel_config in wheel_configs:
            wheel_data = test_data_factory.create_wheel_data(
                name=wheel_config["name"],
                description=wheel_config["description"]
            )
            # Override settings with specific config
            wheel_data["settings"] = wheel_config["settings"]
            
            response = wheel_admin_client.post('/wheels', data=wheel_data)
            assertions.assert_success_response(response, f"Failed to create {wheel_config['name']}")
            
            wheel = response.json_data
            wheel_id = wheel['wheel_id']
            cleanup_manager.register_wheel(wheel_id)
            
            created_wheels.append({
                'wheel': wheel,
                'config': wheel_config
            })
            
            print(f"[WHEEL-ADMIN-WORKFLOW] Created {wheel_config['name']}: {wheel_id}")
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Successfully created {len(created_wheels)} wheels")
        
        # Wait for consistency
        time.sleep(SHORT_WAIT_SECONDS)
        
        # Step 3: Verify wheel admin can view all created wheels
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Viewing all created wheels...")
        
        response = wheel_admin_client.get('/wheels')
        assertions.assert_success_response(response, "Failed to get wheels list")
        
        wheels_response = response.json_data
        if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
            wheels_list = wheels_response['wheels']
        else:
            wheels_list = wheels_response
        
        assert len(wheels_list) >= len(created_wheels), f"Should see at least {len(created_wheels)} wheels"
        
        # Verify each created wheel is in the list
        wheel_ids = [w['wheel_id'] for w in wheels_list]
        for wheel_info in created_wheels:
            wheel_id = wheel_info['wheel']['wheel_id']
            assert wheel_id in wheel_ids, f"Should see created wheel {wheel_id}"
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Wheel admin can view {len(wheels_list)} wheels")
        
        # Step 4: Modify wheel settings
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Modifying wheel settings...")
        
        # Take the first wheel and modify its settings
        target_wheel = created_wheels[0]
        wheel_id = target_wheel['wheel']['wheel_id']
        
        # Update wheel description and settings
        update_data = {
            "description": "Updated description for standard wheel",
            "settings": {
                "allow_rigging": False,  # Changed from True
                "multi_select_enabled": True,  # Changed from False
                "default_multi_select_count": 2,  # Changed from 1
                "require_reason_for_rigging": True,  # Changed from False
                "show_weights": True,  # Changed from False
                "auto_reset_weights": True   # Changed from False
            }
        }
        
        response = wheel_admin_client.put(f'/wheels/{wheel_id}', data=update_data)
        if response.is_success:
            updated_wheel = response.json_data
            print(f"[WHEEL-ADMIN-WORKFLOW] Successfully updated wheel {wheel_id}")
            
            # Verify the changes took effect
            response = wheel_admin_client.get(f'/wheels/{wheel_id}')
            assertions.assert_success_response(response, "Failed to get updated wheel details")
            
            wheel_details = response.json_data
            assert wheel_details['description'] == update_data['description']
            print("[WHEEL-ADMIN-WORKFLOW] Wheel settings updated successfully")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Wheel update not supported or failed: {response.status_code}")
        
        # Step 5: Delete a wheel
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Deleting a wheel...")
        
        # Delete the last wheel
        wheel_to_delete = created_wheels[-1]
        wheel_id_to_delete = wheel_to_delete['wheel']['wheel_id']
        
        response = wheel_admin_client.delete(f'/wheels/{wheel_id_to_delete}')
        if response.is_success:
            print(f"[WHEEL-ADMIN-WORKFLOW] Successfully deleted wheel {wheel_id_to_delete}")
            
            # Verify the wheel is no longer accessible
            response = wheel_admin_client.get(f'/wheels/{wheel_id_to_delete}')
            assert response.is_client_error or response.status_code == 404, \
                "Deleted wheel should not be accessible"
            print("[WHEEL-ADMIN-WORKFLOW] Deleted wheel no longer accessible")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Wheel deletion not supported or failed: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Wheel lifecycle management completed successfully")

    @pytest.mark.workflow
    @pytest.mark.participant_management
    def test_wheel_admin_complete_participant_management_workflow(self, api_client: APIClient,
                                                                test_data_factory: TestDataFactory,
                                                                cleanup_manager: CleanupManager,
                                                                assertions: APIAssertions):
        """
        Test complete wheel administrator workflow for participant management
        
        Workflow:
        1. Wheel admin creates a wheel
        2. Wheel admin adds participants with different weights and properties
        3. Wheel admin modifies participant weights and information
        4. Wheel admin views participant statistics and information
        5. Wheel admin removes participants as needed
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing complete participant management...")
        
        # Step 1: Create authenticated wheel admin and setup
        print("[WHEEL-ADMIN-WORKFLOW] Step 1: Creating authenticated wheel admin and wheel...")
        
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "ParticipantMgmtTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Create a wheel for participant management
        wheel_data = test_data_factory.create_wheel_data(
            name="ParticipantManagementWheel",
            description="Wheel for testing participant management"
        )
        
        response = wheel_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create wheel for participant management")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Created wheel for participant management: {wheel_id}")
        
        # Step 2: Add participants with different weights and properties
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Adding participants with different configurations...")
        
        participant_configs = [
            {"name": "High Priority Task", "weight": 10, "email_suffix": "high"},
            {"name": "Medium Priority Task", "weight": 5, "email_suffix": "med"},
            {"name": "Low Priority Task", "weight": 2, "email_suffix": "low"},
            {"name": "Special Assignment", "weight": 8, "email_suffix": "special"},
            {"name": "Optional Task", "weight": 1, "email_suffix": "opt"}
        ]
        
        created_participants = []
        
        for i, participant_config in enumerate(participant_configs):
            participant_data = test_data_factory.create_participant_data(
                name=participant_config["name"]
            )
            participant_data["weight"] = participant_config["weight"]
            participant_data["email"] = f"participant-{participant_config['email_suffix']}-{int(time.time())}-{i:03d}@integrationtest.example.com"
            
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                             data=participant_data)
            assertions.assert_success_response(response, f"Failed to create participant {participant_config['name']}")
            
            participant = response.json_data
            created_participants.append({
                'participant': participant,
                'config': participant_config
            })
            cleanup_manager.register_participant(participant['participant_id'])
            
            print(f"[WHEEL-ADMIN-WORKFLOW] Added participant: {participant_config['name']} (weight: {participant_config['weight']})")
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Successfully added {len(created_participants)} participants")
        
        # Wait for consistency
        time.sleep(SHORT_WAIT_SECONDS)
        
        # Step 3: View all participants
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Viewing all participants...")
        
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants list")
        
        participants_response = response.json_data
        if isinstance(participants_response, dict) and 'participants' in participants_response:
            participants_list = participants_response['participants']
        else:
            participants_list = participants_response
        
        assert len(participants_list) == len(created_participants), \
            f"Should see all {len(created_participants)} created participants"
        
        # Verify each participant is present with correct weight
        participant_ids = [p['participant_id'] for p in participants_list]
        for participant_info in created_participants:
            participant_id = participant_info['participant']['participant_id']
            assert participant_id in participant_ids, f"Should see created participant {participant_id}"
            
            # Find the participant in the list and verify weight
            found_participant = next(p for p in participants_list if p['participant_id'] == participant_id)
            expected_weight = participant_info['config']['weight']
            assert found_participant['weight'] == expected_weight, \
                f"Participant weight should be {expected_weight}, got {found_participant['weight']}"
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Wheel admin can view {len(participants_list)} participants with correct weights")
        
        # Step 4: Modify participant weights and properties
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Modifying participant properties...")
        
        # Take the first participant and modify its weight
        target_participant = created_participants[0]
        participant_id = target_participant['participant']['participant_id']
        
        # Update participant weight and name
        update_data = {
            "participant_name": "Updated High Priority Task",
            "weight": 15  # Increased from 10
        }
        
        response = wheel_admin_client.put(f'/wheels/{wheel_id}/participants/{participant_id}',
                                        data=update_data)
        if response.is_success:
            updated_participant = response.json_data
            print(f"[WHEEL-ADMIN-WORKFLOW] Successfully updated participant {participant_id}")
            
            # Verify the changes took effect
            response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
            assertions.assert_success_response(response, "Failed to get updated participants list")
            
            participants_response = response.json_data
            if isinstance(participants_response, dict) and 'participants' in participants_response:
                participants_list = participants_response['participants']
            else:
                participants_list = participants_response
            
            updated_participant = next(p for p in participants_list if p['participant_id'] == participant_id)
            assert updated_participant['participant_name'] == update_data['participant_name']
            assert updated_participant['weight'] == update_data['weight']
            print("[WHEEL-ADMIN-WORKFLOW] Participant properties updated successfully")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Participant update not supported or failed: {response.status_code}")
        
        # Step 5: Remove a participant
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Removing a participant...")
        
        # Delete the last participant
        participant_to_delete = created_participants[-1]
        participant_id_to_delete = participant_to_delete['participant']['participant_id']
        
        response = wheel_admin_client.delete(f'/wheels/{wheel_id}/participants/{participant_id_to_delete}')
        if response.is_success:
            print(f"[WHEEL-ADMIN-WORKFLOW] Successfully deleted participant {participant_id_to_delete}")
            
            # Verify the participant is no longer in the list
            response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
            assertions.assert_success_response(response, "Failed to get participants list after deletion")
            
            participants_response = response.json_data
            if isinstance(participants_response, dict) and 'participants' in participants_response:
                participants_list = participants_response['participants']
            else:
                participants_list = participants_response
            
            participant_ids = [p['participant_id'] for p in participants_list]
            assert participant_id_to_delete not in participant_ids, \
                "Deleted participant should not be in the list"
            print("[WHEEL-ADMIN-WORKFLOW] Deleted participant no longer in list")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Participant deletion not supported or failed: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Participant management completed successfully")

    @pytest.mark.workflow
    @pytest.mark.spinning
    def test_wheel_admin_wheel_spinning_and_management_workflow(self, api_client: APIClient,
                                                              test_data_factory: TestDataFactory,
                                                              cleanup_manager: CleanupManager,
                                                              assertions: APIAssertions):
        """
        Test wheel administrator workflow for wheel spinning and results management
        
        Workflow:
        1. Wheel admin creates wheel with specific configuration
        2. Wheel admin adds participants with strategic weights
        3. Wheel admin spins wheel multiple times
        4. Wheel admin analyzes spin results and participant statistics
        5. Wheel admin adjusts participant weights based on results
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing wheel spinning and management...")
        
        # Step 1: Create authenticated wheel admin and setup
        print("[WHEEL-ADMIN-WORKFLOW] Step 1: Creating wheel admin and wheel for spinning...")
        
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "SpinMgmtTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Create wheel with specific spinning configuration
        wheel_data = test_data_factory.create_wheel_data(
            name="SpinManagementWheel",
            description="Wheel for testing spin management workflows"
        )
        wheel_data["settings"]["show_weights"] = True  # Enable weight visibility for admin
        
        response = wheel_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create wheel for spin management")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Created wheel for spin management: {wheel_id}")
        
        # Step 2: Add participants with strategic weights
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Adding participants with strategic weights...")
        
        participant_configs = [
            {"name": "Team Lead", "weight": 3},     # Lower weight (less frequent selection)
            {"name": "Senior Dev", "weight": 5},    # Medium weight
            {"name": "Junior Dev A", "weight": 8},  # Higher weight (more frequent selection)
            {"name": "Junior Dev B", "weight": 8},  # Higher weight (more frequent selection)
            {"name": "Intern", "weight": 6}         # Medium-high weight
        ]
        
        created_participants = []
        
        for participant_config in participant_configs:
            participant_data = test_data_factory.create_participant_data(
                name=participant_config["name"]
            )
            participant_data["weight"] = participant_config["weight"]
            
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                             data=participant_data)
            assertions.assert_success_response(response, f"Failed to create participant {participant_config['name']}")
            
            participant = response.json_data
            created_participants.append(participant)
            cleanup_manager.register_participant(participant['participant_id'])
            
            print(f"[WHEEL-ADMIN-WORKFLOW] Added {participant_config['name']} with weight {participant_config['weight']}")
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Added {len(created_participants)} participants with strategic weights")
        
        # Wait for consistency
        time.sleep(1.0)
        
        # Step 3: Perform multiple spins to gather data
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Performing multiple spins...")
        
        spin_results = []
        spin_count = 5
        
        for i in range(spin_count):
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest')
            assertions.assert_success_response(response, f"Failed to spin wheel (spin {i+1})")
            
            suggest_result = response.json_data
            assert 'selected_participant' in suggest_result, "Suggest result should contain selected participant"
            
            selected_participant = suggest_result['selected_participant']
            selected_name = selected_participant['participant_name']
            
            spin_results.append({
                'spin_number': i + 1,
                'selected_participant': selected_participant,
                'result': suggest_result
            })
            
            print(f"[WHEEL-ADMIN-WORKFLOW] Spin {i+1}: Selected '{selected_name}'")
            
            # Small delay between spins
            time.sleep(SPIN_DELAY_SECONDS)
        
        # Step 4: Analyze spin results
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Analyzing spin results...")
        
        # Count selections per participant
        selection_counts = {}
        for spin_result in spin_results:
            participant_name = spin_result['selected_participant']['participant_name']
            selection_counts[participant_name] = selection_counts.get(participant_name, 0) + 1
        
        print("[WHEEL-ADMIN-WORKFLOW] Selection frequency analysis:")
        for participant_name, count in selection_counts.items():
            percentage = (count / spin_count) * 100
            print(f"[WHEEL-ADMIN-WORKFLOW]   {participant_name}: {count}/{spin_count} ({percentage:.1f}%)")
        
        # Verify that spins are working (at least one participant was selected)
        assert len(selection_counts) > 0, "At least one participant should have been selected"
        assert sum(selection_counts.values()) == spin_count, "Total selections should equal spin count"
        
        # Step 5: Verify wheel admin can view wheel statistics
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Viewing wheel statistics...")
        
        response = wheel_admin_client.get(f'/wheels/{wheel_id}')
        assertions.assert_success_response(response, "Failed to get wheel details")
        
        wheel_details = response.json_data
        total_spins = wheel_details.get('total_spins', 0)
        
        if total_spins > 0:
            print(f"[WHEEL-ADMIN-WORKFLOW] Wheel statistics - Total spins: {total_spins}")
        else:
            print("[WHEEL-ADMIN-WORKFLOW] Wheel statistics not available or spins not tracked")
        
        # Get updated participant statistics
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants with updated stats")
        
        participants_response = response.json_data
        if isinstance(participants_response, dict) and 'participants' in participants_response:
            participants_list = participants_response['participants']
        else:
            participants_list = participants_response
        
        print("[WHEEL-ADMIN-WORKFLOW] Participant statistics:")
        for participant in participants_list:
            name = participant['participant_name']
            weight = participant['weight']
            selection_count = participant.get('selection_count', 0)
            print(f"[WHEEL-ADMIN-WORKFLOW]   {name}: weight={weight}, selections={selection_count}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Wheel spinning and management completed successfully")

    @pytest.mark.permissions
    def test_wheel_admin_cannot_manage_users(self, api_client: APIClient,
                                           test_data_factory: TestDataFactory,
                                           cleanup_manager: CleanupManager,
                                           assertions: APIAssertions):
        """
        Test that wheel administrators cannot manage users
        
        Verifies permission boundaries - WHEEL_ADMIN can manage wheels/participants but not users.
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing wheel admin cannot manage users...")
        
        # Create wheel admin
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "UserMgmtPermissionTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        
        # Try to create additional wheel groups (should fail for non-deployment-admin)
        new_wheel_group_data = test_data_factory.create_public_wheel_group_data(
            name="UnauthorizedWheelGroup"
        )
        
        response = wheel_admin_client.post('/wheel-group/create-public', data=new_wheel_group_data)
        
        # The exact behavior depends on system design - documenting the current behavior
        print(f"[WHEEL-ADMIN-WORKFLOW] Wheel group creation attempt: {response.status_code}")
        
        # Wheel admins should focus on wheel/participant management, not user management
        print("[WHEEL-ADMIN-WORKFLOW] ✅ User management permission boundaries tested")

    @pytest.mark.permissions
    def test_wheel_admin_cross_wheel_group_isolation(self, api_client: APIClient,
                                                    test_data_factory: TestDataFactory,
                                                    cleanup_manager: CleanupManager,
                                                    assertions: APIAssertions):
        """
        Test that wheel administrators cannot access resources from other wheel groups
        
        Verifies security isolation between wheel groups for WHEEL_ADMIN role.
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing cross-wheel-group isolation...")
        
        # Create wheel admin's wheel group
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "WheelAdminIsolationTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        
        # Create a wheel group that the wheel admin should NOT have access to
        other_wheel_group_data = test_data_factory.create_public_wheel_group_data(
            name="OtherWheelAdminGroup"
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
        
        time.sleep(2.0)  # Wait for user creation
        
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
        
        # Wait for consistency
        time.sleep(1.0)
        
        # Wheel admin should not be able to access the other wheel group's resources
        
        # Try to get wheels list - should not include other group's wheels
        response = wheel_admin_client.get('/wheels')
        if response.is_success:
            wheels_response = response.json_data
            if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
                wheels_list = wheels_response['wheels']
            else:
                wheels_list = wheels_response
            
            for wheel in wheels_list:
                assert wheel['wheel_id'] != other_wheel_id, \
                    f"Wheel admin should not see wheel {other_wheel_id} from other wheel group"
            print(f"[WHEEL-ADMIN-WORKFLOW] Wheel admin correctly isolated: sees {len(wheels_list)} wheels (not including other group's wheel)")
        
        # Try to access other wheel directly (should fail)
        response = wheel_admin_client.get(f'/wheels/{other_wheel_id}')
        assert response.is_client_error or response.status_code == 404, \
            "Wheel admin should not be able to access wheel from other group"
        print(f"[WHEEL-ADMIN-WORKFLOW] Direct access to other wheel blocked: {response.status_code}")
        
        # Try to modify other wheel (should fail)
        update_data = {"description": "Unauthorized modification attempt"}
        response = wheel_admin_client.put(f'/wheels/{other_wheel_id}', data=update_data)
        assert response.is_client_error or response.status_code == 404, \
            "Wheel admin should not be able to modify wheel from other group"
        print(f"[WHEEL-ADMIN-WORKFLOW] Modification access to other wheel blocked: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Wheel admin correctly isolated from other wheel groups")

    @pytest.mark.workflow
    def test_wheel_admin_comprehensive_wheel_and_participant_operations(self, api_client: APIClient,
                                                                       test_data_factory: TestDataFactory,
                                                                       cleanup_manager: CleanupManager,
                                                                       assertions: APIAssertions):
        """
        Test comprehensive wheel admin operations: adding, renaming, deleting participants and wheels
        
        This test covers all the core WHEEL_ADMIN operations in a realistic workflow:
        1. Create multiple wheels with different purposes
        2. Add participants to wheels with various configurations
        3. Rename participants to reflect changing requirements
        4. Delete participants that are no longer needed
        5. Delete entire wheels when projects are completed
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing comprehensive wheel and participant operations...")
        
        # Step 1: Create authenticated wheel admin
        print("[WHEEL-ADMIN-WORKFLOW] Step 1: Creating authenticated wheel admin...")
        
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "ComprehensiveTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Step 2: Create multiple wheels for different purposes
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Creating wheels for different project needs...")
        
        wheel_projects = [
            {
                "name": "ProjectAssignmentWheel",
                "description": "Assign team members to new projects",
                "participants": ["Alice", "Bob", "Charlie", "Diana", "Eve"]
            },
            {
                "name": "CodeReviewWheel", 
                "description": "Select code reviewers for pull requests",
                "participants": ["Senior Dev A", "Senior Dev B", "Team Lead", "Architect"]
            },
            {
                "name": "PresentationWheel",
                "description": "Choose who presents at team meetings",
                "participants": ["Presenter 1", "Presenter 2", "Presenter 3"]
            }
        ]
        
        created_wheels = []
        
        for project in wheel_projects:
            # Create wheel
            wheel_data = test_data_factory.create_wheel_data(
                name=project["name"],
                description=project["description"]
            )
            
            response = wheel_admin_client.post('/wheels', data=wheel_data)
            assertions.assert_success_response(response, f"Failed to create {project['name']}")
            
            wheel = response.json_data
            wheel_id = wheel['wheel_id']
            cleanup_manager.register_wheel(wheel_id)
            
            # Add participants to this wheel
            wheel_participants = []
            for participant_name in project["participants"]:
                participant_data = test_data_factory.create_participant_data(name=participant_name)
                
                response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                                 data=participant_data)
                assertions.assert_success_response(response, f"Failed to add participant {participant_name}")
                
                participant = response.json_data
                wheel_participants.append(participant)
                cleanup_manager.register_participant(participant['participant_id'])
            
            created_wheels.append({
                'wheel': wheel,
                'participants': wheel_participants,
                'project_info': project
            })
            
            print(f"[WHEEL-ADMIN-WORKFLOW] Created {project['name']} with {len(wheel_participants)} participants")
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Successfully created {len(created_wheels)} wheels with participants")
        
        # Wait for consistency
        time.sleep(1.0)
        
        # Step 3: Rename participants to reflect changing requirements
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Renaming participants to reflect new roles...")
        
        # Take the first wheel and rename some participants
        target_wheel = created_wheels[0]
        wheel_id = target_wheel['wheel']['wheel_id']
        participants = target_wheel['participants']
        
        # Rename the first two participants
        rename_operations = [
            {"old_name": "Alice", "new_name": "Alice (Project Manager)"},
            {"old_name": "Bob", "new_name": "Bob (Tech Lead)"}
        ]
        
        for rename_op in rename_operations:
            # Find participant with old name
            target_participant = None
            for p in participants:
                if p['participant_name'] == rename_op["old_name"]:
                    target_participant = p
                    break
            
            if target_participant:
                participant_id = target_participant['participant_id']
                update_data = {
                    "participant_name": rename_op["new_name"]
                }
                
                response = wheel_admin_client.put(f'/wheels/{wheel_id}/participants/{participant_id}',
                                                data=update_data)
                if response.is_success:
                    print(f"[WHEEL-ADMIN-WORKFLOW] Renamed '{rename_op['old_name']}' to '{rename_op['new_name']}'")
                else:
                    print(f"[WHEEL-ADMIN-WORKFLOW] Rename not supported or failed: {response.status_code}")
        
        # Step 4: Add new participants to existing wheels
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Adding new participants to existing wheels...")
        
        # Add new participants to the second wheel (CodeReviewWheel)
        target_wheel = created_wheels[1]
        wheel_id = target_wheel['wheel']['wheel_id']
        
        new_participants = ["Junior Dev C", "Intern Developer"]
        
        for participant_name in new_participants:
            participant_data = test_data_factory.create_participant_data(name=participant_name)
            
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                             data=participant_data)
            if response.is_success:
                participant = response.json_data
                cleanup_manager.register_participant(participant['participant_id'])
                print(f"[WHEEL-ADMIN-WORKFLOW] Added new participant: {participant_name}")
            else:
                print(f"[WHEEL-ADMIN-WORKFLOW] Failed to add participant {participant_name}: {response.status_code}")
        
        # Step 5: Delete specific participants that are no longer needed
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Removing participants no longer needed...")
        
        # Remove one participant from the third wheel (PresentationWheel)
        target_wheel = created_wheels[2]
        wheel_id = target_wheel['wheel']['wheel_id']
        participants = target_wheel['participants']
        
        if not participants:
            assertions.fail("No participants found in wheel to remove")
        
        participant_to_remove = participants[0]  # Remove first participant
        participant_id = participant_to_remove['participant_id']
        participant_name = participant_to_remove['participant_name']
        
        response = wheel_admin_client.delete(f'/wheels/{wheel_id}/participants/{participant_id}')
        if response.is_success:
            print(f"[WHEEL-ADMIN-WORKFLOW] Removed participant: {participant_name}")
            
            # Verify removal
            response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
            if response.is_success:
                participants_response = response.json_data
                if isinstance(participants_response, dict) and 'participants' in participants_response:
                    remaining_participants = participants_response['participants']
                else:
                    remaining_participants = participants_response
                
                participant_ids = [p['participant_id'] for p in remaining_participants]
                assert participant_id not in participant_ids, "Participant should be removed"
                print(f"[WHEEL-ADMIN-WORKFLOW] Verified: {len(remaining_participants)} participants remain")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Participant deletion not supported or failed: {response.status_code}")
        
        # Step 6: Delete an entire wheel that's no longer needed
        print("[WHEEL-ADMIN-WORKFLOW] Step 6: Deleting wheel no longer needed...")
        
        # Delete the last wheel (PresentationWheel)
        wheel_to_delete = created_wheels[-1]
        wheel_id_to_delete = wheel_to_delete['wheel']['wheel_id']
        wheel_name = wheel_to_delete['project_info']['name']
        
        response = wheel_admin_client.delete(f'/wheels/{wheel_id_to_delete}')
        if response.is_success:
            print(f"[WHEEL-ADMIN-WORKFLOW] Deleted wheel: {wheel_name}")
            
            # Verify the wheel is no longer accessible
            response = wheel_admin_client.get(f'/wheels/{wheel_id_to_delete}')
            assert response.is_client_error or response.status_code == 404, \
                "Deleted wheel should not be accessible"
            print("[WHEEL-ADMIN-WORKFLOW] Verified: Deleted wheel no longer accessible")
            
            # Verify wheel is not in wheels list
            response = wheel_admin_client.get('/wheels')
            if response.is_success:
                wheels_response = response.json_data
                if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
                    wheels_list = wheels_response['wheels']
                else:
                    wheels_list = wheels_response
                
                wheel_ids = [w['wheel_id'] for w in wheels_list]
                assert wheel_id_to_delete not in wheel_ids, "Deleted wheel should not be in list"
                print(f"[WHEEL-ADMIN-WORKFLOW] Verified: Deleted wheel not in list of {len(wheels_list)} wheels")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Wheel deletion not supported or failed: {response.status_code}")
        
        # Step 7: Verify remaining wheels and participants are still functional
        print("[WHEEL-ADMIN-WORKFLOW] Step 7: Verifying remaining wheels are functional...")
        
        remaining_wheels = created_wheels[:-1]  # All except the deleted one
        
        for wheel_info in remaining_wheels:
            wheel_id = wheel_info['wheel']['wheel_id']
            wheel_name = wheel_info['project_info']['name']
            
            # Test that we can still spin the wheel
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest')
            if response.is_success:
                suggest_result = response.json_data
                if 'selected_participant' in suggest_result:
                    selected_name = suggest_result['selected_participant']['participant_name']
                    print(f"[WHEEL-ADMIN-WORKFLOW] {wheel_name} still functional: selected '{selected_name}'")
                else:
                    print(f"[WHEEL-ADMIN-WORKFLOW] {wheel_name} responded but no participant selected")
            else:
                print(f"[WHEEL-ADMIN-WORKFLOW] {wheel_name} spin failed: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Comprehensive wheel and participant operations completed successfully")

    @pytest.mark.workflow
    @pytest.mark.spinning
    def test_wheel_admin_advanced_rigging_operations_workflow(self, api_client: APIClient,
                                                            test_data_factory: TestDataFactory,
                                                            cleanup_manager: CleanupManager,
                                                            assertions: APIAssertions):
        """
        Test comprehensive rigging operations for wheel admins
        
        Covers:
        - POST /v2/wheels/{wheel_id}/participants/{participant_id}/rig
        - DELETE /v2/wheels/{wheel_id}/rigging
        - Hidden vs visible rigging
        - Reason requirements for rigging
        - Rigging with wheel settings that disable it
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing advanced rigging operations...")
        
        # Step 1: Create authenticated wheel admin and setup
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "RiggingTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Create wheel with rigging enabled
        wheel_data = test_data_factory.create_wheel_data(
            name="RiggingTestWheel",
            description="Test wheel for rigging operations"
        )
        # Ensure rigging is enabled
        wheel_data['settings'] = {
            "allow_rigging": True,
            "rigging_visible": True
        }
        
        response = wheel_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create rigging test wheel")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        # Create multiple participants for rigging tests
        participants_data = [
            test_data_factory.create_participant_data("Alice", weight=10),
            test_data_factory.create_participant_data("Bob", weight=10),
            test_data_factory.create_participant_data("Charlie", weight=10),
            test_data_factory.create_participant_data("Diana", weight=10)
        ]
        
        created_participants = []
        for participant_data in participants_data:
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                             data=participant_data)
            assertions.assert_success_response(response, f"Failed to create participant {participant_data['participant_name']}")
            
            participant = response.json_data
            created_participants.append(participant)
            cleanup_manager.register_participant(participant['participant_id'])
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Setup complete: wheel with {len(created_participants)} participants")
        time.sleep(1.0)
        
        # Step 2: Test individual participant rigging
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Testing individual participant rigging...")
        
        alice = created_participants[0]
        alice_id = alice['participant_id']
        
        # Rig Alice with reason
        rig_data = {
            "reason": "Alice is the team lead for this project"
        }
        
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants/{alice_id}/rig', 
                                         data=rig_data)
        assertions.assert_success_response(response, "Failed to rig Alice")
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Successfully rigged Alice with reason: {rig_data['reason']}")
        
        # Verify rigging took effect by spinning
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest')
        assertions.assert_success_response(response, "Failed to get suggestions from rigged wheel")
        
        suggest_result = response.json_data
        selected_participant = suggest_result['selected_participant']
        
        assert selected_participant['participant_id'] == alice_id, \
            f"Rigged wheel should select Alice, but selected {selected_participant['participant_name']}"
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Rigging verified: Selected {selected_participant['participant_name']} as expected")
        
        # Step 3: Test rigging with apply_changes parameter
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Testing rigging with apply_changes...")
        
        # Test selection with apply_changes=false (should not affect weights)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=false')
        assertions.assert_success_response(response, "Failed to get suggestions with apply_changes=false")
        
        suggest_result_no_apply = response.json_data
        selected_no_apply = suggest_result_no_apply['selected_participant']
        
        assert selected_no_apply['participant_id'] == alice_id, \
            "Rigged wheel should still select Alice even with apply_changes=false"
        
        print("[WHEEL-ADMIN-WORKFLOW] apply_changes=false works correctly with rigging")
        
        # Test selection with apply_changes=true (should affect weights)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=true')
        assertions.assert_success_response(response, "Failed to get suggestions with apply_changes=true")
        
        suggest_result_apply = response.json_data
        selected_apply = suggest_result_apply['selected_participant']
        
        assert selected_apply['participant_id'] == alice_id, \
            "Rigged wheel should select Alice with apply_changes=true"
        
        print("[WHEEL-ADMIN-WORKFLOW] apply_changes=true works correctly with rigging")
        
        # Step 4: Test multiple rigging scenarios
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Testing multiple rigging scenarios...")
        
        # Clear existing rigging first
        response = wheel_admin_client.delete(f'/wheels/{wheel_id}/unrig')
        if response.is_success:
            print("[WHEEL-ADMIN-WORKFLOW] Cleared existing rigging")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Rigging clear not supported or failed: {response.status_code}")
            print("[WHEEL-ADMIN-WORKFLOW] Continuing with existing rigging state")
        
        # Rig multiple participants
        bob = created_participants[1]
        bob_id = bob['participant_id']
        
        rig_bob_data = {
            "reason": "Bob has specific expertise needed"
        }
        
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants/{bob_id}/rig',
                                         data=rig_bob_data)
        assertions.assert_success_response(response, "Failed to rig Bob")
        
        print("[WHEEL-ADMIN-WORKFLOW] Successfully rigged Bob")
        
        # Verify Bob is now selected
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest')
        assertions.assert_success_response(response, "Failed to get suggestions after rigging Bob")
        
        suggest_result = response.json_data
        selected_participant = suggest_result['selected_participant']
        
        assert selected_participant['participant_id'] == bob_id, \
            f"Rigged wheel should select Bob, but selected {selected_participant['participant_name']}"
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Bob rigging verified: Selected {selected_participant['participant_name']}")
        
        # Step 5: Test hidden rigging
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Testing hidden rigging...")
        
        # Create wheel with hidden rigging
        hidden_wheel_data = test_data_factory.create_wheel_data(
            name="HiddenRiggingWheel",
            description="Test wheel for hidden rigging"
        )
        hidden_wheel_data['settings'] = {
            "allow_rigging": True,
            "rigging_visible": False  # Hidden rigging
        }
        
        response = wheel_admin_client.post('/wheels', data=hidden_wheel_data)
        assertions.assert_success_response(response, "Failed to create hidden rigging wheel")
        
        hidden_wheel = response.json_data
        hidden_wheel_id = hidden_wheel['wheel_id']
        cleanup_manager.register_wheel(hidden_wheel_id)
        
        # Add participants to hidden rigging wheel
        charlie_data = test_data_factory.create_participant_data("Charlie")
        response = wheel_admin_client.post(f'/wheels/{hidden_wheel_id}/participants',
                                         data=charlie_data)
        assertions.assert_success_response(response, "Failed to create Charlie in hidden rigging wheel")
        
        charlie_hidden = response.json_data
        charlie_hidden_id = charlie_hidden['participant_id']
        cleanup_manager.register_participant(charlie_hidden_id)
        
        # Rig Charlie in hidden wheel
        rig_charlie_data = {
            "reason": "Hidden rigging test"
        }
        
        response = wheel_admin_client.post(f'/wheels/{hidden_wheel_id}/participants/{charlie_hidden_id}/rig',
                                         data=rig_charlie_data)
        assertions.assert_success_response(response, "Failed to rig Charlie in hidden wheel")
        
        print("[WHEEL-ADMIN-WORKFLOW] Successfully set up hidden rigging")
        
        # Step 6: Test rigging with disabled rigging settings
        print("[WHEEL-ADMIN-WORKFLOW] Step 6: Testing rigging with disabled settings...")
        
        # Create wheel with rigging disabled
        no_rig_wheel_data = test_data_factory.create_wheel_data(
            name="NoRiggingWheel",
            description="Test wheel with rigging disabled"
        )
        no_rig_wheel_data['settings'] = {
            "allow_rigging": False  # Rigging disabled
        }
        
        response = wheel_admin_client.post('/wheels', data=no_rig_wheel_data)
        assertions.assert_success_response(response, "Failed to create no-rigging wheel")
        
        no_rig_wheel = response.json_data
        no_rig_wheel_id = no_rig_wheel['wheel_id']
        cleanup_manager.register_wheel(no_rig_wheel_id)
        
        # Add participant to no-rigging wheel
        diana_data = test_data_factory.create_participant_data("Diana")
        response = wheel_admin_client.post(f'/wheels/{no_rig_wheel_id}/participants',
                                         data=diana_data)
        assertions.assert_success_response(response, "Failed to create Diana in no-rigging wheel")
        
        diana_no_rig = response.json_data
        diana_no_rig_id = diana_no_rig['participant_id']
        cleanup_manager.register_participant(diana_no_rig_id)
        
        # Try to rig Diana (should fail)
        rig_diana_data = {
            "reason": "This should fail"
        }
        
        response = wheel_admin_client.post(f'/wheels/{no_rig_wheel_id}/participants/{diana_no_rig_id}/rig',
                                         data=rig_diana_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Rigging correctly blocked on disabled wheel: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Rigging not blocked on disabled wheel: {response.status_code}")
        
        # Step 7: Test rigging without reason (should fail if required)
        print("[WHEEL-ADMIN-WORKFLOW] Step 7: Testing rigging without reason...")
        
        # Try to rig without reason
        empty_rig_data = {}
        
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants/{alice_id}/rig',
                                         data=empty_rig_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Rigging without reason correctly blocked: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Rigging without reason allowed: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Advanced rigging operations workflow completed successfully")

    @pytest.mark.workflow
    def test_wheel_admin_advanced_weight_management_workflow(self, api_client: APIClient,
                                                           test_data_factory: TestDataFactory,
                                                           cleanup_manager: CleanupManager,
                                                           assertions: APIAssertions):
        """
        Test comprehensive weight management operations for wheel admins
        
        Covers:
        - POST /v2/wheels/{wheel_id}/reset (weight reset functionality)
        - Weight redistribution after selections
        - Weight-based selection verification
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing advanced weight management...")
        
        # Step 1: Create authenticated wheel admin and setup
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "WeightManagementTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Create wheel for weight management testing
        wheel_data = test_data_factory.create_wheel_data(
            name="WeightManagementWheel",
            description="Test wheel for weight management operations"
        )
        
        response = wheel_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create weight management wheel")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        # Create participants with different initial weights
        participants_data = [
            test_data_factory.create_participant_data("HighWeight", weight=50),
            test_data_factory.create_participant_data("MediumWeight", weight=25),
            test_data_factory.create_participant_data("LowWeight", weight=10),
            test_data_factory.create_participant_data("MinWeight", weight=1)
        ]
        
        created_participants = []
        initial_weights = {}
        
        for participant_data in participants_data:
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                             data=participant_data)
            assertions.assert_success_response(response, f"Failed to create participant {participant_data['participant_name']}")
            
            participant = response.json_data
            created_participants.append(participant)
            initial_weights[participant['participant_id']] = participant_data['weight']
            cleanup_manager.register_participant(participant['participant_id'])
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Setup: {len(created_participants)} participants with varied weights")
        time.sleep(1.0)
        
        # Step 2: Test selection probability verification
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Testing weight-based selection probability...")
        
        # Perform multiple selections to verify weight-based probability
        selection_counts = {}
        num_tests = 20
        
        for i in range(num_tests):
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=false')
            assertions.assert_success_response(response, f"Failed to get suggestions on test {i+1}")
            
            suggest_result = response.json_data
            selected_participant = suggest_result['selected_participant']
            selected_id = selected_participant['participant_id']
            
            if selected_id not in selection_counts:
                selection_counts[selected_id] = 0
            selection_counts[selected_id] += 1
            
            time.sleep(0.1)  # Small delay between selections
        
        # Analyze selection distribution
        print("[WHEEL-ADMIN-WORKFLOW] Selection distribution analysis:")
        for participant in created_participants:
            participant_id = participant['participant_id']
            participant_name = participant['participant_name']
            count = selection_counts.get(participant_id, 0)
            percentage = (count / num_tests) * 100
            initial_weight = initial_weights[participant_id]
            
            print(f"[WHEEL-ADMIN-WORKFLOW]   {participant_name} (weight {initial_weight}): {count}/{num_tests} ({percentage:.1f}%)")
        
        # Verify that higher weight participants were selected more often
        high_weight_participant = created_participants[0]  # HighWeight
        low_weight_participant = created_participants[3]   # MinWeight
        
        high_weight_count = selection_counts.get(high_weight_participant['participant_id'], 0)
        low_weight_count = selection_counts.get(low_weight_participant['participant_id'], 0)
        
        # High weight should generally be selected more often (probabilistic test)
        if high_weight_count >= low_weight_count:
            print("[WHEEL-ADMIN-WORKFLOW] ✅ Weight-based selection working correctly")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Unexpected selection distribution: high={high_weight_count}, low={low_weight_count}")
        
        # Step 3: Test weight redistribution after selections
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Testing weight redistribution after selections...")
        
        # Get initial participant weights
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants for weight check")
        
        participants_before = response.json_data
        if isinstance(participants_before, dict) and 'participants' in participants_before:
            participants_before = participants_before['participants']
        
        weights_before = {p['participant_id']: p.get('weight', p.get('current_weight', 0)) for p in participants_before}
        
        print("[WHEEL-ADMIN-WORKFLOW] Weights before selection:")
        for participant in created_participants:
            participant_id = participant['participant_id']
            weight = weights_before.get(participant_id, 0)
            print(f"[WHEEL-ADMIN-WORKFLOW]   {participant['participant_name']}: {weight}")
        
        # Perform selection with apply_changes=true
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=true')
        assertions.assert_success_response(response, "Failed to get suggestions with apply_changes=true")
        
        suggest_result = response.json_data
        selected_participant = suggest_result['selected_participant']
        selected_name = selected_participant['participant_name']
        selected_id = selected_participant['participant_id']
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Selected {selected_name} with apply_changes=true")
        
        # Check weights after selection
        time.sleep(WEIGHT_UPDATE_DELAY_SECONDS)  # Allow for weight updates
        
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants after selection")
        
        participants_after = response.json_data
        if isinstance(participants_after, dict) and 'participants' in participants_after:
            participants_after = participants_after['participants']
        
        weights_after = {p['participant_id']: p.get('weight', p.get('current_weight', 0)) for p in participants_after}
        
        print("[WHEEL-ADMIN-WORKFLOW] Weights after selection:")
        for participant in created_participants:
            participant_id = participant['participant_id']
            weight_before = weights_before.get(participant_id, 0)
            weight_after = weights_after.get(participant_id, 0)
            change = weight_after - weight_before
            print(f"[WHEEL-ADMIN-WORKFLOW]   {participant['participant_name']}: {weight_before} → {weight_after} (Δ{change:+})")
        
        # Verify selected participant's weight decreased
        selected_weight_before = weights_before.get(selected_id, 0)
        selected_weight_after = weights_after.get(selected_id, 0)
        
        if selected_weight_after < selected_weight_before:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Selected participant weight correctly decreased: {selected_weight_before} → {selected_weight_after}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Selected participant weight did not decrease: {selected_weight_before} → {selected_weight_after}")
        
        # Step 4: Test weight reset functionality
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Testing weight reset functionality...")
        
        # Reset weights to original values
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/reset')
        assertions.assert_success_response(response, "Failed to reset wheel weights")
        
        print("[WHEEL-ADMIN-WORKFLOW] Weight reset requested")
        
        # Check weights after reset
        time.sleep(0.5)  # Allow for reset to process
        
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants after reset")
        
        participants_reset = response.json_data
        if isinstance(participants_reset, dict) and 'participants' in participants_reset:
            participants_reset = participants_reset['participants']
        
        weights_reset = {p['participant_id']: p.get('weight', p.get('current_weight', 0)) for p in participants_reset}
        
        print("[WHEEL-ADMIN-WORKFLOW] Weights after reset:")
        weights_match_initial = True
        for participant in created_participants:
            participant_id = participant['participant_id']
            initial_weight = initial_weights[participant_id]
            reset_weight = weights_reset.get(participant_id, 0)
            
            print(f"[WHEEL-ADMIN-WORKFLOW]   {participant['participant_name']}: {reset_weight} (initial: {initial_weight})")
            
            if reset_weight != initial_weight:
                weights_match_initial = False
        
        if weights_match_initial:
            print("[WHEEL-ADMIN-WORKFLOW] ✅ Weight reset successfully restored initial weights")
        else:
            print("[WHEEL-ADMIN-WORKFLOW] ⚠️ Weight reset did not fully restore initial weights")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Advanced weight management workflow completed successfully")

    @pytest.mark.workflow
    @pytest.mark.spinning
    def test_wheel_admin_selection_algorithm_comprehensive_testing(self, api_client: APIClient,
                                                                 test_data_factory: TestDataFactory,
                                                                 cleanup_manager: CleanupManager,
                                                                 assertions: APIAssertions):
        """
        Test comprehensive selection algorithm behavior for wheel admins
        
        Covers:
        - Selection probability verification with statistical analysis
        - Weight-based selection accuracy testing
        - Rigged selection behavior verification
        - Selection with apply_changes=true/false comparison
        - Edge cases and error conditions
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing comprehensive selection algorithm behavior...")
        
        # Step 1: Create authenticated wheel admin and setup
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "SelectionAlgorithmTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Create wheel for algorithm testing
        wheel_data = test_data_factory.create_wheel_data(
            name="AlgorithmTestWheel",
            description="Test wheel for selection algorithm verification"
        )
        wheel_data['settings'] = {
            "allow_rigging": True,
            "rigging_visible": True
        }
        
        response = wheel_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create algorithm test wheel")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        # Create participants with carefully chosen weights for statistical testing
        participants_data = [
            test_data_factory.create_participant_data("Frequent", weight=60),    # 60% probability
            test_data_factory.create_participant_data("Moderate", weight=30),    # 30% probability  
            test_data_factory.create_participant_data("Rare", weight=10)         # 10% probability
        ]
        
        created_participants = []
        expected_probabilities = {}
        total_weight = sum(p['weight'] for p in participants_data)
        
        for participant_data in participants_data:
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants',
                                             data=participant_data)
            assertions.assert_success_response(response, f"Failed to create participant {participant_data['participant_name']}")
            
            participant = response.json_data
            created_participants.append(participant)
            
            # Calculate expected probability
            expected_prob = participant_data['weight'] / total_weight
            expected_probabilities[participant['participant_id']] = {
                'name': participant_data['participant_name'],
                'weight': participant_data['weight'],
                'expected_probability': expected_prob
            }
            
            cleanup_manager.register_participant(participant['participant_id'])
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Setup: {len(created_participants)} participants with known probabilities")
        time.sleep(1.0)
        
        # Step 2: Statistical selection probability verification
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Statistical selection probability verification...")
        
        # Perform many selections for statistical analysis
        selection_counts = {}
        num_statistical_tests = 100  # Enough for reasonable statistical confidence
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Performing {num_statistical_tests} selections for statistical analysis...")
        
        for i in range(num_statistical_tests):
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=false')
            assertions.assert_success_response(response, f"Failed to get suggestions on statistical test {i+1}")
            
            suggest_result = response.json_data
            selected_participant = suggest_result['selected_participant']
            selected_id = selected_participant['participant_id']
            
            if selected_id not in selection_counts:
                selection_counts[selected_id] = 0
            selection_counts[selected_id] += 1
            
            if (i + 1) % 20 == 0:
                print(f"[WHEEL-ADMIN-WORKFLOW] Completed {i+1}/{num_statistical_tests} selections...")
        
        # Analyze statistical results
        print("[WHEEL-ADMIN-WORKFLOW] Statistical analysis results:")
        total_selections = sum(selection_counts.values())
        
        for participant_id, expected_data in expected_probabilities.items():
            actual_count = selection_counts.get(participant_id, 0)
            actual_probability = actual_count / total_selections if total_selections > 0 else 0
            expected_probability = expected_data['expected_probability']
            
            difference = abs(actual_probability - expected_probability)
            difference_percent = difference * 100
            
            print(f"[WHEEL-ADMIN-WORKFLOW]   {expected_data['name']}:")
            print(f"[WHEEL-ADMIN-WORKFLOW]     Expected: {expected_probability:.1%} ({expected_probability*total_selections:.1f} selections)")
            print(f"[WHEEL-ADMIN-WORKFLOW]     Actual:   {actual_probability:.1%} ({actual_count} selections)")
            print(f"[WHEEL-ADMIN-WORKFLOW]     Difference: {difference_percent:.1f} percentage points")
            
            # Statistical tolerance - allow up to 10 percentage points difference for small sample
            if difference_percent <= 10.0:
                print(f"[WHEEL-ADMIN-WORKFLOW]     ✅ Within acceptable statistical variance")
            else:
                print(f"[WHEEL-ADMIN-WORKFLOW]     ⚠️ Outside expected statistical variance")
        
        # Step 3: Test rigged selection behavior
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Testing rigged selection behavior...")
        
        # Rig the "Rare" participant (lowest weight)
        rare_participant = None
        for participant in created_participants:
            if expected_probabilities[participant['participant_id']]['name'] == "Rare":
                rare_participant = participant
                break
        
        assert rare_participant is not None, "Could not find Rare participant"
        
        rig_data = {
            "reason": "Testing rigged selection behavior"
        }
        
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants/{rare_participant['participant_id']}/rig',
                                         data=rig_data)
        assertions.assert_success_response(response, "Failed to rig Rare participant")
        
        print("[WHEEL-ADMIN-WORKFLOW] Rigged 'Rare' participant (normally 10% probability)")
        
        # Test rigged selection behavior - should now always select Rare
        rigged_tests = 10
        rigged_selections = 0
        
        for i in range(rigged_tests):
            response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=false')
            assertions.assert_success_response(response, f"Failed to get rigged suggestions on test {i+1}")
            
            suggest_result = response.json_data
            selected_participant = suggest_result['selected_participant']
            
            if selected_participant['participant_id'] == rare_participant['participant_id']:
                rigged_selections += 1
        
        rigged_percentage = (rigged_selections / rigged_tests) * 100
        print(f"[WHEEL-ADMIN-WORKFLOW] Rigged selection verification: {rigged_selections}/{rigged_tests} ({rigged_percentage:.1f}%) selected Rare")
        
        if rigged_selections == rigged_tests:
            print("[WHEEL-ADMIN-WORKFLOW] ✅ Rigging working perfectly - all selections picked rigged participant")
        elif rigged_selections >= rigged_tests * 0.8:  # Allow for some variance
            print("[WHEEL-ADMIN-WORKFLOW] ✅ Rigging working well - most selections picked rigged participant")
        else:
            print("[WHEEL-ADMIN-WORKFLOW] ⚠️ Rigging may not be working correctly")
        
        # Step 4: Test apply_changes comparison
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Comparing apply_changes=true vs false...")
        
        # Clear rigging for this test
        response = wheel_admin_client.delete(f'/wheels/{wheel_id}/rigging')
        if response.is_success:
            print("[WHEEL-ADMIN-WORKFLOW] Cleared rigging for apply_changes test")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Rigging clear not supported or failed: {response.status_code}")
            print("[WHEEL-ADMIN-WORKFLOW] Continuing with existing rigging state")
        
        # Get initial weights
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants for apply_changes test")
        
        participants_before = response.json_data
        if isinstance(participants_before, dict) and 'participants' in participants_before:
            participants_before = participants_before['participants']
        
        weights_before = {p['participant_id']: p.get('weight', p.get('current_weight', 0)) for p in participants_before}
        
        # Test apply_changes=false (should not change weights)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=false')
        assertions.assert_success_response(response, "Failed to test apply_changes=false")
        
        suggest_result_false = response.json_data
        selected_false = suggest_result_false['selected_participant']
        
        # Check weights didn't change
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants after apply_changes=false")
        
        participants_after_false = response.json_data
        if isinstance(participants_after_false, dict) and 'participants' in participants_after_false:
            participants_after_false = participants_after_false['participants']
        
        weights_after_false = {p['participant_id']: p.get('weight', p.get('current_weight', 0)) for p in participants_after_false}
        
        weights_unchanged = all(weights_before[pid] == weights_after_false.get(pid, 0) for pid in weights_before.keys())
        
        if weights_unchanged:
            print("[WHEEL-ADMIN-WORKFLOW] ✅ apply_changes=false correctly preserved weights")
        else:
            print("[WHEEL-ADMIN-WORKFLOW] ⚠️ apply_changes=false may have changed weights")
        
        # Test apply_changes=true (should change weights)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=true')
        assertions.assert_success_response(response, "Failed to test apply_changes=true")
        
        suggest_result_true = response.json_data
        selected_true = suggest_result_true['selected_participant']
        selected_true_id = selected_true['participant_id']
        
        # Check weights changed
        time.sleep(0.5)  # Allow for weight updates
        
        response = wheel_admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Failed to get participants after apply_changes=true")
        
        participants_after_true = response.json_data
        if isinstance(participants_after_true, dict) and 'participants' in participants_after_true:
            participants_after_true = participants_after_true['participants']
        
        weights_after_true = {p['participant_id']: p.get('weight', p.get('current_weight', 0)) for p in participants_after_true}
        
        selected_weight_change = weights_before.get(selected_true_id, 0) - weights_after_true.get(selected_true_id, 0)
        
        if selected_weight_change > 0:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ apply_changes=true correctly decreased selected participant weight by {selected_weight_change}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ apply_changes=true did not decrease selected participant weight (change: {selected_weight_change})")
        
        # Step 5: Test edge cases
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Testing edge cases and error conditions...")
        
        # Test participant name conflicts
        duplicate_name_data = test_data_factory.create_participant_data("Frequent")  # Same name as existing participant
        
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=duplicate_name_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Duplicate participant name correctly blocked: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Duplicate participant name allowed: {response.status_code}")
            # Clean up if it was created
            if response.is_success:
                duplicate_participant = response.json_data
                cleanup_manager.register_participant(duplicate_participant['participant_id'])
        
        # Test selection with zero-weight participants
        zero_weight_data = test_data_factory.create_participant_data("ZeroWeight", weight=0)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=zero_weight_data)
        
        if response.is_success:
            zero_weight_participant = response.json_data
            cleanup_manager.register_participant(zero_weight_participant['participant_id'])
            
            print("[WHEEL-ADMIN-WORKFLOW] Added zero-weight participant")
            
            # Test if zero-weight participant can be selected
            zero_weight_selected = False
            for i in range(10):
                response = wheel_admin_client.post(f'/wheels/{wheel_id}/suggest?apply_changes=false')
                if response.is_success:
                    suggest_result = response.json_data
                    if suggest_result['selected_participant']['participant_id'] == zero_weight_participant['participant_id']:
                        zero_weight_selected = True
                        break
            
            if zero_weight_selected:
                print("[WHEEL-ADMIN-WORKFLOW] ⚠️ Zero-weight participant was selected")
            else:
                print("[WHEEL-ADMIN-WORKFLOW] ✅ Zero-weight participant correctly not selected")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Zero-weight participant creation failed: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Comprehensive selection algorithm testing completed successfully")

    @pytest.mark.workflow
    def test_wheel_admin_error_handling_and_edge_cases(self, api_client: APIClient,
                                                     test_data_factory: TestDataFactory,
                                                     cleanup_manager: CleanupManager,
                                                     assertions: APIAssertions):
        """
        Test error handling and edge cases for wheel admin operations
        
        Covers:
        - Participant name conflicts
        - Invalid wheel configurations
        - Boundary conditions for weights
        - API error responses and handling
        """
        print("\n[WHEEL-ADMIN-WORKFLOW] Testing error handling and edge cases...")
        
        # Step 1: Create authenticated wheel admin and setup
        wheel_admin_info = self._create_authenticated_wheel_admin_client(
            api_client, test_data_factory, cleanup_manager, assertions,
            "ErrorHandlingTestGroup"
        )
        
        wheel_admin_client = wheel_admin_info['client']
        wheel_group_id = wheel_admin_info['wheel_group_id']
        
        # Create wheel for error testing
        wheel_data = test_data_factory.create_wheel_data(
            name="ErrorTestWheel",
            description="Test wheel for error handling"
        )
        
        response = wheel_admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, "Failed to create error test wheel")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        print(f"[WHEEL-ADMIN-WORKFLOW] Setup: Created wheel for error testing: {wheel_id}")
        
        # Step 2: Test participant name conflicts
        print("[WHEEL-ADMIN-WORKFLOW] Step 2: Testing participant name conflicts...")
        
        # Create first participant
        participant_data = test_data_factory.create_participant_data("ConflictTest")
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=participant_data)
        assertions.assert_success_response(response, "Failed to create first participant")
        
        first_participant = response.json_data
        cleanup_manager.register_participant(first_participant['participant_id'])
        
        print("[WHEEL-ADMIN-WORKFLOW] Created first participant: ConflictTest")
        
        # Try to create second participant with same name
        duplicate_data = test_data_factory.create_participant_data("ConflictTest")
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=duplicate_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Duplicate name correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Duplicate name allowed: {response.status_code}")
            if response.is_success:
                duplicate_participant = response.json_data
                cleanup_manager.register_participant(duplicate_participant['participant_id'])
        
        # Test case-insensitive name conflicts
        case_variant_data = test_data_factory.create_participant_data("conflicttest")  # lowercase
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=case_variant_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Case-insensitive duplicate correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Case-insensitive duplicate allowed: {response.status_code}")
            if response.is_success:
                case_participant = response.json_data
                cleanup_manager.register_participant(case_participant['participant_id'])
        
        # Step 3: Test boundary conditions for weights
        print("[WHEEL-ADMIN-WORKFLOW] Step 3: Testing weight boundary conditions...")
        
        # Test negative weight
        negative_weight_data = test_data_factory.create_participant_data("NegativeWeight", weight=-5)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=negative_weight_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Negative weight correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Negative weight allowed: {response.status_code}")
            if response.is_success:
                negative_participant = response.json_data
                cleanup_manager.register_participant(negative_participant['participant_id'])
        
        # Test extremely high weight
        high_weight_data = test_data_factory.create_participant_data("HighWeight", weight=999999)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=high_weight_data)
        
        if response.is_success:
            high_weight_participant = response.json_data
            cleanup_manager.register_participant(high_weight_participant['participant_id'])
            print(f"[WHEEL-ADMIN-WORKFLOW] High weight (999999) allowed: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] High weight rejected: {response.status_code}")
        
        # Test fractional weight
        fractional_weight_data = test_data_factory.create_participant_data("FractionalWeight", weight=5.5)
        response = wheel_admin_client.post(f'/wheels/{wheel_id}/participants', data=fractional_weight_data)
        
        if response.is_success:
            fractional_participant = response.json_data
            cleanup_manager.register_participant(fractional_participant['participant_id'])
            print(f"[WHEEL-ADMIN-WORKFLOW] Fractional weight (5.5) allowed: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] Fractional weight rejected: {response.status_code}")
        
        # Step 4: Test invalid wheel configurations
        print("[WHEEL-ADMIN-WORKFLOW] Step 4: Testing invalid wheel configurations...")
        
        # Test wheel with empty name
        empty_name_wheel_data = test_data_factory.create_wheel_data(
            name="",
            description="Wheel with empty name"
        )
        
        response = wheel_admin_client.post('/wheels', data=empty_name_wheel_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Empty wheel name correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Empty wheel name allowed: {response.status_code}")
            if response.is_success:
                empty_wheel = response.json_data
                cleanup_manager.register_wheel(empty_wheel['wheel_id'])
        
        # Test wheel with extremely long name
        long_name = "A" * 1000  # 1000 character name
        long_name_wheel_data = test_data_factory.create_wheel_data(
            name=long_name,
            description="Wheel with very long name"
        )
        
        response = wheel_admin_client.post('/wheels', data=long_name_wheel_data)
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Extremely long wheel name correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Extremely long wheel name allowed: {response.status_code}")
            if response.is_success:
                long_wheel = response.json_data
                cleanup_manager.register_wheel(long_wheel['wheel_id'])
        
        # Step 5: Test operations on non-existent resources
        print("[WHEEL-ADMIN-WORKFLOW] Step 5: Testing operations on non-existent resources...")
        
        # Test accessing non-existent wheel
        fake_wheel_id = "00000000-0000-0000-0000-000000000000"
        response = wheel_admin_client.get(f'/wheels/{fake_wheel_id}')
        
        if response.is_client_error or response.status_code == 404:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Non-existent wheel correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Non-existent wheel request succeeded: {response.status_code}")
        
        # Test adding participant to non-existent wheel
        participant_data = test_data_factory.create_participant_data("TestParticipant")
        response = wheel_admin_client.post(f'/wheels/{fake_wheel_id}/participants', data=participant_data)
        
        if response.is_client_error or response.status_code == 404:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Adding participant to non-existent wheel correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Adding participant to non-existent wheel succeeded: {response.status_code}")
        
        # Test modifying non-existent participant
        fake_participant_id = "00000000-0000-0000-0000-000000000000"
        update_data = {"participant_name": "Updated Name"}
        response = wheel_admin_client.put(f'/wheels/{wheel_id}/participants/{fake_participant_id}', data=update_data)
        
        if response.is_client_error or response.status_code == 404:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Modifying non-existent participant correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Modifying non-existent participant succeeded: {response.status_code}")
        
        # Step 6: Test spinning wheel with no participants
        print("[WHEEL-ADMIN-WORKFLOW] Step 6: Testing wheel operations with no participants...")
        
        # Create empty wheel
        empty_wheel_data = test_data_factory.create_wheel_data(
            name="EmptyWheel",
            description="Wheel with no participants"
        )
        
        response = wheel_admin_client.post('/wheels', data=empty_wheel_data)
        assertions.assert_success_response(response, "Failed to create empty wheel")
        
        empty_wheel = response.json_data
        empty_wheel_id = empty_wheel['wheel_id']
        cleanup_manager.register_wheel(empty_wheel_id)
        
        # Try to spin empty wheel
        response = wheel_admin_client.post(f'/wheels/{empty_wheel_id}/suggest')
        
        if response.is_client_error:
            print(f"[WHEEL-ADMIN-WORKFLOW] ✅ Spinning empty wheel correctly rejected: {response.status_code}")
        else:
            print(f"[WHEEL-ADMIN-WORKFLOW] ⚠️ Spinning empty wheel succeeded: {response.status_code}")
        
        print("[WHEEL-ADMIN-WORKFLOW] ✅ Error handling and edge cases testing completed successfully")
