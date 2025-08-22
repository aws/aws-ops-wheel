"""
Cleanup Utilities for AWS Ops Wheel v2 Integration Tests
"""
import time
from typing import List, Dict, Any, Optional, Tuple
from .api_client import APIClient, APIResponse
from .auth_manager import AuthManager


class CleanupManager:
    """Manages cleanup of test data and resources"""
    
    def __init__(self, api_client: APIClient, auth_manager: AuthManager, 
                 cleanup_enabled: bool = True, debug: bool = False):
        """
        Initialize cleanup manager
        
        Args:
            api_client: API client instance
            auth_manager: Authentication manager
            cleanup_enabled: Whether cleanup is enabled
            debug: Enable debug logging
        """
        self.api_client = api_client
        self.auth_manager = auth_manager
        self.cleanup_enabled = cleanup_enabled
        self.debug = debug
        
        # Track created resources for cleanup
        self._created_wheel_groups: List[str] = []
        self._created_wheels: List[str] = []
        self._created_participants: List[str] = []
        self._created_users: List[str] = []
        
        # Failed cleanup tracking
        self._failed_cleanups: List[Dict[str, Any]] = []
        
    def _log(self, message: str):
        """Log debug message if debug is enabled"""
        if self.debug:
            print(f"[CLEANUP] {message}")
    
    def register_wheel_group(self, wheel_group_id: str):
        """
        Register wheel group for cleanup
        
        Args:
            wheel_group_id: Wheel group ID to track
        """
        if wheel_group_id not in self._created_wheel_groups:
            self._created_wheel_groups.append(wheel_group_id)
            self._log(f"Registered wheel group for cleanup: {wheel_group_id}")
    
    def register_wheel(self, wheel_id: str):
        """
        Register wheel for cleanup
        
        Args:
            wheel_id: Wheel ID to track
        """
        if wheel_id not in self._created_wheels:
            self._created_wheels.append(wheel_id)
            self._log(f"Registered wheel for cleanup: {wheel_id}")
    
    def register_participant(self, participant_id: str):
        """
        Register participant for cleanup
        
        Args:
            participant_id: Participant ID to track
        """
        if participant_id not in self._created_participants:
            self._created_participants.append(participant_id)
            self._log(f"Registered participant for cleanup: {participant_id}")
    
    def register_user(self, user_id: str):
        """
        Register user for cleanup
        
        Args:
            user_id: User ID to track
        """
        if user_id not in self._created_users:
            self._created_users.append(user_id)
            self._log(f"Registered user for cleanup: {user_id}")
    
    def delete_participant(self, participant_id: str) -> bool:
        """
        Delete a participant
        
        Args:
            participant_id: Participant ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping participant: {participant_id}")
            return True
        
        try:
            self._log(f"Deleting participant: {participant_id}")
            response = self.api_client.delete(f'/app/api/v2/participants/{participant_id}')
            
            if response.is_success:
                self._log(f"Successfully deleted participant: {participant_id}")
                if participant_id in self._created_participants:
                    self._created_participants.remove(participant_id)
                return True
            else:
                self._log(f"Failed to delete participant {participant_id}: {response.status_code}")
                self._record_failed_cleanup('participant', participant_id, response.status_code, response.text)
                return False
                
        except Exception as e:
            self._log(f"Exception deleting participant {participant_id}: {e}")
            self._record_failed_cleanup('participant', participant_id, None, str(e))
            return False
    
    def delete_wheel(self, wheel_id: str) -> bool:
        """
        Delete a wheel and its participants
        
        Args:
            wheel_id: Wheel ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping wheel: {wheel_id}")
            return True
        
        try:
            # First, delete all participants in the wheel
            self._log(f"Getting participants for wheel: {wheel_id}")
            response = self.api_client.get(f'/app/api/v2/wheels/{wheel_id}/participants')
            
            if response.is_success and response.json_data:
                participants = response.json_data.get('participants', [])
                for participant in participants:
                    participant_id = participant.get('participant_id')
                    if participant_id:
                        self.delete_participant(participant_id)
            
            # Then delete the wheel itself
            self._log(f"Deleting wheel: {wheel_id}")
            response = self.api_client.delete(f'/app/api/v2/wheels/{wheel_id}')
            
            if response.is_success:
                self._log(f"Successfully deleted wheel: {wheel_id}")
                if wheel_id in self._created_wheels:
                    self._created_wheels.remove(wheel_id)
                return True
            else:
                self._log(f"Failed to delete wheel {wheel_id}: {response.status_code}")
                self._record_failed_cleanup('wheel', wheel_id, response.status_code, response.text)
                return False
                
        except Exception as e:
            self._log(f"Exception deleting wheel {wheel_id}: {e}")
            self._record_failed_cleanup('wheel', wheel_id, None, str(e))
            return False
    
    def delete_wheel_group(self, wheel_group_id: str) -> bool:
        """
        Delete a wheel group and all its contents
        
        Args:
            wheel_group_id: Wheel group ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping wheel group: {wheel_group_id}")
            return True
        
        try:
            # First, get all wheels in the wheel group
            self._log(f"Getting wheels for wheel group: {wheel_group_id}")
            response = self.api_client.get(f'/app/api/v2/wheel-group/{wheel_group_id}/wheels')
            
            if response.is_success and response.json_data:
                wheels = response.json_data.get('wheels', [])
                for wheel in wheels:
                    wheel_id = wheel.get('wheel_id')
                    if wheel_id:
                        self.delete_wheel(wheel_id)
            
            # Then delete the wheel group
            self._log(f"Deleting wheel group: {wheel_group_id}")
            response = self.api_client.delete(f'/app/api/v2/wheel-group/{wheel_group_id}')
            
            if response.is_success:
                self._log(f"Successfully deleted wheel group: {wheel_group_id}")
                if wheel_group_id in self._created_wheel_groups:
                    self._created_wheel_groups.remove(wheel_group_id)
                return True
            else:
                self._log(f"Failed to delete wheel group {wheel_group_id}: {response.status_code}")
                self._record_failed_cleanup('wheel_group', wheel_group_id, response.status_code, response.text)
                return False
                
        except Exception as e:
            self._log(f"Exception deleting wheel group {wheel_group_id}: {e}")
            self._record_failed_cleanup('wheel_group', wheel_group_id, None, str(e))
            return False
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user (requires admin authentication)
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping user: {user_id}")
            return True
        
        if not self.auth_manager.is_admin():
            self._log(f"Not admin, cannot delete user: {user_id}")
            return False
        
        try:
            self._log(f"Deleting user: {user_id}")
            response = self.api_client.delete(f'/app/api/v2/admin/users/{user_id}')
            
            if response.is_success:
                self._log(f"Successfully deleted user: {user_id}")
                if user_id in self._created_users:
                    self._created_users.remove(user_id)
                return True
            else:
                self._log(f"Failed to delete user {user_id}: {response.status_code}")
                self._record_failed_cleanup('user', user_id, response.status_code, response.text)
                return False
                
        except Exception as e:
            self._log(f"Exception deleting user {user_id}: {e}")
            self._record_failed_cleanup('user', user_id, None, str(e))
            return False
    
    def cleanup_all_registered_resources(self) -> Tuple[int, int]:
        """
        Clean up all registered resources
        
        Returns:
            Tuple of (successful_cleanups, failed_cleanups)
        """
        if not self.cleanup_enabled:
            self._log("Cleanup disabled, skipping all resource cleanup")
            return 0, 0
        
        self._log("Starting cleanup of all registered resources")
        successful = 0
        failed = 0
        
        # Clean up in reverse dependency order
        # 1. Participants (no dependencies)
        for participant_id in self._created_participants.copy():
            if self.delete_participant(participant_id):
                successful += 1
            else:
                failed += 1
        
        # 2. Wheels (depend on participants being cleaned up)
        for wheel_id in self._created_wheels.copy():
            if self.delete_wheel(wheel_id):
                successful += 1
            else:
                failed += 1
        
        # 3. Wheel groups (depend on wheels being cleaned up)
        for wheel_group_id in self._created_wheel_groups.copy():
            if self.delete_wheel_group(wheel_group_id):
                successful += 1
            else:
                failed += 1
        
        # 4. Users (can be cleaned up independently)
        for user_id in self._created_users.copy():
            if self.delete_user(user_id):
                successful += 1
            else:
                failed += 1
        
        self._log(f"Cleanup completed: {successful} successful, {failed} failed")
        return successful, failed
    
    def cleanup_test_data_by_pattern(self, pattern: str) -> Tuple[int, int]:
        """
        Clean up test data by name pattern (requires admin authentication)
        
        Args:
            pattern: Pattern to match (e.g., "IntegTest", "TestUser")
            
        Returns:
            Tuple of (successful_cleanups, failed_cleanups)
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping pattern cleanup: {pattern}")
            return 0, 0
        
        if not self.auth_manager.is_admin():
            self._log("Not admin, cannot perform pattern cleanup")
            return 0, 0
        
        self._log(f"Cleaning up test data with pattern: {pattern}")
        successful = 0
        failed = 0
        
        try:
            # Get all wheel groups and find matches
            response = self.api_client.get('/app/api/v2/admin/wheel-groups')
            
            if response.is_success and response.json_data:
                wheel_groups = response.json_data.get('wheel_groups', [])
                
                for wheel_group in wheel_groups:
                    name = wheel_group.get('wheel_group_name', '')
                    wheel_group_id = wheel_group.get('wheel_group_id')
                    
                    if pattern in name and wheel_group_id:
                        self._log(f"Found test wheel group to cleanup: {name}")
                        if self.delete_wheel_group(wheel_group_id):
                            successful += 1
                        else:
                            failed += 1
            
        except Exception as e:
            self._log(f"Exception during pattern cleanup: {e}")
            failed += 1
        
        self._log(f"Pattern cleanup completed: {successful} successful, {failed} failed")
        return successful, failed
    
    def _record_failed_cleanup(self, resource_type: str, resource_id: str, 
                              status_code: Optional[int], error_message: str):
        """Record failed cleanup for reporting"""
        self._failed_cleanups.append({
            'resource_type': resource_type,
            'resource_id': resource_id,
            'status_code': status_code,
            'error_message': error_message,
            'timestamp': time.time()
        })
    
    def get_failed_cleanups(self) -> List[Dict[str, Any]]:
        """
        Get list of failed cleanups
        
        Returns:
            List of failed cleanup records
        """
        return self._failed_cleanups.copy()
    
    def get_remaining_resources(self) -> Dict[str, List[str]]:
        """
        Get remaining tracked resources
        
        Returns:
            Dictionary of remaining resources by type
        """
        return {
            'wheel_groups': self._created_wheel_groups.copy(),
            'wheels': self._created_wheels.copy(),
            'participants': self._created_participants.copy(),
            'users': self._created_users.copy()
        }
    
    def has_remaining_resources(self) -> bool:
        """
        Check if there are remaining resources to clean up
        
        Returns:
            True if resources remain
        """
        remaining = self.get_remaining_resources()
        return any(resources for resources in remaining.values())
    
    def verify_cleanup_complete(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify that cleanup is complete by checking if resources still exist
        
        Returns:
            Tuple of (is_complete, verification_results)
        """
        if not self.cleanup_enabled:
            return True, {'cleanup_disabled': True}
        
        self._log("Verifying cleanup completion")
        results = {
            'verified_deleted': [],
            'still_exist': [],
            'verification_errors': []
        }
        
        # Check remaining wheel groups
        for wheel_group_id in self._created_wheel_groups:
            try:
                response = self.api_client.get(f'/app/api/v2/wheel-group/{wheel_group_id}')
                if response.status_code == 404:
                    results['verified_deleted'].append(f"wheel_group:{wheel_group_id}")
                elif response.is_success:
                    results['still_exist'].append(f"wheel_group:{wheel_group_id}")
            except Exception as e:
                results['verification_errors'].append(f"wheel_group:{wheel_group_id}:{e}")
        
        # Check remaining wheels
        for wheel_id in self._created_wheels:
            try:
                response = self.api_client.get(f'/app/api/v2/wheels/{wheel_id}')
                if response.status_code == 404:
                    results['verified_deleted'].append(f"wheel:{wheel_id}")
                elif response.is_success:
                    results['still_exist'].append(f"wheel:{wheel_id}")
            except Exception as e:
                results['verification_errors'].append(f"wheel:{wheel_id}:{e}")
        
        is_complete = len(results['still_exist']) == 0
        self._log(f"Cleanup verification: {'COMPLETE' if is_complete else 'INCOMPLETE'}")
        
        return is_complete, results
    
    def force_cleanup_by_admin(self) -> Tuple[int, int]:
        """
        Force cleanup of all test data using admin privileges
        
        Returns:
            Tuple of (successful_cleanups, failed_cleanups)
        """
        if not self.cleanup_enabled:
            self._log("Cleanup disabled, skipping force cleanup")
            return 0, 0
        
        if not self.auth_manager.is_admin():
            self._log("Not admin, cannot perform force cleanup")
            return 0, 0
        
        self._log("Performing force cleanup using admin privileges")
        
        # Clean up by common test patterns
        patterns = ['IntegTest', 'PublicTest', 'testuser', 'Test Participant']
        total_successful = 0
        total_failed = 0
        
        for pattern in patterns:
            successful, failed = self.cleanup_test_data_by_pattern(pattern)
            total_successful += successful
            total_failed += failed
        
        return total_successful, total_failed
