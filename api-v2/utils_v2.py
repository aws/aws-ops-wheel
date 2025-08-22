#  Enhanced Utilities for AWS Ops Wheel v2 Multi-wheel-group
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import boto3
import boto3.dynamodb.conditions
from botocore.exceptions import ClientError
import datetime
import os
import uuid
from typing import Dict, Any, List, Optional
from decimal import Decimal
from base import NotFoundError


# DynamoDB connection
dynamodb = boto3.resource('dynamodb')

# Get environment suffix for dynamic table naming
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# Multi-wheel-group table connections with dynamic suffix
# Check for explicit table name environment variables first, then fall back to constructed names
WheelGroupsTable = dynamodb.Table(os.environ.get('WHEEL_GROUPS_TABLE') or f'OpsWheelV2-WheelGroups-{ENVIRONMENT}')
UsersTable = dynamodb.Table(os.environ.get('USERS_TABLE') or f'OpsWheelV2-Users-{ENVIRONMENT}')
WheelsTable = dynamodb.Table(os.environ.get('WHEELS_TABLE') or f'OpsWheelV2-Wheels-{ENVIRONMENT}')
ParticipantsTable = dynamodb.Table(os.environ.get('PARTICIPANTS_TABLE') or f'OpsWheelV2-Participants-{ENVIRONMENT}')

# Debug logging for table names
import logging
logger = logging.getLogger()
logger.info(f"[DEBUG] Environment: {ENVIRONMENT}")
logger.info(f"[DEBUG] WheelGroupsTable name: {WheelGroupsTable.name}")
logger.info(f"[DEBUG] UsersTable name: {UsersTable.name}")
logger.info(f"[DEBUG] WheelsTable name: {WheelsTable.name}")
logger.info(f"[DEBUG] ParticipantsTable name: {ParticipantsTable.name}")


def add_extended_table_functions(table):
    """Add extended functionality to DynamoDB table objects"""
    
    def get_existing_item(Key, *args, **kwargs):
        """Get item and throw 404 if it doesn't exist"""
        response = table.get_item(Key=Key, *args, **kwargs)
        if 'Item' not in response:
            raise NotFoundError(f"{table.name} : {Key} could not be found")
        return response['Item']

    def iter_query(*args, **kwargs):
        """Unwrap pagination from DynamoDB query results"""
        # Ensure KeyConditionExpression uses boto3.dynamodb.conditions for safety
        if 'KeyConditionExpression' in kwargs and isinstance(kwargs['KeyConditionExpression'], str):
            raise ValueError("KeyConditionExpression must use boto3.dynamodb.conditions.Key() for security")
        
        query_results = None
        while query_results is None or 'LastEvaluatedKey' in query_results:
            if query_results is not None:
                kwargs['ExclusiveStartKey'] = query_results['LastEvaluatedKey']
            query_results = table.query(*args, **kwargs)
            for item in query_results['Items']:
                yield item

    def iter_scan(*args, **kwargs):
        """Unwrap pagination from DynamoDB scan results"""
        scan_results = None
        while scan_results is None or 'LastEvaluatedKey' in scan_results:
            if scan_results is not None:
                kwargs['ExclusiveStartKey'] = scan_results['LastEvaluatedKey']
            scan_results = table.scan(*args, **kwargs)
            for item in scan_results['Items']:
                yield item

    table.get_existing_item = get_existing_item
    table.iter_query = iter_query
    table.iter_scan = iter_scan


# Apply extended functions to all tables
add_extended_table_functions(WheelGroupsTable)
add_extended_table_functions(UsersTable)
add_extended_table_functions(WheelsTable)
add_extended_table_functions(ParticipantsTable)


# Utility Functions
def check_string(string: Any) -> bool:
    """Check if value is a non-empty string"""
    return isinstance(string, str) and len(string) > 0


def get_uuid() -> str:
    """Generate a new UUID string"""
    return str(uuid.uuid4())


def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format"""
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def to_update_kwargs(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Convert attribute dictionary to DynamoDB update expression kwargs"""
    return {
        'UpdateExpression': 'set {}'.format(', '.join([f"#{k} = :{k}" for k in attributes])),
        'ExpressionAttributeValues': {f":{k}": v for k, v in attributes.items()},
        'ExpressionAttributeNames': {f"#{k}": k for k in attributes}
    }


def decimal_to_float(obj: Any) -> Any:
    """Recursively convert DynamoDB Decimal objects to float"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(v) for v in obj]
    return obj


# Wheel-group-specific utility functions
def create_wheel_group_wheel_id(wheel_group_id: str, wheel_id: str) -> str:
    """Create composite key for wheel-group-wheel operations"""
    return f"{wheel_group_id}#{wheel_id}"


def parse_wheel_group_wheel_id(wheel_group_wheel_id: str) -> tuple:
    """Parse composite wheel-group-wheel ID back to components"""
    parts = wheel_group_wheel_id.split('#', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid wheel_group_wheel_id format: {wheel_group_wheel_id}")
    return parts[0], parts[1]


class WheelGroupRepository:
    """Repository class for wheel group operations"""
    
    @staticmethod
    def create_wheel_group(wheel_group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new wheel group"""
        timestamp = get_utc_timestamp()
        
        # Convert any float values to Decimal for DynamoDB compatibility
        quotas = wheel_group_data.get('quotas', {
            'max_wheels': 1000,
            'max_participants_per_wheel': 1000,
            'max_multi_select': 30
        })
        # Convert quota values to Decimal if they're numeric
        for key, value in quotas.items():
            if isinstance(value, (int, float)):
                quotas[key] = Decimal(str(value))
        
        settings = wheel_group_data.get('settings', {
            'allow_rigging': True,
            'default_participant_weight': 1.0,
            'theme': 'default',
            'timezone': 'UTC'
        })
        # Convert settings values to Decimal if they're numeric floats
        for key, value in settings.items():
            if isinstance(value, float):
                settings[key] = Decimal(str(value))
        
        wheel_group = {
            'wheel_group_id': wheel_group_data.get('wheel_group_id') or get_uuid(),
            'wheel_group_name': wheel_group_data['wheel_group_name'],
            'created_at': timestamp,
            'updated_at': timestamp,  # Initially same as created_at
            'quotas': quotas,
            'settings': settings
        }
        
        WheelGroupsTable.put_item(Item=wheel_group)
        return wheel_group
    
    @staticmethod
    def get_wheel_group(wheel_group_id: str) -> Dict[str, Any]:
        """Get wheel group by ID"""
        logger.info(f"[WheelGroupRepository.get_wheel_group] Input: {wheel_group_id} (type: {type(wheel_group_id)})")
        
        # Defensive check for None or invalid wheel_group_id
        if wheel_group_id is None:
            import traceback
            stack_trace = traceback.format_stack()
            logger.error(f"[WheelGroupRepository.get_wheel_group] Called with None wheel_group_id - this indicates a logic error")
            logger.error(f"[WheelGroupRepository.get_wheel_group] FULL STACK TRACE:")
            for line in stack_trace:
                logger.error(f"[STACK] {line.strip()}")
            raise ValueError("wheel_group_id cannot be None. This typically happens when a deployment admin's wheel_group_id is incorrectly used.")
        
        if not isinstance(wheel_group_id, str) or not wheel_group_id.strip():
            logger.error(f"[WheelGroupRepository.get_wheel_group] Invalid wheel_group_id: {repr(wheel_group_id)}")
            raise ValueError(f"wheel_group_id must be a non-empty string, got: {repr(wheel_group_id)}")
        
        key = {'wheel_group_id': wheel_group_id}
        logger.info(f"[WheelGroupRepository.get_wheel_group] DynamoDB Key: {key}")
        logger.info(f"[WheelGroupRepository.get_wheel_group] Table name: {WheelGroupsTable.name}")
        
        try:
            result = WheelGroupsTable.get_existing_item(Key=key)
            logger.info(f"[WheelGroupRepository.get_wheel_group] Success: Found wheel group")
            return result
        except Exception as e:
            logger.error(f"[WheelGroupRepository.get_wheel_group] Error: {str(e)}")
            logger.error(f"[WheelGroupRepository.get_wheel_group] Error type: {type(e)}")
            import traceback
            logger.error(f"[WheelGroupRepository.get_wheel_group] Traceback: {traceback.format_exc()}")
            raise
    
    @staticmethod
    def update_wheel_group(wheel_group_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update wheel group information"""
        updates['updated_at'] = get_utc_timestamp()
        WheelGroupsTable.update_item(
            Key={'wheel_group_id': wheel_group_id},
            **to_update_kwargs(updates)
        )
        # Return updated wheel group
        return WheelGroupsTable.get_existing_item(Key={'wheel_group_id': wheel_group_id})
    
    @staticmethod
    def delete_wheel_group(wheel_group_id: str) -> None:
        """Delete a wheel group (admin operation)"""
        WheelGroupsTable.delete_item(Key={'wheel_group_id': wheel_group_id})
    
    @staticmethod  
    def list_all_wheel_groups() -> List[Dict[str, Any]]:
        """List all wheel groups in the system"""
        try:
            # Use scan operation to get all wheel groups
            response = WheelGroupsTable.scan()
            return response.get('Items', [])
        except ClientError as ce:
            if ce.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Wheel groups table not found - returning empty list")
                # Return empty list when table doesn't exist (test environment)
                return []
            else:
                # Re-raise other ClientErrors (like database connection issues)
                raise ce
        except Exception as e:
            # Re-raise other database errors that should cause failures
            logger.error(f"Error scanning wheel groups: {str(e)}")
            raise e


class UserRepository:
    """Repository class for user operations"""
    
    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        timestamp = get_utc_timestamp()
        
        user = {
            'user_id': user_data['user_id'],  # From Cognito sub
            'wheel_group_id': user_data['wheel_group_id'],
            'email': user_data['email'],
            'name': user_data.get('name', user_data['email']),
            'role': user_data.get('role', 'USER'),
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        UsersTable.put_item(Item=user)
        return user
    
    @staticmethod
    def get_user(user_id: str) -> Dict[str, Any]:
        """Get user by ID"""
        return UsersTable.get_existing_item(Key={'user_id': user_id})
    
    @staticmethod
    def get_users_by_wheel_group(wheel_group_id: str) -> List[Dict[str, Any]]:
        """Get all users for a wheel group"""
        response = UsersTable.query(
            IndexName='wheel-group-role-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('wheel_group_id').eq(wheel_group_id)
        )
        return response.get('Items', [])
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        response = UsersTable.query(
            IndexName='email-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email)
        )
        items = response.get('Items', [])
        return items[0] if items else None
    
    @staticmethod
    def update_user(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user information"""
        updates['updated_at'] = get_utc_timestamp()
        UsersTable.update_item(
            Key={'user_id': user_id},
            **to_update_kwargs(updates)
        )
        return UsersTable.get_existing_item(Key={'user_id': user_id})
    
    @staticmethod
    def update_user_role(user_id: str, new_role: str) -> Dict[str, Any]:
        """Update user role"""
        return UserRepository.update_user(user_id, {'role': new_role})
    
    @staticmethod
    def update_last_login(user_id: str) -> Dict[str, Any]:
        """Update user's last login timestamp"""
        return UserRepository.update_user(user_id, {'last_login_at': get_utc_timestamp()})
    
    @staticmethod
    def delete_user(user_id: str) -> None:
        """Delete a user"""
        UsersTable.delete_item(Key={'user_id': user_id})


class WheelRepository:
    """Repository class for wheel-group-aware wheel operations"""
    
    @staticmethod
    def create_wheel(wheel_group_id: str, wheel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new wheel for a wheel group"""
        timestamp = get_utc_timestamp()
        
        wheel = {
            'wheel_group_id': wheel_group_id,
            'wheel_id': wheel_data.get('wheel_id') or get_uuid(),
            'wheel_name': wheel_data['wheel_name'],
            'description': wheel_data.get('description', ''),
            'created_by': wheel_data['created_by'],
            'created_at': timestamp,
            'updated_at': timestamp,
            'settings': wheel_data.get('settings', {
                'allow_rigging': True,
                'multi_select_enabled': True,
                'default_multi_select_count': 1,
                'require_reason_for_rigging': False,
                'show_weights': False,
                'auto_reset_weights': False
            }),
            'participant_count': 0,
            'total_spins': 0
        }
        
        # Only add last_spun_at and last_spun_by if they have values
        # This avoids DynamoDB GSI issues with NULL values
        if wheel_data.get('last_spun_at'):
            wheel['last_spun_at'] = wheel_data['last_spun_at']
        if wheel_data.get('last_spun_by'):
            wheel['last_spun_by'] = wheel_data['last_spun_by']
        
        WheelsTable.put_item(Item=wheel)
        return wheel
    
    @staticmethod
    def get_wheel(wheel_group_id: str, wheel_id: str) -> Dict[str, Any]:
        """Get wheel by wheel group and wheel ID"""
        return WheelsTable.get_existing_item(Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id})
    
    @staticmethod
    def list_wheel_group_wheels(wheel_group_id: str) -> List[Dict[str, Any]]:
        """Get all wheels for a wheel group"""
        response = WheelsTable.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('wheel_group_id').eq(wheel_group_id)
        )
        return response.get('Items', [])
    
    @staticmethod
    def update_wheel(wheel_group_id: str, wheel_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update wheel information"""
        updates['updated_at'] = get_utc_timestamp()
        WheelsTable.update_item(
            Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id},
            **to_update_kwargs(updates)
        )
        return WheelsTable.get_existing_item(Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id})
    
    @staticmethod
    def delete_wheel(wheel_group_id: str, wheel_id: str) -> None:
        """Delete a wheel and all its participants"""
        # Delete the wheel
        WheelsTable.delete_item(Key={'wheel_group_id': wheel_group_id, 'wheel_id': wheel_id})
        
        # Delete all participants
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        participants = ParticipantsTable.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('wheel_group_wheel_id').eq(wheel_group_wheel_id),
            ProjectionExpression='participant_id'
        )
        
        with ParticipantsTable.batch_writer() as batch:
            for participant in participants.get('Items', []):
                batch.delete_item(Key={
                    'wheel_group_wheel_id': wheel_group_wheel_id,
                    'participant_id': participant['participant_id']
                })


class ParticipantRepository:
    """Repository class for wheel-group-aware participant operations"""
    
    @staticmethod
    def create_participant(wheel_group_id: str, wheel_id: str, participant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new participant for a wheel"""
        timestamp = get_utc_timestamp()
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        
        participant = {
            'wheel_group_wheel_id': wheel_group_wheel_id,
            'participant_id': participant_data.get('participant_id') or get_uuid(),
            'participant_name': participant_data['participant_name'],
            'participant_url': participant_data.get('participant_url', ''),
            'weight': Decimal(str(participant_data.get('weight', 1.0))),
            'original_weight': Decimal(str(participant_data.get('weight', 1.0))),
            'created_at': timestamp,
            'updated_at': timestamp,
            # Don't include last_selected_at for new participants to avoid GSI issues
            # 'last_selected_at': None,
            'selection_count': 0
        }
        
        ParticipantsTable.put_item(Item=participant)
        return participant
    
    @staticmethod
    def get_participant(wheel_group_id: str, wheel_id: str, participant_id: str) -> Dict[str, Any]:
        """Get participant by IDs"""
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        return ParticipantsTable.get_existing_item(Key={
            'wheel_group_wheel_id': wheel_group_wheel_id,
            'participant_id': participant_id
        })
    
    @staticmethod
    def list_wheel_participants(wheel_group_id: str, wheel_id: str) -> List[Dict[str, Any]]:
        """Get all participants for a wheel"""
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        response = ParticipantsTable.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('wheel_group_wheel_id').eq(wheel_group_wheel_id)
        )
        # Convert Decimal objects to float for JSON serialization
        return [decimal_to_float(item) for item in response.get('Items', [])]
    
    @staticmethod
    def update_participant(wheel_group_id: str, wheel_id: str, participant_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update participant information"""
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        updates['updated_at'] = get_utc_timestamp()
        
        # Convert weight and original_weight to Decimal if present
        if 'weight' in updates:
            updates['weight'] = Decimal(str(updates['weight']))
        if 'original_weight' in updates:
            updates['original_weight'] = Decimal(str(updates['original_weight']))
        
        ParticipantsTable.update_item(
            Key={'wheel_group_wheel_id': wheel_group_wheel_id, 'participant_id': participant_id},
            **to_update_kwargs(updates)
        )
        return ParticipantsTable.get_existing_item(Key={
            'wheel_group_wheel_id': wheel_group_wheel_id,
            'participant_id': participant_id
        })
    
    @staticmethod
    def delete_participant(wheel_group_id: str, wheel_id: str, participant_id: str) -> Optional[Dict[str, Any]]:
        """Delete a participant and return the deleted item"""
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        response = ParticipantsTable.delete_item(
            Key={'wheel_group_wheel_id': wheel_group_wheel_id, 'participant_id': participant_id},
            ReturnValues='ALL_OLD'
        )
        return response.get('Attributes')
    
    @staticmethod
    def batch_update_participants(wheel_group_id: str, wheel_id: str, participant_updates: List[Dict[str, Any]]) -> None:
        """Batch update multiple participants (for weight redistribution)"""
        wheel_group_wheel_id = create_wheel_group_wheel_id(wheel_group_id, wheel_id)
        
        # Use individual update_item calls instead of batch writer with put_item
        # because put_item requires complete items, but we only have partial updates
        for update in participant_updates:
            participant_id = update['participant_id']
            
            # Prepare the update data
            update_data = {}
            for key, value in update.items():
                if key != 'participant_id':  # Skip the key field
                    if key == 'weight':
                        update_data[key] = Decimal(str(value))
                    elif key == 'selection_count':
                        update_data[key] = Decimal(str(value)) if not isinstance(value, Decimal) else value
                    else:
                        update_data[key] = value
            
            update_data['updated_at'] = get_utc_timestamp()
            
            # Use update_item for each participant
            ParticipantsTable.update_item(
                Key={'wheel_group_wheel_id': wheel_group_wheel_id, 'participant_id': participant_id},
                **to_update_kwargs(update_data)
            )


# Export repositories for easy importing
__all__ = [
    'WheelGroupsTable', 'UsersTable', 'WheelsTable', 'ParticipantsTable',
    'WheelGroupRepository', 'UserRepository', 'WheelRepository', 'ParticipantRepository',
    'check_string', 'get_uuid', 'get_utc_timestamp', 'to_update_kwargs',
    'decimal_to_float', 'create_wheel_group_wheel_id', 'parse_wheel_group_wheel_id'
]
