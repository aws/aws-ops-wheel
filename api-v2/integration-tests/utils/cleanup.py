"""
Enhanced Cleanup Utilities for AWS Ops Wheel v2 Integration Tests

This module manages cleanup of test data and resources using direct AWS SDK operations
for reliability and performance, while maintaining the existing pytest integration pattern.
"""
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from .aws_cleanup_core import AWSResourceCleanupOrchestrator


class CleanupManager:
    """Manages cleanup of test data and resources using AWS SDK"""
    
    def __init__(self, cleanup_enabled: bool = True, debug: bool = False, dry_run: bool = False):
        """
        Initialize cleanup manager with AWS SDK backend
        
        Args:
            cleanup_enabled: Whether cleanup is enabled
            debug: Enable debug logging
            dry_run: If True, only show what would be deleted without actually deleting
        """
        self.cleanup_enabled = cleanup_enabled
        self.debug = debug
        self.dry_run = dry_run
        
        # Initialize AWS SDK cleanup orchestrator
        self.aws_orchestrator = AWSResourceCleanupOrchestrator(aws_region='us-west-2', dry_run=dry_run, debug=debug)
        
        # Track created resources for cleanup (same as before)
        self._created_wheel_groups: List[str] = []
        self._created_wheels: List[str] = []
        self._created_participants: List[str] = []
        self._created_users: List[str] = []
        self._created_cognito_users: List[str] = []  # NEW: Cognito user tracking
        
        # Custom cleanup functions (for backward compatibility)
        self._custom_cleanup_functions: List[Callable] = []
        
        # Enhanced metadata tracking for better cleanup
        self._resource_metadata: Dict[str, Dict] = {
            'participants': {},  # participant_id -> {wheel_id, wheel_group_id, timestamp}
            'wheels': {},        # wheel_id -> {wheel_group_id, timestamp}
            'wheel_groups': {},  # wheel_group_id -> {timestamp}
            'users': {},         # user_id -> {timestamp}
            'cognito_users': {}  # username -> {email, timestamp}
        }
        
        # Cleanup results tracking
        self._cleanup_results: Dict[str, Any] = {
            'successful_deletes': 0,
            'failed_deletes': 0,
            'errors': []
        }
    
    def _log(self, message: str):
        """Log debug message if debug is enabled"""
        if self.debug:
            print(f"[CLEANUP] {message}")
    
    # ========================================================================
    # RESOURCE REGISTRATION METHODS (same signatures as before - no test changes needed)
    # ========================================================================
    
    def register_wheel_group(self, wheel_group_id: str):
        """
        Register wheel group for cleanup
        
        Args:
            wheel_group_id: Wheel group ID to track
        """
        if wheel_group_id not in self._created_wheel_groups:
            self._created_wheel_groups.append(wheel_group_id)
            self._resource_metadata['wheel_groups'][wheel_group_id] = {
                'timestamp': time.time()
            }
            self._log(f"Registered wheel group for cleanup: {wheel_group_id}")
    
    def register_wheel(self, wheel_id: str, wheel_group_id: str = None):
        """
        Register wheel for cleanup
        
        Args:
            wheel_id: Wheel ID to track
            wheel_group_id: Optional wheel group ID for context
        """
        if wheel_id not in self._created_wheels:
            self._created_wheels.append(wheel_id)
            self._resource_metadata['wheels'][wheel_id] = {
                'wheel_group_id': wheel_group_id,
                'timestamp': time.time()
            }
            self._log(f"Registered wheel for cleanup: {wheel_id}")
    
    def register_participant(self, participant_id: str, wheel_id: str = None, wheel_group_id: str = None):
        """
        Register participant for cleanup
        
        Args:
            participant_id: Participant ID to track
            wheel_id: Optional wheel ID for context
            wheel_group_id: Optional wheel group ID for context
        """
        if participant_id not in self._created_participants:
            self._created_participants.append(participant_id)
            self._resource_metadata['participants'][participant_id] = {
                'wheel_id': wheel_id,
                'wheel_group_id': wheel_group_id,
                'timestamp': time.time()
            }
            self._log(f"Registered participant for cleanup: {participant_id}")
    
    def register_user(self, user_id: str):
        """
        Register user for cleanup
        
        Args:
            user_id: User ID to track
        """
        if user_id not in self._created_users:
            self._created_users.append(user_id)
            self._resource_metadata['users'][user_id] = {
                'timestamp': time.time()
            }
            self._log(f"Registered user for cleanup: {user_id}")
    
    def register_cognito_user(self, username: str, email: str = None):
        """
        Register Cognito user for cleanup (NEW)
        
        Args:
            username: Cognito username to track
            email: Optional email for verification
        """
        if username not in self._created_cognito_users:
            self._created_cognito_users.append(username)
            self._resource_metadata['cognito_users'][username] = {
                'email': email,
                'timestamp': time.time()
            }
            self._log(f"Registered Cognito user for cleanup: {username}")
    
    def register_custom_cleanup(self, cleanup_function: Callable):
        """
        Register custom cleanup function for backward compatibility
        
        Args:
            cleanup_function: Function to call during cleanup
        """
        self._custom_cleanup_functions.append(cleanup_function)
        self._log(f"Registered custom cleanup function: {cleanup_function.__name__}")
    
    # ========================================================================
    # LEGACY COMPATIBILITY METHODS (maintain existing method signatures)
    # ========================================================================
    
    def delete_participant(self, participant_id: str) -> bool:
        """
        Legacy method - delete a single participant immediately
        
        Args:
            participant_id: Participant ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping participant: {participant_id}")
            return True
        
        self._log(f"Legacy delete_participant called for: {participant_id}")
        
        # Use AWS SDK to delete immediately
        results = self.aws_orchestrator.cleanup_registered_resources(
            participant_ids=[participant_id]
        )
        
        success = results['details'].get('participants', {}).get('successful', 0) > 0
        if success:
            # Remove from tracking lists
            if participant_id in self._created_participants:
                self._created_participants.remove(participant_id)
            if participant_id in self._resource_metadata['participants']:
                del self._resource_metadata['participants'][participant_id]
        
        return success
    
    def delete_wheel(self, wheel_id: str) -> bool:
        """
        Legacy method - delete a single wheel immediately
        
        Args:
            wheel_id: Wheel ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping wheel: {wheel_id}")
            return True
        
        self._log(f"Legacy delete_wheel called for: {wheel_id}")
        
        # Use AWS SDK to delete immediately
        results = self.aws_orchestrator.cleanup_registered_resources(
            wheel_ids=[wheel_id]
        )
        
        success = results['details'].get('wheels', {}).get('successful', 0) > 0
        if success:
            # Remove from tracking lists
            if wheel_id in self._created_wheels:
                self._created_wheels.remove(wheel_id)
            if wheel_id in self._resource_metadata['wheels']:
                del self._resource_metadata['wheels'][wheel_id]
        
        return success
    
    def delete_wheel_group(self, wheel_group_id: str) -> bool:
        """
        Legacy method - delete a single wheel group immediately
        
        Args:
            wheel_group_id: Wheel group ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping wheel group: {wheel_group_id}")
            return True
        
        self._log(f"Legacy delete_wheel_group called for: {wheel_group_id}")
        
        # Use AWS SDK to delete immediately
        results = self.aws_orchestrator.cleanup_registered_resources(
            wheel_group_ids=[wheel_group_id]
        )
        
        success = results['details'].get('wheel_groups', {}).get('successful', 0) > 0
        if success:
            # Remove from tracking lists
            if wheel_group_id in self._created_wheel_groups:
                self._created_wheel_groups.remove(wheel_group_id)
            if wheel_group_id in self._resource_metadata['wheel_groups']:
                del self._resource_metadata['wheel_groups'][wheel_group_id]
        
        return success
    
    def delete_user(self, user_id: str) -> bool:
        """
        Legacy method - delete a single user immediately
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if deletion successful
        """
        if not self.cleanup_enabled:
            self._log(f"Cleanup disabled, skipping user: {user_id}")
            return True
        
        self._log(f"Legacy delete_user called for: {user_id}")
        
        # Use AWS SDK to delete immediately  
        results = self.aws_orchestrator.cleanup_registered_resources(
            user_ids=[user_id]
        )
        
        success = results['details'].get('users', {}).get('successful', 0) > 0
        if success:
            # Remove from tracking lists
            if user_id in self._created_users:
                self._created_users.remove(user_id)
            if user_id in self._resource_metadata['users']:
                del self._resource_metadata['users'][user_id]
        
        return success
    
    # ========================================================================
    # MAIN CLEANUP ORCHESTRATION
    # ========================================================================
    
    def cleanup_all_registered_resources(self) -> Tuple[int, int]:
        """
        Clean up all registered resources using AWS SDK
        
        Returns:
            Tuple of (successful_cleanups, failed_cleanups)
        """
        if not self.cleanup_enabled:
            self._log("Cleanup disabled, skipping all resource cleanup")
            return 0, 0
        
        start_time = time.time()
        self._log("Starting AWS SDK cleanup of all registered resources")
        
        # Execute custom cleanup functions first (backward compatibility)
        custom_successful = 0
        custom_failed = 0
        for cleanup_func in self._custom_cleanup_functions:
            try:
                self._log(f"Executing custom cleanup function: {cleanup_func.__name__}")
                cleanup_func()
                custom_successful += 1
            except Exception as e:
                self._log(f"Custom cleanup function failed: {cleanup_func.__name__}: {e}")
                custom_failed += 1
        
        # Use AWS SDK orchestrator for bulk cleanup
        results = self.aws_orchestrator.cleanup_registered_resources(
            participant_ids=self._created_participants.copy() if self._created_participants else None,
            wheel_ids=self._created_wheels.copy() if self._created_wheels else None,
            wheel_group_ids=self._created_wheel_groups.copy() if self._created_wheel_groups else None,
            user_ids=self._created_users.copy() if self._created_users else None,
            cognito_usernames=self._created_cognito_users.copy() if self._created_cognito_users else None
        )
        
        # Update cleanup results
        self._cleanup_results['successful_deletes'] = results['total_successful'] + custom_successful
        self._cleanup_results['failed_deletes'] = results['total_failed'] + custom_failed
        
        # Clear tracking lists (successful items were cleaned up)
        if results['total_successful'] > 0:
            self._clear_successful_resources(results['details'])
        
        # Log cleanup summary
        duration = time.time() - start_time
        self._log_cleanup_summary(
            self._cleanup_results['successful_deletes'],
            self._cleanup_results['failed_deletes'], 
            duration,
            results['details']
        )
        
        return self._cleanup_results['successful_deletes'], self._cleanup_results['failed_deletes']
    
    def _clear_successful_resources(self, cleanup_details: Dict[str, Dict[str, int]]):
        """Clear successfully cleaned resources from tracking lists"""
        
        # Clear participants
        participants_successful = cleanup_details.get('participants', {}).get('successful', 0)
        if participants_successful > 0:
            self._created_participants.clear()
            self._resource_metadata['participants'].clear()
        
        # Clear wheels
        wheels_successful = cleanup_details.get('wheels', {}).get('successful', 0)
        if wheels_successful > 0:
            self._created_wheels.clear()
            self._resource_metadata['wheels'].clear()
        
        # Clear wheel groups
        wheel_groups_successful = cleanup_details.get('wheel_groups', {}).get('successful', 0)
        if wheel_groups_successful > 0:
            self._created_wheel_groups.clear()
            self._resource_metadata['wheel_groups'].clear()
        
        # Clear users
        users_successful = cleanup_details.get('users', {}).get('successful', 0)
        if users_successful > 0:
            self._created_users.clear()
            self._resource_metadata['users'].clear()
        
        # Clear Cognito users
        cognito_users_successful = cleanup_details.get('cognito_users', {}).get('successful', 0)
        if cognito_users_successful > 0:
            self._created_cognito_users.clear()
            self._resource_metadata['cognito_users'].clear()
    
    def _log_cleanup_summary(self, successful: int, failed: int, duration: float, details: Dict[str, Any]):
        """Enhanced cleanup logging with performance metrics"""
        self._log(f"=== CLEANUP SUMMARY ===")
        self._log(f"Duration: {duration:.2f} seconds")
        self._log(f"Total successful: {successful}")
        self._log(f"Total failed: {failed}")
        
        if self.debug and details:
            for resource_type, counts in details.items():
                self._log(f"{resource_type}: {counts['successful']} successful, {counts['failed']} failed")
        
        if self.dry_run:
            self._log("DRY RUN MODE - No actual deletions performed")
    
    # ========================================================================
    # LEGACY COMPATIBILITY METHODS (kept for backward compatibility)
    # ========================================================================
    
    def cleanup_test_data_by_pattern(self, pattern: str) -> Tuple[int, int]:
        """
        Legacy method - kept for backward compatibility but not recommended
        Use the standalone clear_test_data.py script for pattern-based cleanup
        
        Args:
            pattern: Pattern to match (not used in new implementation)
            
        Returns:
            Tuple of (0, 0) indicating this method is deprecated
        """
        self._log(f"cleanup_test_data_by_pattern called with pattern: {pattern}")
        self._log("This method is deprecated. Use clear_test_data.py script for pattern-based cleanup")
        return 0, 0
    
    def get_failed_cleanups(self) -> List[Dict[str, Any]]:
        """
        Get list of failed cleanups (legacy compatibility)
        
        Returns:
            List of failed cleanup records
        """
        return self._cleanup_results.get('errors', [])
    
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
            'users': self._created_users.copy(),
            'cognito_users': self._created_cognito_users.copy()  # NEW
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
        Verify that cleanup is complete
        
        Returns:
            Tuple of (is_complete, verification_results)
        """
        if not self.cleanup_enabled:
            return True, {'cleanup_disabled': True}
        
        # Simple check - if no resources remain in tracking lists, consider complete
        remaining = self.get_remaining_resources()
        total_remaining = sum(len(resources) for resources in remaining.values())
        
        is_complete = total_remaining == 0
        
        results = {
            'total_remaining': total_remaining,
            'remaining_resources': remaining,
            'is_complete': is_complete
        }
        
        self._log(f"Cleanup verification: {'COMPLETE' if is_complete else 'INCOMPLETE'}")
        return is_complete, results
    
    def force_cleanup_by_admin(self) -> Tuple[int, int]:
        """
        Legacy method - use clear_test_data.py script instead
        
        Returns:
            Tuple of (0, 0) indicating this method is deprecated
        """
        self._log("force_cleanup_by_admin called - this method is deprecated")
        self._log("Use clear_test_data.py script for comprehensive cleanup")
        return 0, 0
    
    # ========================================================================
    # NEW ENHANCED METHODS
    # ========================================================================
    
    def get_cleanup_metrics(self) -> Dict[str, Any]:
        """
        Return cleanup performance and success metrics
        
        Returns:
            Dictionary with cleanup metrics
        """
        remaining = self.get_remaining_resources()
        
        return {
            'cleanup_enabled': self.cleanup_enabled,
            'dry_run_mode': self.dry_run,
            'successful_deletes': self._cleanup_results.get('successful_deletes', 0),
            'failed_deletes': self._cleanup_results.get('failed_deletes', 0),
            'remaining_resources': {
                resource_type: len(resource_list) 
                for resource_type, resource_list in remaining.items()
            },
            'total_remaining': sum(len(resources) for resources in remaining.values()),
            'custom_cleanup_functions': len(self._custom_cleanup_functions)
        }
    
    def clear_all_tracking(self):
        """
        Clear all resource tracking (useful for testing)
        """
        self._created_wheel_groups.clear()
        self._created_wheels.clear()
        self._created_participants.clear()
        self._created_users.clear()
        self._created_cognito_users.clear()
        self._resource_metadata = {
            'participants': {},
            'wheels': {},
            'wheel_groups': {},
            'users': {},
            'cognito_users': {}
        }
        self._custom_cleanup_functions.clear()
        self._cleanup_results = {
            'successful_deletes': 0,
            'failed_deletes': 0,
            'errors': []
        }
        self._log("Cleared all resource tracking")
