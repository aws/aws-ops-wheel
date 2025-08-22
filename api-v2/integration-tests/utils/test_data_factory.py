"""
Test Data Factory for AWS Ops Wheel v2 Integration Tests
"""
import uuid
import time
import random
from typing import Dict, Any, List, Optional
from datetime import datetime


class TestDataFactory:
    """Factory for generating consistent test data"""
    
    def __init__(self, test_run_id: Optional[str] = None):
        """
        Initialize test data factory
        
        Args:
            test_run_id: Unique identifier for this test run
        """
        self.test_run_id = test_run_id or str(int(time.time()))
        self.counter = 0
        
    def _get_unique_suffix(self) -> str:
        """Get unique suffix for test data"""
        self.counter += 1
        return f"{self.test_run_id}-{self.counter:03d}"
    
    def generate_wheel_group_name(self, prefix: str = "IntegTest") -> str:
        """
        Generate unique wheel group name
        
        Args:
            prefix: Prefix for the name
            
        Returns:
            Unique wheel group name
        """
        return f"{prefix}-WheelGroup-{self._get_unique_suffix()}"
    
    def generate_wheel_name(self, prefix: str = "IntegTest") -> str:
        """
        Generate unique wheel name
        
        Args:
            prefix: Prefix for the name
            
        Returns:
            Unique wheel name
        """
        return f"{prefix}-Wheel-{self._get_unique_suffix()}"
    
    def generate_username(self, prefix: str = "testuser") -> str:
        """
        Generate unique username
        
        Args:
            prefix: Prefix for the username
            
        Returns:
            Unique username
        """
        return f"{prefix}-{self._get_unique_suffix()}"
    
    def generate_email(self, username: Optional[str] = None) -> str:
        """
        Generate test email address
        
        Args:
            username: Username to base email on
            
        Returns:
            Test email address
        """
        if not username:
            username = f"testuser-{self._get_unique_suffix()}"
        return f"{username}@integrationtest.example.com"
    
    def generate_password(self, length: int = 12) -> str:
        """
        Generate test password
        
        Args:
            length: Password length
            
        Returns:
            Test password that meets requirements
        """
        # Ensure password meets typical requirements
        base = f"TestPass{self.counter}!"
        if len(base) < length:
            base += "x" * (length - len(base))
        return base[:length]
    
    def create_wheel_group_data(self, name: Optional[str] = None, 
                               description: Optional[str] = None,
                               include_admin_user: bool = False) -> Dict[str, Any]:
        """
        Create wheel group test data
        
        Args:
            name: Wheel group name (generated if not provided)
            description: Wheel group description
            include_admin_user: Whether to include admin_user field (for admin API)
            
        Returns:
            Wheel group data dictionary
        """
        if not name:
            name = self.generate_wheel_group_name()
        
        if not description:
            description = f"Integration test wheel group created at {datetime.now().isoformat()}"
        
        data = {
            'wheel_group_name': name,
            'description': description,
            'settings': {
                'allow_public_wheels': True,
                'require_approval_for_participation': False,
                'max_wheels_per_user': 10,
                'max_participants_per_wheel': 100
            },
            'quotas': {
                'max_wheels': 50,
                'max_participants': 1000,
                'max_users': 100
            }
        }
        
        # Add admin_user field if requested (for admin API endpoints)
        if include_admin_user:
            admin_username = self.generate_username("wgadmin")
            admin_email = self.generate_email(admin_username)
            admin_password = self.generate_password()
            
            data['admin_user'] = {
                'username': admin_username,
                'email': admin_email,
                'password': admin_password
            }
        
        return data
    
    def create_public_wheel_group_data(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create public wheel group test data (for the critical endpoint)
        
        Args:
            name: Wheel group name (generated if not provided)
            
        Returns:
            Public wheel group creation data
        """
        if not name:
            name = self.generate_wheel_group_name("PublicTest")
        
        admin_username = self.generate_username("admin")
        admin_email = self.generate_email(admin_username)
        admin_password = self.generate_password()
        
        return {
            'wheel_group_name': name,
            'description': f"Public wheel group for integration testing - {datetime.now().isoformat()}",
            'admin_user': {
                'username': admin_username,
                'email': admin_email,
                'password': admin_password
            }
        }
    
    def create_wheel_data(self, name: Optional[str] = None, 
                         description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create wheel test data
        
        Args:
            name: Wheel name (generated if not provided)
            description: Wheel description
            
        Returns:
            Wheel data dictionary
        """
        if not name:
            name = self.generate_wheel_name()
        
        if not description:
            description = f"Integration test wheel created at {datetime.now().isoformat()}"
        
        return {
            'name': name,
            'description': description,
            'settings': {
                'allow_duplicates': False,
                'selection_algorithm': 'weighted_random',
                'auto_remove_selected': False,
                'require_confirmation': False
            }
        }
    
    def create_participant_data(self, name: Optional[str] = None, 
                               email: Optional[str] = None,
                               weight: Optional[int] = None) -> Dict[str, Any]:
        """
        Create participant test data
        
        Args:
            name: Participant name (generated if not provided)
            email: Participant email (generated if not provided)
            weight: Participant weight (random if not provided)
            
        Returns:
            Participant data dictionary
        """
        if not name:
            name = f"Test Participant {self._get_unique_suffix()}"
        
        if not email:
            username = f"participant-{self._get_unique_suffix()}"
            email = self.generate_email(username)
        
        if weight is None:
            weight = random.randint(1, 10)
        
        return {
            'name': name,
            'email': email,
            'weight': weight,
            'metadata': {
                'test_participant': True,
                'created_at': datetime.now().isoformat()
            }
        }
    
    def create_user_data(self, username: Optional[str] = None,
                        email: Optional[str] = None,
                        password: Optional[str] = None,
                        role: str = 'USER') -> Dict[str, Any]:
        """
        Create user test data
        
        Args:
            username: Username (generated if not provided)
            email: Email (generated if not provided)
            password: Password (generated if not provided)
            role: User role
            
        Returns:
            User data dictionary
        """
        if not username:
            username = self.generate_username()
        
        if not email:
            email = self.generate_email(username)
        
        if not password:
            password = self.generate_password()
        
        return {
            'username': username,
            'email': email,
            'password': password,
            'role': role,
            'profile': {
                'first_name': f"Test",
                'last_name': f"User-{self._get_unique_suffix()}",
                'department': "Integration Testing"
            }
        }
    
    def create_multiple_participants(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Create multiple participant data sets
        
        Args:
            count: Number of participants to create
            
        Returns:
            List of participant data dictionaries
        """
        participants = []
        for i in range(count):
            participant = self.create_participant_data(
                name=f"Test Participant {i+1} - {self._get_unique_suffix()}",
                weight=random.randint(1, 10)
            )
            participants.append(participant)
        
        return participants
    
    def create_selection_test_data(self) -> Dict[str, Any]:
        """
        Create test data for selection algorithm testing
        
        Returns:
            Test data for wheel spinning
        """
        return {
            'rigged_participant_id': None,  # Can be set after participant creation
            'algorithm': 'weighted_random',
            'options': {
                'respect_weights': True,
                'allow_consecutive_selections': False
            }
        }
    
    def get_test_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about this test run
        
        Returns:
            Test metadata
        """
        return {
            'test_run_id': self.test_run_id,
            'generated_items': self.counter,
            'timestamp': datetime.now().isoformat(),
            'factory_version': '1.0'
        }
    
    def create_search_test_queries(self) -> List[Dict[str, Any]]:
        """
        Create test queries for search functionality
        
        Returns:
            List of search query test cases
        """
        return [
            {
                'query': 'IntegTest',
                'expected_type': 'wheel_group',
                'description': 'Search for integration test wheel groups'
            },
            {
                'query': 'Test Participant',
                'expected_type': 'participant',
                'description': 'Search for test participants'
            },
            {
                'query': 'nonexistent',
                'expected_type': 'none',
                'description': 'Search for non-existent items'
            }
        ]
    
    def create_pagination_test_data(self, total_items: int = 25) -> Dict[str, Any]:
        """
        Create test data for pagination testing
        
        Args:
            total_items: Total number of items to create for pagination tests
            
        Returns:
            Pagination test configuration
        """
        return {
            'total_items': total_items,
            'page_sizes': [5, 10, 20],
            'expected_pages': {
                5: (total_items + 4) // 5,
                10: (total_items + 9) // 10,
                20: (total_items + 19) // 20
            }
        }
    
    def create_error_test_cases(self) -> List[Dict[str, Any]]:
        """
        Create test cases for error handling
        
        Returns:
            List of error test cases
        """
        return [
            {
                'name': 'missing_required_field',
                'data': {'description': 'Missing required name field'},
                'expected_status': 400,
                'expected_error': 'validation_error'
            },
            {
                'name': 'invalid_email_format',
                'data': {'email': 'invalid-email'},
                'expected_status': 400,
                'expected_error': 'invalid_email'
            },
            {
                'name': 'duplicate_name',
                'data': {'name': 'DuplicateTestName'},
                'expected_status': 409,
                'expected_error': 'conflict'
            },
            {
                'name': 'unauthorized_access',
                'data': None,
                'expected_status': 401,
                'expected_error': 'unauthorized'
            },
            {
                'name': 'forbidden_action',
                'data': None,
                'expected_status': 403,
                'expected_error': 'forbidden'
            },
            {
                'name': 'resource_not_found',
                'data': None,
                'expected_status': 404,
                'expected_error': 'not_found'
            }
        ]
