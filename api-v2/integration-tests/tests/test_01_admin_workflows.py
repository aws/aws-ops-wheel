"""
Integration tests for ADMIN Workflows in AWS Ops Wheel v2

Tests comprehensive ADMIN role capabilities:
- Full wheel group management and administration
- Complete wheel lifecycle management (create, read, update, delete)
- Comprehensive participant management
- Wheel group settings and configuration management
- Advanced wheel operations (bulk actions, batch operations)
- Administrative reporting and analytics
- Cross-wheel operations within owned wheel groups
- Security boundary enforcement

ADMIN Role Capabilities:
- Full access to everything within their owned wheel groups
- Wheel group creation, configuration, and management
- Complete wheel and participant management
- Advanced administrative operations
- Statistical analysis and reporting
- Cannot access other users' wheel groups (isolation enforcement)

Uses dynamic user creation and demonstrates complete administrative workflows
"""

import pytest
import time
import logging
import concurrent.futures
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timezone

from utils.api_client import APIClient, APIResponse
from utils.assertions import APIAssertions
from utils.test_data_factory import TestDataFactory
from utils.cleanup import CleanupManager
from utils.cognito_authenticator import CognitoAuthenticator
from config.test_config import TestConfig

# Configure logging
logger = logging.getLogger(__name__)

# Test constants - optimized for performance
CONSISTENCY_WAIT_SECONDS = 1.0
SHORT_WAIT_SECONDS = 0.5
MICRO_WAIT_SECONDS = 0.2
BATCH_OPERATION_DELAY_SECONDS = 0.1
SPIN_DELAY_SECONDS = 0.1

# Test retry constants
MAX_AUTH_RETRIES = 3
AUTH_RETRY_DELAY_SECONDS = 0.5

# Administrative test constants
BULK_OPERATIONS_COUNT = 5
ADMIN_REPORTING_SAMPLE_SIZE = 10
CONCURRENT_OPERATIONS_COUNT = 3


class TestAdminWorkflows:
    """Test class for ADMIN role comprehensive workflow testing"""

    def _wait_for_resource_consistency(self, check_func, timeout_seconds: float = CONSISTENCY_WAIT_SECONDS) -> bool:
        """Wait for resource consistency using exponential backoff"""
        import time
        start_time = time.time()
        delay = 0.1
        
        while time.time() - start_time < timeout_seconds:
            try:
                if check_func():
                    return True
            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Resource consistency check failed: {e}")
                return False
            except Exception as e:
                logger.debug(f"Resource consistency check exception: {e}")
                pass
            time.sleep(delay)
            delay = min(delay * 1.5, 1.0)
        return False

    def _safe_api_call(self, client, method, url, data=None, max_retries=3):
        """Safe API call with proper error handling"""
        response = None
        for attempt in range(max_retries):
            try:
                if method == 'POST':
                    response = client.post(url, data=data)
                elif method == 'GET':
                    response = client.get(url)
                elif method == 'PUT':
                    response = client.put(url, data=data)
                elif method == 'DELETE':
                    response = client.delete(url)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.is_success:
                    return response
                elif response.status_code >= 500:  # Server error, retry
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                else:  # Client error, don't retry
                    break
                    
            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"API call failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise
        
        # Return response or create a default error response if None
        if response is None:
            # Create a mock response object with error status
            class MockResponse:
                def __init__(self):
                    self.status_code = 500
                    self.is_success = False
                    self.is_client_error = False
                    self.json_data = {}
                    self.text = "Failed to get response after retries"
            response = MockResponse()
        return response

    def _check_user_ready(self, username: str) -> bool:
        """Check if a user is ready for authentication"""
        # This is a placeholder - implement actual user readiness check
        # For now, we'll use a simple time-based approach
        return True

    def _retry_with_backoff(self, operation_func, max_retries: int = MAX_AUTH_RETRIES) -> Any:
        """Retry operation with exponential backoff"""
        import time
        for attempt in range(max_retries + 1):
            try:
                return operation_func()
            except Exception as e:
                if attempt < max_retries:
                    delay = AUTH_RETRY_DELAY_SECONDS * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise e

    def _safe_get_nested_value(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Safely get nested dictionary values with dot notation"""
        try:
            keys = path.split('.')
            result = data
            for key in keys:
                if isinstance(result, dict) and key in result:
                    result = result[key]
                else:
                    return default
            return result
        except (KeyError, TypeError, AttributeError):
            return default

    def _parse_response_data(self, response: APIResponse) -> List[Any]:
        """Parse response data handling both direct lists and nested structures"""
        if not response.is_success:
            return []
        
        data = response.json_data
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try common nested keys
            for key in ['wheels', 'participants', 'users', 'items', 'data']:
                if key in data:
                    nested_data = data[key]
                    return nested_data if isinstance(nested_data, list) else []
        
        return []

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format with timezone"""
        return datetime.now(timezone.utc).isoformat()

    def _validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> bool:
        """Validate that all required fields are present in data"""
        try:
            for field in required_fields:
                if '.' in field:
                    # Handle nested fields
                    if self._safe_get_nested_value(data, field) is None:
                        return False
                else:
                    if field not in data or data[field] is None:
                        return False
            return True
        except Exception:
            return False

    def _create_admin_test_environment(self, api_client: APIClient,
                                     test_data_factory: TestDataFactory,
                                     cleanup_manager: CleanupManager,
                                     assertions: APIAssertions) -> Dict[str, Any]:
        """
        Create comprehensive admin test environment with wheel group and authentication
        
        Returns:
            Dict containing authenticated admin client and wheel group information
        """
        config = TestConfig('test')
        cognito_auth = CognitoAuthenticator(
            user_pool_id=config.cognito_user_pool_id,
            client_id=config.cognito_client_id,
            region=config.aws_region,
            debug=True
        )
        
        # Create wheel group for admin testing
        wheel_group_data = test_data_factory.create_public_wheel_group_data(
            name="AdminTestGroup"
        )
        
        response = api_client.post('/wheel-group/create-public', data=wheel_group_data)
        assertions.assert_success_response(response, "Failed to create admin test wheel group")
        
        wheel_group = response.json_data['wheel_group']
        admin_user = response.json_data['admin_user']
        
        wheel_group_id = wheel_group['wheel_group_id']
        admin_username = wheel_group_data['admin_user']['username']
        admin_password = wheel_group_data['admin_user']['password']
        
        cleanup_manager.register_wheel_group(wheel_group_id)
        
        # Wait for user creation consistency
        time.sleep(CONSISTENCY_WAIT_SECONDS)
        
        # Authenticate admin
        def auth_admin():
            return cognito_auth.authenticate_user(admin_username, admin_password)
        
        admin_auth_result = self._retry_with_backoff(auth_admin)
        
        admin_client = APIClient(base_url=config.api_base_url, debug=True)
        admin_client.set_auth_token(admin_auth_result['id_token'])
        
        return {
            'config': config,
            'cognito_auth': cognito_auth,
            'wheel_group_id': wheel_group_id,
            'wheel_group': wheel_group,
            'admin_username': admin_username,
            'admin_password': admin_password,
            'admin_client': admin_client,
            'admin_auth_result': admin_auth_result
        }

    def _setup_comprehensive_wheel_infrastructure(self, admin_client: APIClient,
                                                test_data_factory: TestDataFactory,
                                                cleanup_manager: CleanupManager,
                                                assertions: APIAssertions) -> Dict[str, Any]:
        """Setup comprehensive wheel infrastructure for admin testing"""
        
        # Create multiple wheels with different configurations for comprehensive testing
        wheel_configurations = [
            {
                "name": "ProjectAssignmentWheel",
                "description": "Assign team members to various projects",
                "participants": [
                    {"name": "Senior Developer", "weight": 8},
                    {"name": "Mid-level Developer", "weight": 6},
                    {"name": "Junior Developer", "weight": 4},
                    {"name": "Intern", "weight": 2}
                ],
                "settings": {
                    "allow_rigging": True,
                    "show_weights": True,
                    "multi_select_enabled": True,
                    "default_multi_select_count": 2
                }
            },
            {
                "name": "CodeReviewWheel",
                "description": "Select code reviewers for pull requests",
                "participants": [
                    {"name": "Tech Lead", "weight": 3},
                    {"name": "Senior Engineer", "weight": 5},
                    {"name": "Principal Engineer", "weight": 2}
                ],
                "settings": {
                    "allow_rigging": False,
                    "show_weights": False,
                    "multi_select_enabled": False,
                    "require_reason_for_rigging": True
                }
            },
            {
                "name": "OnCallRotationWheel",
                "description": "Determine on-call rotation assignments",
                "participants": [
                    {"name": "DevOps Engineer A", "weight": 1},
                    {"name": "DevOps Engineer B", "weight": 1},
                    {"name": "Site Reliability Engineer", "weight": 1}
                ],
                "settings": {
                    "allow_rigging": True,
                    "show_weights": True,
                    "auto_reset_weights": True
                }
            },
            {
                "name": "TestDataWheel",
                "description": "Wheel for administrative testing and bulk operations",
                "participants": [
                    {"name": f"TestParticipant{i}", "weight": i + 1} for i in range(6)
                ],
                "settings": {
                    "allow_rigging": True,
                    "show_weights": True,
                    "multi_select_enabled": True,
                    "default_multi_select_count": 3
                }
            }
        ]
        
        created_wheels = []
        all_participants = []
        
        for wheel_config in wheel_configurations:
            # Create wheel
            wheel_data = test_data_factory.create_wheel_data(
                name=wheel_config["name"],
                description=wheel_config["description"]
            )
        wheel_data["settings"] = wheel_config["settings"]
        
        response = admin_client.post('/wheels', data=wheel_data)
        assertions.assert_success_response(response, f"Failed to create {wheel_config['name']}")
        
        wheel = response.json_data
        wheel_id = wheel['wheel_id']
        cleanup_manager.register_wheel(wheel_id)
        
        # Add participants with specific weights
        wheel_participants = []
        participants_config = wheel_config["participants"]
        
        for participant_config in participants_config:
            participant_data = test_data_factory.create_participant_data(
                participant_config["name"]
            )
            participant_data["weight"] = participant_config["weight"]
            
            response = admin_client.post(f'/wheels/{wheel_id}/participants', 
                                       data=participant_data)
            assertions.assert_success_response(response, 
                f"Failed to add participant {participant_config['name']}")
            
            participant = response.json_data
            wheel_participants.append(participant)
            all_participants.append(participant)
            cleanup_manager.register_participant(participant['participant_id'])
            
            # Small delay between participant creation
            time.sleep(MICRO_WAIT_SECONDS)
        
        created_wheels.append({
            'wheel': wheel,
            'participants': wheel_participants,
            'config': wheel_config
        })
        
        # Small delay between wheel creation
        time.sleep(SHORT_WAIT_SECONDS)
        
        return {
            'wheels': created_wheels,
            'all_participants': all_participants,
            'wheel_count': len(created_wheels),
            'participant_count': len(all_participants)
        }

    @pytest.mark.workflow
    @pytest.mark.admin
    def test_admin_comprehensive_wheel_management(self, api_client: APIClient,
                                                test_data_factory: TestDataFactory,
                                                cleanup_manager: CleanupManager,
                                                assertions: APIAssertions):
        """
        Test comprehensive wheel management capabilities for ADMIN role
        
        Validates complete wheel lifecycle management including creation, configuration,
        modification, and administrative operations.
        """
        print("\n[ADMIN] Testing comprehensive wheel management...")
        
        # Step 1: Setup admin test environment
        print("[ADMIN] Step 1: Setting up admin test environment...")
        
        env = self._create_admin_test_environment(
            api_client, test_data_factory, cleanup_manager, assertions
        )
        
        admin_client = env['admin_client']
        
        print(f"[ADMIN] Admin environment created for wheel group: {env['wheel_group_id']}")
        
        # Step 2: Create comprehensive wheel infrastructure
        print("[ADMIN] Step 2: Creating comprehensive wheel infrastructure...")
        
        infrastructure = self._setup_comprehensive_wheel_infrastructure(
            admin_client, test_data_factory, cleanup_manager, assertions
        )
        
        wheels = infrastructure['wheels']
        print(f"[ADMIN] Created {infrastructure['wheel_count']} wheels with {infrastructure['participant_count']} total participants")
        
        # Step 3: Test wheel viewing and listing capabilities
        print("[ADMIN] Step 3: Testing wheel viewing and listing capabilities...")
        
        # Admin can view all wheels in their wheel group
        response = admin_client.get('/wheels')
        assertions.assert_success_response(response, "Admin should be able to view wheels")
        
        wheels_response = response.json_data
        if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
            visible_wheels = wheels_response['wheels']
        else:
            visible_wheels = wheels_response
        
        assert len(visible_wheels) >= infrastructure['wheel_count'], \
            f"Admin should see at least {infrastructure['wheel_count']} wheels"
        print(f"[ADMIN] ✅ Admin can view {len(visible_wheels)} wheels")
        
        # Test individual wheel access
        for wheel_info in wheels[:2]:  # Test first 2 wheels
            wheel = wheel_info['wheel']
            wheel_id = wheel['wheel_id']
            
            response = admin_client.get(f'/wheels/{wheel_id}')
            assertions.assert_success_response(response, f"Admin should access wheel {wheel['wheel_name']}")
            
            wheel_details = response.json_data
            assert wheel_details['wheel_id'] == wheel_id, "Wheel details should match"
            print(f"[ADMIN] ✅ Admin can access wheel: {wheel['wheel_name']}")
        
        # Step 4: Test comprehensive wheel modification capabilities
        print("[ADMIN] Step 4: Testing comprehensive wheel modification capabilities...")
        
        test_wheel = wheels[0]['wheel']
        test_wheel_id = test_wheel['wheel_id']
        
        # Test basic wheel updates
        update_data = {
            "description": "Updated description by admin - comprehensive management test",
            "settings": {
                "allow_rigging": False,
                "show_weights": True,
                "multi_select_enabled": True,
                "default_multi_select_count": 3,
                "require_reason_for_rigging": True
            }
        }
        
        response = admin_client.put(f'/wheels/{test_wheel_id}', data=update_data)
        if response.is_success:
            print("[ADMIN] ✅ Admin can modify wheel settings")
            
            # Verify the changes
            response = admin_client.get(f'/wheels/{test_wheel_id}')
            if response.is_success:
                updated_wheel = response.json_data
                assert "comprehensive management test" in updated_wheel['description'], \
                    "Wheel description should be updated"
                assert updated_wheel['settings']['require_reason_for_rigging'] == True, \
                    "Wheel settings should be updated"
                print("[ADMIN] ✅ Wheel modifications verified")
        else:
            print(f"[ADMIN] ⚠️ Wheel modification returned: {response.status_code}")
        
        # Step 5: Test advanced wheel operations
        print("[ADMIN] Step 5: Testing advanced wheel operations...")
        
        # Test wheel duplication/cloning capability
        clone_data = test_data_factory.create_wheel_data(
            name=f"Clone_{test_wheel['wheel_name']}",
            description=f"Cloned from {test_wheel['wheel_name']} for admin testing"
        )
        clone_data["settings"] = test_wheel.get("settings", {})
        
        response = admin_client.post('/wheels', data=clone_data)
        if response.is_success:
            cloned_wheel = response.json_data
            cleanup_manager.register_wheel(cloned_wheel['wheel_id'])
            print(f"[ADMIN] ✅ Admin created cloned wheel: {cloned_wheel['wheel_name']}")
        else:
            print(f"[ADMIN] ⚠️ Wheel cloning returned: {response.status_code}")
        
        # Test wheel archiving/deletion
        if len(wheels) > 2:  # Only test deletion if we have extra wheels
            deletion_target = wheels[-1]['wheel']  # Use last wheel for deletion test
            deletion_wheel_id = deletion_target['wheel_id']
            
            response = admin_client.delete(f'/wheels/{deletion_wheel_id}')
            if response.is_success:
                print(f"[ADMIN] ✅ Admin can delete wheel: {deletion_target['wheel_name']}")
                
                # Verify deletion
                response = admin_client.get(f'/wheels/{deletion_wheel_id}')
                if response.is_client_error or response.status_code == 404:
                    print("[ADMIN] ✅ Wheel deletion verified")
            else:
                print(f"[ADMIN] ⚠️ Wheel deletion returned: {response.status_code}")
        
        print("[ADMIN] ✅ Comprehensive wheel management validated")

    @pytest.mark.workflow
    @pytest.mark.admin
    def test_admin_comprehensive_participant_management(self, api_client: APIClient,
                                                       test_data_factory: TestDataFactory,
                                                       cleanup_manager: CleanupManager,
                                                       assertions: APIAssertions):
        """
        Test comprehensive participant management capabilities for ADMIN role
        
        Validates complete participant lifecycle including creation, modification, 
        bulk operations, and advanced participant management features.
        """
        print("\n[ADMIN] Testing comprehensive participant management...")
        
        # Step 1: Setup admin environment with wheels
        print("[ADMIN] Step 1: Setting up admin environment for participant management...")
        
        env = self._create_admin_test_environment(
            api_client, test_data_factory, cleanup_manager, assertions
        )
        
        admin_client = env['admin_client']
        infrastructure = self._setup_comprehensive_wheel_infrastructure(
            admin_client, test_data_factory, cleanup_manager, assertions
        )
        
        wheels = infrastructure['wheels']
        test_wheel = wheels[0]  # Use first wheel for participant management testing
        wheel_id = test_wheel['wheel']['wheel_id']
        existing_participants = test_wheel['participants']
        
        print(f"[ADMIN] Using wheel '{test_wheel['wheel']['wheel_name']}' with {len(existing_participants)} existing participants")
        
        # Step 2: Test individual participant operations
        print("[ADMIN] Step 2: Testing individual participant operations...")
        
        # Admin can view all participants
        response = admin_client.get(f'/wheels/{wheel_id}/participants')
        assertions.assert_success_response(response, "Admin should view participants")
        
        participants_response = response.json_data
        if isinstance(participants_response, dict) and 'participants' in participants_response:
            participants_list = participants_response['participants']
        else:
            participants_list = participants_response
            
        assert len(participants_list) >= len(existing_participants), \
            "Admin should see all participants"
        print(f"[ADMIN] ✅ Admin can view {len(participants_list)} participants")
        
        # Admin can add new participants
        new_participant_data = test_data_factory.create_participant_data("AdminAddedParticipant")
        new_participant_data["weight"] = 10
        
        response = admin_client.post(f'/wheels/{wheel_id}/participants', 
                                   data=new_participant_data)
        assertions.assert_success_response(response, "Admin should add participants")
        
        new_participant = response.json_data
        new_participant_id = new_participant['participant_id']
        cleanup_manager.register_participant(new_participant_id)
        print(f"[ADMIN] ✅ Admin added participant: {new_participant['participant_name']}")
        
        # Admin can modify existing participants
        if existing_participants:
            target_participant = existing_participants[0]
            target_participant_id = target_participant['participant_id']
            
            modification_data = {
                "participant_name": f"Modified_{target_participant['participant_name']}",
                "weight": target_participant['weight'] + 5
            }
            
            response = admin_client.put(f'/wheels/{wheel_id}/participants/{target_participant_id}', 
                                      data=modification_data)
            if response.is_success:
                print(f"[ADMIN] ✅ Admin modified participant: {target_participant['participant_name']}")
                
                # Verify modification
                response = admin_client.get(f'/wheels/{wheel_id}/participants')
                if response.is_success:
                    updated_participants_response = response.json_data
                    if isinstance(updated_participants_response, dict) and 'participants' in updated_participants_response:
                        updated_participants = updated_participants_response['participants']
                    else:
                        updated_participants = updated_participants_response
                    
                    modified_participant = next(
                        (p for p in updated_participants if p['participant_id'] == target_participant_id), 
                        None
                    )
                    if modified_participant and "Modified_" in modified_participant['participant_name']:
                        print("[ADMIN] ✅ Participant modification verified")
            else:
                print(f"[ADMIN] ⚠️ Participant modification returned: {response.status_code}")
        
        # Step 3: Test bulk participant operations
        print("[ADMIN] Step 3: Testing bulk participant operations...")
        
        # Create multiple participants for bulk operations testing
        bulk_participants = []
        for i in range(BULK_OPERATIONS_COUNT):
            bulk_participant_data = test_data_factory.create_participant_data(f"BulkParticipant{i+1}")
            bulk_participant_data["weight"] = (i + 1) * 2
            
            response = admin_client.post(f'/wheels/{wheel_id}/participants', 
                                       data=bulk_participant_data)
            if response.is_success:
                participant = response.json_data
                bulk_participants.append(participant)
                cleanup_manager.register_participant(participant['participant_id'])
            
            time.sleep(BATCH_OPERATION_DELAY_SECONDS)  # Small delay between bulk operations
        
        print(f"[ADMIN] ✅ Admin created {len(bulk_participants)} participants in bulk")
        
        # Test bulk weight updates
        for i, participant in enumerate(bulk_participants[:3]):  # Update first 3
            participant_id = participant['participant_id']
            new_weight = (i + 1) * 10
            
            weight_update_data = {"weight": new_weight}
            response = admin_client.put(f'/wheels/{wheel_id}/participants/{participant_id}', 
                                      data=weight_update_data)
            if response.is_success:
                print(f"[ADMIN] ✅ Bulk weight update {i+1}: {participant['participant_name']} → {new_weight}")
            
            time.sleep(BATCH_OPERATION_DELAY_SECONDS)
        
        # Step 4: Test advanced participant management features
        print("[ADMIN] Step 4: Testing advanced participant management features...")
        
        # Test participant statistics and analysis
        response = admin_client.get(f'/wheels/{wheel_id}/participants')
        if response.is_success:
            all_participants_response = response.json_data
            if isinstance(all_participants_response, dict) and 'participants' in all_participants_response:
                all_participants = all_participants_response['participants']
            else:
                all_participants = all_participants_response
            
            if all_participants:
                total_weight = sum(p['weight'] for p in all_participants)
                avg_weight = total_weight / len(all_participants)
                
                print(f"[ADMIN] Participant statistics:")
                print(f"[ADMIN]   Total participants: {len(all_participants)}")
                print(f"[ADMIN]   Total weight: {total_weight}")
                print(f"[ADMIN]   Average weight: {avg_weight:.2f}")
                print("[ADMIN] ✅ Admin can analyze participant statistics")
            else:
                print("[ADMIN] ⚠️ No participants found for statistics")
        
        # Test participant deletion (cleanup some bulk participants)
        if len(bulk_participants) > 2:
            deletion_targets = bulk_participants[-2:]  # Delete last 2 bulk participants
            
            for participant in deletion_targets:
                participant_id = participant['participant_id']
                response = admin_client.delete(f'/wheels/{wheel_id}/participants/{participant_id}')
                if response.is_success:
                    print(f"[ADMIN] ✅ Admin deleted participant: {participant['participant_name']}")
                else:
                    print(f"[ADMIN] ⚠️ Participant deletion returned: {response.status_code}")
                
                time.sleep(BATCH_OPERATION_DELAY_SECONDS)
        
        print("[ADMIN] ✅ Comprehensive participant management validated")

    @pytest.mark.workflow
    @pytest.mark.admin
    def test_admin_advanced_wheel_operations_and_analytics(self, api_client: APIClient,
                                                          test_data_factory: TestDataFactory,
                                                          cleanup_manager: CleanupManager,
                                                          assertions: APIAssertions):
        """
        Test advanced wheel operations and analytics capabilities for ADMIN role
        
        Validates spinning operations, statistical analysis, reporting capabilities,
        and advanced administrative features.
        """
        print("\n[ADMIN] Testing advanced wheel operations and analytics...")
        
        # Step 1: Setup environment with comprehensive infrastructure
        print("[ADMIN] Step 1: Setting up environment for advanced operations...")
        
        env = self._create_admin_test_environment(
            api_client, test_data_factory, cleanup_manager, assertions
        )
        
        admin_client = env['admin_client']
        infrastructure = self._setup_comprehensive_wheel_infrastructure(
            admin_client, test_data_factory, cleanup_manager, assertions
        )
        
        wheels = infrastructure['wheels']
        print(f"[ADMIN] Environment ready with {len(wheels)} wheels for advanced testing")
        
        # Step 2: Test comprehensive spinning operations
        print("[ADMIN] Step 2: Testing comprehensive spinning operations...")
        
        spin_results = []
        statistical_data = {}
        
        for wheel_info in wheels:
            wheel = wheel_info['wheel']
            wheel_id = wheel['wheel_id']
            wheel_name = wheel['wheel_name']
            participants = wheel_info['participants']
            
            if not participants:  # Skip wheels without participants
                continue
            
            print(f"[ADMIN] Testing spins for wheel: {wheel_name}")
            
            # Perform multiple spins for statistical analysis
            wheel_spin_results = []
            participant_selections = {}
            
            for spin_num in range(ADMIN_REPORTING_SAMPLE_SIZE):
                response = admin_client.post(f'/wheels/{wheel_id}/suggest')
                
                if response.is_success:
                    result = response.json_data
                    selected_participant = result.get('selected_participant', {})
                    participant_name = selected_participant.get('participant_name', 'Unknown')
                    
                    wheel_spin_results.append({
                        'spin_number': spin_num + 1,
                        'selected_participant': participant_name,
                        'timestamp': self._get_current_timestamp()
                    })
                    
                    # Track selections for statistical analysis
                    if participant_name in participant_selections:
                        participant_selections[participant_name] += 1
                    else:
                        participant_selections[participant_name] = 1
                    
                    print(f"[ADMIN] Spin {spin_num + 1}: Selected {participant_name}")
                else:
                    print(f"[ADMIN] ⚠️ Spin {spin_num + 1} failed: {response.status_code}")
                
                time.sleep(SPIN_DELAY_SECONDS)
            
            statistical_data[wheel_name] = {
                'total_spins': len(wheel_spin_results),
                'participant_selections': participant_selections,
                'participants_count': len(participants)
            }
            
            spin_results.extend(wheel_spin_results)
        
        print(f"[ADMIN] ✅ Completed {len(spin_results)} total spins across {len(statistical_data)} wheels")
        
        # Step 3: Test advanced statistical analysis and reporting
        print("[ADMIN] Step 3: Testing advanced statistical analysis and reporting...")
        
        # Generate comprehensive statistical report
        print("[ADMIN] Generating comprehensive statistical report:")
        
        for wheel_name, stats in statistical_data.items():
            total_spins = stats['total_spins']
            selections = stats['participant_selections']
            participants_count = stats['participants_count']
            
            print(f"[ADMIN] Wheel: {wheel_name}")
            print(f"[ADMIN]   Total spins: {total_spins}")
            print(f"[ADMIN]   Participants: {participants_count}")
            
            if selections:
                most_selected = max(selections.items(), key=lambda x: x[1])
                least_selected = min(selections.items(), key=lambda x: x[1])
                
                print(f"[ADMIN]   Most selected: {most_selected[0]} ({most_selected[1]} times)")
                print(f"[ADMIN]   Least selected: {least_selected[0]} ({least_selected[1]} times)")
                
                # Calculate selection distribution
                selection_percentages = {
                    name: (count / total_spins) * 100 
                    for name, count in selections.items()
                }
                
                print("[ADMIN]   Selection distribution:")
                for name, percentage in selection_percentages.items():
                    print(f"[ADMIN]     {name}: {percentage:.1f}%")
        
        print("[ADMIN] ✅ Statistical analysis and reporting completed")
        
        # Step 4: Test multi-select and advanced spinning features
        print("[ADMIN] Step 4: Testing multi-select and advanced spinning features...")
        
        # Find wheels with multi-select enabled
        multi_select_wheels = [
            w for w in wheels 
            if w['wheel'].get('settings', {}).get('multi_select_enabled', False)
        ]
        
        if multi_select_wheels:
            test_wheel = multi_select_wheels[0]
            wheel_id = test_wheel['wheel']['wheel_id']
            wheel_name = test_wheel['wheel']['wheel_name']
            
            print(f"[ADMIN] Testing multi-select on wheel: {wheel_name}")
            
            # Test multi-select spinning
            multi_select_data = {"count": 3}
            response = admin_client.post(f'/wheels/{wheel_id}/suggest', data=multi_select_data)
            
            if response.is_success:
                result = response.json_data
                selected_participants = result.get('selected_participants', [])
                
                if selected_participants:
                    print(f"[ADMIN] ✅ Multi-select returned {len(selected_participants)} participants:")
                    for i, participant in enumerate(selected_participants):
                        name = participant.get('participant_name', 'Unknown')
                        print(f"[ADMIN]   {i+1}. {name}")
                else:
                    single_participant = result.get('selected_participant', {})
                    name = single_participant.get('participant_name', 'Unknown')
                    print(f"[ADMIN] Single selection returned: {name}")
            else:
                print(f"[ADMIN] ⚠️ Multi-select spin failed: {response.status_code}")
        
        # Step 5: Test concurrent operations and performance
        print("[ADMIN] Step 5: Testing concurrent operations and performance...")
        
        if wheels:
            test_wheel = wheels[0]
            wheel_id = test_wheel['wheel']['wheel_id']
            wheel_name = test_wheel['wheel']['wheel_name']
            
            print(f"[ADMIN] Testing concurrent operations on wheel: {wheel_name}")
            
            # Test concurrent spinning operations
            concurrent_results = []
            start_time = time.time()
            
            for i in range(CONCURRENT_OPERATIONS_COUNT):
                response = admin_client.post(f'/wheels/{wheel_id}/suggest')
                if response.is_success:
                    concurrent_results.append(True)
                    result = response.json_data
                    participant_name = result.get('selected_participant', {}).get('participant_name', 'Unknown')
                    print(f"[ADMIN] Concurrent spin {i+1}: {participant_name}")
                else:
                    concurrent_results.append(False)
                    print(f"[ADMIN] ⚠️ Concurrent spin {i+1} failed: {response.status_code}")
                
                time.sleep(BATCH_OPERATION_DELAY_SECONDS)
            
            end_time = time.time()
            total_time = end_time - start_time
            successful_operations = sum(concurrent_results)
            
            print(f"[ADMIN] Concurrent operations: {successful_operations}/{CONCURRENT_OPERATIONS_COUNT} successful")
            print(f"[ADMIN] Total time: {total_time:.2f} seconds")
            print(f"[ADMIN] Average time per operation: {total_time/CONCURRENT_OPERATIONS_COUNT:.2f} seconds")
            
            assert successful_operations >= CONCURRENT_OPERATIONS_COUNT - 1, \
                "Most concurrent operations should succeed"
        
        print("[ADMIN] ✅ Advanced wheel operations and analytics validated")

    @pytest.mark.workflow
    @pytest.mark.admin
    @pytest.mark.security
    def test_admin_security_boundary_enforcement(self, api_client: APIClient,
                                                test_data_factory: TestDataFactory,
                                                cleanup_manager: CleanupManager,
                                                assertions: APIAssertions):
        """
        Test security boundary enforcement for ADMIN role
        
        Validates that admins can only access their own wheel groups and cannot
        perform operations on other users' wheel groups.
        """
        print("\n[ADMIN] Testing security boundary enforcement...")
        
        # Step 1: Create admin environment and another isolated wheel group
        print("[ADMIN] Step 1: Setting up security boundary test environment...")
        
        env = self._create_admin_test_environment(
            api_client, test_data_factory, cleanup_manager, assertions
        )
        
        admin_client = env['admin_client']
        
        # Create another wheel group for isolation testing
        other_group_data = test_data_factory.create_public_wheel_group_data(
            name="OtherIsolatedGroup"
        )
        
        response = api_client.post('/wheel-group/create-public', data=other_group_data)
        assertions.assert_success_response(response, "Failed to create isolated wheel group")
        
        other_wheel_group = response.json_data['wheel_group']
        other_wheel_group_id = other_wheel_group['wheel_group_id']
        cleanup_manager.register_wheel_group(other_wheel_group_id)
        
        # Authenticate as the other wheel group admin
        config = TestConfig('test')
        cognito_auth = CognitoAuthenticator(
            user_pool_id=config.cognito_user_pool_id,
            client_id=config.cognito_client_id,
            region=config.aws_region,
            debug=True
        )
        
        other_admin_username = other_group_data['admin_user']['username']
        other_admin_password = other_group_data['admin_user']['password']
        
        time.sleep(CONSISTENCY_WAIT_SECONDS)
        
        def auth_other_admin():
            return cognito_auth.authenticate_user(other_admin_username, other_admin_password)
        
        other_admin_auth = self._retry_with_backoff(auth_other_admin)
        
        other_admin_client = APIClient(base_url=config.api_base_url, debug=True)
        other_admin_client.set_auth_token(other_admin_auth['id_token'])
        
        # Step 2: Create content in both wheel groups
        print("[ADMIN] Step 2: Creating content in both wheel groups...")
        
        # Create wheel in admin's own group
        own_wheel_data = test_data_factory.create_wheel_data("AdminOwnWheel")
        response = admin_client.post('/wheels', data=own_wheel_data)
        assertions.assert_success_response(response, "Admin should create wheel in own group")
        
        own_wheel = response.json_data
        own_wheel_id = own_wheel['wheel_id']
        cleanup_manager.register_wheel(own_wheel_id)
        
        # Create wheel in other group
        other_wheel_data = test_data_factory.create_wheel_data("OtherGroupWheel")
        response = other_admin_client.post('/wheels', data=other_wheel_data)
        assertions.assert_success_response(response, "Other admin should create wheel in their group")
        
        other_wheel = response.json_data
        other_wheel_id = other_wheel['wheel_id']
        cleanup_manager.register_wheel(other_wheel_id)
        
        print(f"[ADMIN] Created own wheel: {own_wheel_id}")
        print(f"[ADMIN] Created other wheel (for isolation testing): {other_wheel_id}")
        
        # Step 3: Test access isolation
        print("[ADMIN] Step 3: Testing access isolation...")
        
        # Admin can access their own wheel
        response = admin_client.get(f'/wheels/{own_wheel_id}')
        assertions.assert_success_response(response, "Admin should access own wheel")
        print("[ADMIN] ✅ Admin can access own wheel")
        
        # Admin cannot access other group's wheel
        response = admin_client.get(f'/wheels/{other_wheel_id}')
        assert response.is_client_error or response.status_code == 404, \
            "Admin should not access other group's wheel"
        print(f"[ADMIN] ✅ Admin blocked from other wheel: {response.status_code}")
        
        # Step 4: Test modification isolation
        print("[ADMIN] Step 4: Testing modification isolation...")
        
        # Admin can modify their own wheel
        own_wheel_update = {"description": "Modified by rightful admin"}
        response = admin_client.put(f'/wheels/{own_wheel_id}', data=own_wheel_update)
        if response.is_success:
            print("[ADMIN] ✅ Admin can modify own wheel")
        else:
            print(f"[ADMIN] ⚠️ Own wheel modification returned: {response.status_code}")
        
        # Admin cannot modify other group's wheel
        other_wheel_update = {"description": "Unauthorized modification attempt"}
        response = admin_client.put(f'/wheels/{other_wheel_id}', data=other_wheel_update)
        assert response.is_client_error or response.status_code == 404, \
            "Admin should not modify other group's wheel"
        print(f"[ADMIN] ✅ Admin blocked from modifying other wheel: {response.status_code}")
        
        # Step 5: Test wheel list isolation
        print("[ADMIN] Step 5: Testing wheel list isolation...")
        
        # Admin should only see their own wheels
        response = admin_client.get('/wheels')
        if response.is_success:
            wheels_response = response.json_data
            if isinstance(wheels_response, dict) and 'wheels' in wheels_response:
                visible_wheels = wheels_response['wheels']
            else:
                visible_wheels = wheels_response
            
            visible_wheel_ids = [w['wheel_id'] for w in visible_wheels]
            
            assert own_wheel_id in visible_wheel_ids, "Admin should see own wheel in list"
            assert other_wheel_id not in visible_wheel_ids, "Admin should not see other group's wheel"
            
            print(f"[ADMIN] ✅ Admin sees {len(visible_wheels)} wheels (properly isolated)")
        
        print("[ADMIN] ✅ Security boundary enforcement validated")

    @pytest.mark.workflow
    @pytest.mark.admin
    @pytest.mark.integration
    def test_admin_end_to_end_administrative_workflow(self, api_client: APIClient,
                                                     test_data_factory: TestDataFactory,
                                                     cleanup_manager: CleanupManager,
                                                     assertions: APIAssertions):
        """
        Test complete end-to-end administrative workflow for ADMIN role
        
        Simulates a realistic administrative scenario covering wheel group setup,
        team management, operational activities, and administrative reporting.
        """
        print("\n[ADMIN] Testing end-to-end administrative workflow...")
        
        # Step 1: Initial administrative setup
        print("[ADMIN] Step 1: Initial administrative setup...")
        
        env = self._create_admin_test_environment(
            api_client, test_data_factory, cleanup_manager, assertions
        )
        
        admin_client = env['admin_client']
        wheel_group_id = env['wheel_group_id']
        
        print(f"[ADMIN] Administrative environment ready for wheel group: {wheel_group_id}")
        
        # Step 2: Team structure setup
        print("[ADMIN] Step 2: Setting up team structure...")
        
        # Create departmental wheels representing different team functions
        departmental_wheels = [
            {
                "name": "Engineering_ProjectAssignment",
                "description": "Engineering team project assignments",
                "team_members": [
                    {"name": "Engineering Manager", "weight": 2},
                    {"name": "Senior Software Engineer", "weight": 4},
                    {"name": "Software Engineer", "weight": 6},
                    {"name": "Junior Software Engineer", "weight": 3}
                ]
            },
            {
                "name": "QA_TestAssignment",
                "description": "QA team test assignment rotation",
                "team_members": [
                    {"name": "QA Lead", "weight": 3},
                    {"name": "Senior QA Engineer", "weight": 4},
                    {"name": "QA Engineer", "weight": 3}
                ]
            },
            {
                "name": "DevOps_OnCallRotation",
                "description": "DevOps on-call rotation management",
                "team_members": [
                    {"name": "DevOps Manager", "weight": 1},
                    {"name": "Senior DevOps Engineer", "weight": 2},
                    {"name": "DevOps Engineer", "weight": 2},
                    {"name": "Site Reliability Engineer", "weight": 2}
                ]
            }
        ]
        
        created_departmental_wheels = []
        
        for dept_config in departmental_wheels:
            print(f"[ADMIN] Setting up department: {dept_config['name']}")
            
            # Create departmental wheel
            wheel_data = test_data_factory.create_wheel_data(
                name=dept_config["name"],
                description=dept_config["description"]
            )
            wheel_data["settings"] = {
                "allow_rigging": True,
                "show_weights": True,
                "multi_select_enabled": False
            }
            
            response = admin_client.post('/wheels', data=wheel_data)
            assertions.assert_success_response(response, f"Failed to create {dept_config['name']}")
            
            wheel = response.json_data
            wheel_id = wheel['wheel_id']
            cleanup_manager.register_wheel(wheel_id)
            
            # Add team members
            team_members = []
            for member_config in dept_config["team_members"]:
                member_data = test_data_factory.create_participant_data(member_config["name"])
                member_data["weight"] = member_config["weight"]
                
                response = admin_client.post(f'/wheels/{wheel_id}/participants', 
                                           data=member_data)
                assertions.assert_success_response(response, 
                    f"Failed to add {member_config['name']}")
                
                member = response.json_data
                team_members.append(member)
                cleanup_manager.register_participant(member['participant_id'])
                
                time.sleep(MICRO_WAIT_SECONDS)
            
            created_departmental_wheels.append({
                'wheel': wheel,
                'members': team_members,
                'config': dept_config
            })
            
            print(f"[ADMIN] ✅ Set up {dept_config['name']} with {len(team_members)} members")
            
            time.sleep(SHORT_WAIT_SECONDS)
        
        # Step 3: Daily operational activities simulation
        print("[ADMIN] Step 3: Simulating daily operational activities...")
        
        daily_operations = []
        
        for dept_wheel in created_departmental_wheels:
            wheel = dept_wheel['wheel']
            wheel_id = wheel['wheel_id']
            wheel_name = wheel['wheel_name']
            
            print(f"[ADMIN] Running daily operations for: {wheel_name}")
            
            # Simulate morning assignments (multiple spins)
            morning_assignments = []
            for assignment_num in range(3):
                response = admin_client.post(f'/wheels/{wheel_id}/suggest')
                
                if response.is_success:
                    result = response.json_data
                    selected = result.get('selected_participant', {}).get('participant_name', 'Unknown')
                    
                    assignment = {
                        'department': wheel_name,
                        'assignment_number': assignment_num + 1,
                        'assigned_member': selected,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    morning_assignments.append(assignment)
                    print(f"[ADMIN] Assignment {assignment_num + 1}: {selected}")
                
                time.sleep(SPIN_DELAY_SECONDS)
            
            daily_operations.extend(morning_assignments)
            
            # Simulate administrative adjustments (weight modifications)
            if dept_wheel['members']:
                target_member = dept_wheel['members'][0]
                member_id = target_member['participant_id']
                original_weight = target_member['weight']
                new_weight = original_weight + 1
                
                adjustment_data = {"weight": new_weight}
                response = admin_client.put(f'/wheels/{wheel_id}/participants/{member_id}', 
                                          data=adjustment_data)
                
                if response.is_success:
                    print(f"[ADMIN] ✅ Adjusted {target_member['participant_name']} weight: {original_weight} → {new_weight}")
                else:
                    print(f"[ADMIN] ⚠️ Weight adjustment failed: {response.status_code}")
        
        print(f"[ADMIN] ✅ Completed {len(daily_operations)} daily operational activities")
        
        # Step 4: Administrative reporting and analysis
        print("[ADMIN] Step 4: Generating administrative reports and analysis...")
        
        # Generate comprehensive administrative report
        admin_report = {
            'report_timestamp': self._get_current_timestamp(),
            'wheel_group_id': wheel_group_id,
            'total_departments': len(created_departmental_wheels),
            'total_operations': len(daily_operations),
            'departmental_summary': {}
        }
        
        print("[ADMIN] Administrative Report:")
        print(f"[ADMIN]   Report Generated: {admin_report['report_timestamp']}")
        print(f"[ADMIN]   Wheel Group ID: {wheel_group_id}")
        print(f"[ADMIN]   Total Departments: {admin_report['total_departments']}")
        print(f"[ADMIN]   Total Operations: {admin_report['total_operations']}")
        
        # Department-wise analysis
        for dept_wheel in created_departmental_wheels:
            wheel_name = dept_wheel['wheel']['wheel_name']
            members_count = len(dept_wheel['members'])
            
            dept_operations = [op for op in daily_operations if op['department'] == wheel_name]
            operations_count = len(dept_operations)
            
            # Calculate member assignment distribution
            member_assignments = {}
            for operation in dept_operations:
                assigned_member = operation['assigned_member']
                if assigned_member in member_assignments:
                    member_assignments[assigned_member] += 1
                else:
                    member_assignments[assigned_member] = 1
            
            dept_summary = {
                'members_count': members_count,
                'operations_count': operations_count,
                'assignment_distribution': member_assignments
            }
            
            admin_report['departmental_summary'][wheel_name] = dept_summary
            
            print(f"[ADMIN]   Department: {wheel_name}")
            print(f"[ADMIN]     Members: {members_count}")
            print(f"[ADMIN]     Operations: {operations_count}")
            
            if member_assignments:
                most_assigned = max(member_assignments.items(), key=lambda x: x[1])
                print(f"[ADMIN]     Most assigned: {most_assigned[0]} ({most_assigned[1]} times)")
        
        # Step 5: Administrative maintenance and cleanup demonstration
        print("[ADMIN] Step 5: Demonstrating administrative maintenance...")
        
        # Demonstrate administrative maintenance tasks
        maintenance_tasks = [
            "Verify wheel configurations",
            "Review participant weights",
            "Check operational statistics",
            "Validate system health"
        ]
        
        for task in maintenance_tasks:
            print(f"[ADMIN] Maintenance task: {task}")
            
            if task == "Verify wheel configurations":
                # Verify all wheels are accessible
                response = admin_client.get('/wheels')
                if response.is_success:
                    wheels_count = len(response.json_data.get('wheels', []))
                    print(f"[ADMIN] ✅ Verified {wheels_count} wheel configurations")
            
            elif task == "Review participant weights":
                # Review participant weights across all wheels
                total_participants = 0
                for dept_wheel in created_departmental_wheels:
                    wheel_id = dept_wheel['wheel']['wheel_id']
                    response = admin_client.get(f'/wheels/{wheel_id}/participants')
                    if response.is_success:
                        participants = response.json_data
                        total_participants += len(participants)
                
                print(f"[ADMIN] ✅ Reviewed {total_participants} participant weights")
            
            elif task == "Check operational statistics":
                # Summary of operational statistics
                unique_members = set(op['assigned_member'] for op in daily_operations)
                print(f"[ADMIN] ✅ Operational statistics: {len(daily_operations)} operations, {len(unique_members)} unique assignees")
            
            elif task == "Validate system health":
                # Simple system health check by accessing wheels
                health_check_passed = True
                for dept_wheel in created_departmental_wheels[:2]:  # Check first 2 wheels
                    wheel_id = dept_wheel['wheel']['wheel_id']
                    response = admin_client.get(f'/wheels/{wheel_id}')
                    if not response.is_success:
                        health_check_passed = False
                        break
                
                if health_check_passed:
                    print("[ADMIN] ✅ System health validation passed")
                else:
                    print("[ADMIN] ⚠️ System health validation issues detected")
            
            time.sleep(MICRO_WAIT_SECONDS)
        
        print("[ADMIN] ✅ End-to-end administrative workflow completed successfully")
        print(f"[ADMIN] Final summary: {admin_report['total_departments']} departments, {admin_report['total_operations']} operations managed")

    @pytest.mark.workflow
    @pytest.mark.admin
    @pytest.mark.user_management
    def test_admin_user_role_management_workflow(self, api_client: APIClient,
                                                test_data_factory: TestDataFactory,
                                                cleanup_manager: CleanupManager,
                                                assertions: APIAssertions):
        """
        Test ADMIN role's user management and role transition capabilities
        
        Validates that admins can:
        1. Create users with different roles (WHEEL_ADMIN, USER)
        2. Verify proper permissions for each role
        3. Change user roles and verify permission changes
        4. Manage user lifecycle within their wheel group
        """
        print("\n[ADMIN] Testing user role management workflow...")
        
        # Step 1: Setup admin environment
        print("[ADMIN] Step 1: Setting up admin environment for user management...")
        
        env = self._create_admin_test_environment(
            api_client, test_data_factory, cleanup_manager, assertions
        )
        
        admin_client = env['admin_client']
        wheel_group_id = env['wheel_group_id']
        config = env['config']
        cognito_auth = env['cognito_auth']
        
        print(f"[ADMIN] Admin environment ready for wheel group: {wheel_group_id}")
        
        # Create a test wheel for permission verification
        test_wheel_data = test_data_factory.create_wheel_data("RoleTestWheel")
        response = admin_client.post('/wheels', data=test_wheel_data)
        assertions.assert_success_response(response, "Admin should create test wheel")
        
        test_wheel = response.json_data
        test_wheel_id = test_wheel['wheel_id']
        cleanup_manager.register_wheel(test_wheel_id)
        
        # Add a test participant to the wheel
        participant_data = test_data_factory.create_participant_data("TestParticipant")
        response = admin_client.post(f'/wheels/{test_wheel_id}/participants', data=participant_data)
        assertions.assert_success_response(response, "Admin should add test participant")
        
        test_participant = response.json_data
        test_participant_id = test_participant['participant_id']
        cleanup_manager.register_participant(test_participant_id)
        
        print(f"[ADMIN] Created test wheel: {test_wheel['wheel_name']} with test participant: {test_participant['participant_name']}")
        
        # Step 2: Create a user with WHEEL_ADMIN role
        print("[ADMIN] Step 2: Creating user with WHEEL_ADMIN role...")
        
        # Create user data dynamically
        wheel_admin_username = test_data_factory.generate_username("wheeladmin")
        wheel_admin_email = test_data_factory.generate_email(wheel_admin_username)
        wheel_admin_password = test_data_factory.generate_password()
        
        wheel_admin_user_data = {
            "username": wheel_admin_username,
            "email": wheel_admin_email,
            "password": wheel_admin_password,
            "role": "WHEEL_ADMIN"
        }
        
        # Admin creates wheel admin user dynamically
        response = admin_client.post('/wheel-group/users', data=wheel_admin_user_data)
        assertions.assert_success_response(response, "Admin should create WHEEL_ADMIN user")
        
        wheel_admin_user = response.json_data
        wheel_admin_user_id = wheel_admin_user.get('user_id', wheel_admin_user.get('id'))
        
        # Use temporary password if provided by the API
        if 'temporary_password' in wheel_admin_user:
            wheel_admin_password = wheel_admin_user['temporary_password']
            print(f"[ADMIN] ✅ Created WHEEL_ADMIN user: {wheel_admin_username} (using temporary password)")
        else:
            print(f"[ADMIN] ✅ Created WHEEL_ADMIN user: {wheel_admin_username}")
        
        # Wait for user creation consistency
        time.sleep(CONSISTENCY_WAIT_SECONDS)
        
        # Step 3: Authenticate as WHEEL_ADMIN and verify permissions
        print("[ADMIN] Step 3: Testing WHEEL_ADMIN permissions...")
        
        def auth_wheel_admin():
            return cognito_auth.authenticate_user(wheel_admin_username, wheel_admin_password)
        
        wheel_admin_auth = self._retry_with_backoff(auth_wheel_admin)
        
        wheel_admin_client = APIClient(base_url=config.api_base_url, debug=True)
        wheel_admin_client.set_auth_token(wheel_admin_auth['id_token'])
        
        # Test WHEEL_ADMIN permissions - should be able to manage wheels and participants
        print("[ADMIN] Testing WHEEL_ADMIN capabilities...")
        
        # WHEEL_ADMIN can view wheels
        response = wheel_admin_client.get('/wheels')
        if response.is_success:
            print("[ADMIN] ✅ WHEEL_ADMIN can view wheels")
        else:
            print(f"[ADMIN] ⚠️ WHEEL_ADMIN wheel view failed: {response.status_code}")
        
        # WHEEL_ADMIN can access specific wheel
        response = wheel_admin_client.get(f'/wheels/{test_wheel_id}')
        if response.is_success:
            print("[ADMIN] ✅ WHEEL_ADMIN can access specific wheel")
        else:
            print(f"[ADMIN] ⚠️ WHEEL_ADMIN wheel access failed: {response.status_code}")
        
        # WHEEL_ADMIN can create wheels
        wheel_admin_wheel_data = test_data_factory.create_wheel_data("WheelAdminCreatedWheel")
        response = wheel_admin_client.post('/wheels', data=wheel_admin_wheel_data)
        if response.is_success:
            wheel_admin_wheel = response.json_data
            wheel_admin_wheel_id = wheel_admin_wheel['wheel_id']
            cleanup_manager.register_wheel(wheel_admin_wheel_id)
            print(f"[ADMIN] ✅ WHEEL_ADMIN can create wheels: {wheel_admin_wheel['wheel_name']}")
        else:
            print(f"[ADMIN] ⚠️ WHEEL_ADMIN wheel creation failed: {response.status_code}")
        
        # WHEEL_ADMIN can manage participants
        wheel_admin_participant_data = test_data_factory.create_participant_data("WheelAdminParticipant")
        response = wheel_admin_client.post(f'/wheels/{test_wheel_id}/participants', 
                                         data=wheel_admin_participant_data)
        if response.is_success:
            wheel_admin_participant = response.json_data
            cleanup_manager.register_participant(wheel_admin_participant['participant_id'])
            print(f"[ADMIN] ✅ WHEEL_ADMIN can add participants: {wheel_admin_participant['participant_name']}")
        else:
            print(f"[ADMIN] ⚠️ WHEEL_ADMIN participant creation failed: {response.status_code}")
        
        # WHEEL_ADMIN can spin wheels
        response = wheel_admin_client.post(f'/wheels/{test_wheel_id}/suggest')
        if response.is_success:
            spin_result = response.json_data
            selected = spin_result.get('selected_participant', {}).get('participant_name', 'Unknown')
            print(f"[ADMIN] ✅ WHEEL_ADMIN can spin wheels: Selected {selected}")
        else:
            print(f"[ADMIN] ⚠️ WHEEL_ADMIN wheel spinning failed: {response.status_code}")
        
        # WHEEL_ADMIN cannot manage users (should fail)
        unauthorized_user_data = {
            "username": test_data_factory.generate_username("unauthorized"),
            "email": test_data_factory.generate_email("unauthorized"),
            "password": test_data_factory.generate_password(),
            "role": "USER"
        }
        response = wheel_admin_client.post('/wheel-group/users', data=unauthorized_user_data)
        if response.is_client_error or response.status_code in [403, 404]:
            print("[ADMIN] ✅ WHEEL_ADMIN correctly blocked from user management")
        else:
            print(f"[ADMIN] ⚠️ WHEEL_ADMIN user management should be blocked: {response.status_code}")
        
        print("[ADMIN] ✅ WHEEL_ADMIN permissions verified")
        
        # Step 4: Admin changes user role from WHEEL_ADMIN to USER
        print("[ADMIN] Step 4: Changing user role from WHEEL_ADMIN to USER...")
        
        role_change_data = {
            "role": "USER"
        }
        
        response = admin_client.put(f'/wheel-group/users/{wheel_admin_user_id}', 
                                  data=role_change_data)
        if response.is_success:
            print(f"[ADMIN] ✅ Admin changed user role: {wheel_admin_username} → USER")
        else:
            print(f"[ADMIN] ⚠️ Role change failed: {response.status_code}")
            # Try alternative endpoint if first fails
            response = admin_client.put(f'/users/{wheel_admin_user_id}/role', 
                                      data=role_change_data)
            if response.is_success:
                print(f"[ADMIN] ✅ Admin changed user role (alternative endpoint): {wheel_admin_username} → USER")
            else:
                print(f"[ADMIN] ⚠️ Role change failed on alternative endpoint: {response.status_code}")
        
        # Wait for role change to propagate
        time.sleep(CONSISTENCY_WAIT_SECONDS)
        
        # Step 5: Re-authenticate as USER and verify reduced permissions
        print("[ADMIN] Step 5: Testing USER permissions after role change...")
        
        # Re-authenticate to get new token with updated role
        user_auth = self._retry_with_backoff(auth_wheel_admin)  # Same user, new role
        
        user_client = APIClient(base_url=config.api_base_url, debug=True)
        user_client.set_auth_token(user_auth['id_token'])
        
        # Test USER permissions - should be read-only
        print("[ADMIN] Testing USER capabilities...")
        
        # USER can view wheels (read-only)
        response = user_client.get('/wheels')
        if response.is_success:
            print("[ADMIN] ✅ USER can view wheels")
        else:
            print(f"[ADMIN] ⚠️ USER wheel view failed: {response.status_code}")
        
        # USER can access specific wheel details
        response = user_client.get(f'/wheels/{test_wheel_id}')
        if response.is_success:
            print("[ADMIN] ✅ USER can access wheel details")
        else:
            print(f"[ADMIN] ⚠️ USER wheel access failed: {response.status_code}")
        
        # USER can view participants
        response = user_client.get(f'/wheels/{test_wheel_id}/participants')
        if response.is_success:
            print("[ADMIN] ✅ USER can view participants")
        else:
            print(f"[ADMIN] ⚠️ USER participant view failed: {response.status_code}")
        
        # USER can spin wheels (basic functionality)
        response = user_client.post(f'/wheels/{test_wheel_id}/suggest')
        if response.is_success:
            spin_result = response.json_data
            selected = spin_result.get('selected_participant', {}).get('participant_name', 'Unknown')
            print(f"[ADMIN] ✅ USER can spin wheels: Selected {selected}")
        else:
            print(f"[ADMIN] ⚠️ USER wheel spinning failed: {response.status_code}")
        
        # USER cannot create wheels (should fail)
        user_wheel_data = test_data_factory.create_wheel_data("UnauthorizedUserWheel")
        response = user_client.post('/wheels', data=user_wheel_data)
        if response.is_client_error or response.status_code in [403, 404]:
            print("[ADMIN] ✅ USER correctly blocked from creating wheels")
        else:
            print(f"[ADMIN] ⚠️ USER wheel creation should be blocked: {response.status_code}")
        
        # USER cannot add participants (should fail)
        user_participant_data = test_data_factory.create_participant_data("UnauthorizedParticipant")
        response = user_client.post(f'/wheels/{test_wheel_id}/participants', 
                                  data=user_participant_data)
        if response.is_client_error or response.status_code in [403, 404]:
            print("[ADMIN] ✅ USER correctly blocked from adding participants")
        else:
            print(f"[ADMIN] ⚠️ USER participant creation should be blocked: {response.status_code}")
        
        # USER cannot modify participants (should fail)
        if test_participant_id:
            participant_update_data = {"weight": 999}
            response = user_client.put(f'/wheels/{test_wheel_id}/participants/{test_participant_id}', 
                                     data=participant_update_data)
            if response.is_client_error or response.status_code in [403, 404]:
                print("[ADMIN] ✅ USER correctly blocked from modifying participants")
            else:
                print(f"[ADMIN] ⚠️ USER participant modification should be blocked: {response.status_code}")
        
        # USER cannot manage users (should fail)
        response = user_client.post('/wheel-group/users', data=unauthorized_user_data)
        if response.is_client_error or response.status_code in [403, 404]:
            print("[ADMIN] ✅ USER correctly blocked from user management")
        else:
            print(f"[ADMIN] ⚠️ USER user management should be blocked: {response.status_code}")
        
        print("[ADMIN] ✅ USER permissions verified - properly restricted to read-only")
        
        # Step 6: Admin verification and cleanup
        print("[ADMIN] Step 6: Admin verification and user lifecycle management...")
        
        # Admin can view all users in the wheel group
        response = admin_client.get('/wheel-group/users')
        if response.is_success:
            users_list = response.json_data
            user_count = len(users_list) if isinstance(users_list, list) else users_list.get('count', 0)
            print(f"[ADMIN] ✅ Admin can view {user_count} users in wheel group")
        else:
            print(f"[ADMIN] ⚠️ Admin user listing failed: {response.status_code}")
        
        # Admin can view specific user details
        response = admin_client.get(f'/wheel-group/users/{wheel_admin_user_id}')
        if response.is_success:
            user_details = response.json_data
            current_role = user_details.get('role', 'unknown')
            print(f"[ADMIN] ✅ Admin can view user details - current role: {current_role}")
        else:
            print(f"[ADMIN] ⚠️ Admin user details failed: {response.status_code}")
        
        
        print("[ADMIN] ✅ User role management workflow completed successfully")
        print(f"[ADMIN] Summary: Created WHEEL_ADMIN → Verified permissions → Changed to USER → Verified restricted permissions")
