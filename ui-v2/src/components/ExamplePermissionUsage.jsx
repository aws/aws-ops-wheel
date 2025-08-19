/*
 * Permission Guard Usage Examples
 * This file demonstrates how to use the PermissionGuard component
 */

import React from 'react';
import PermissionGuard from './PermissionGuard';
import { usePermissions, useUserInfo } from './PermissionContext';
import { Button } from 'react-bootstrap';

// Example 1: Simple Permission Guard
const WheelManagementExample = () => {
  return (
    <div>
      <h3>Wheel Management</h3>
      
      {/* Everyone can view wheels */}
      <Button variant="info">View Wheels</Button>
      
      {/* Only WHEEL_ADMIN and ADMIN can create wheels */}
      <PermissionGuard permission="create_wheel">
        <Button variant="primary">Create New Wheel</Button>
      </PermissionGuard>
      
      {/* Only ADMIN can delete wheels */}
      <PermissionGuard permission="delete_wheel">
        <Button variant="danger">Delete Wheel</Button>
      </PermissionGuard>
      
      {/* Only ADMIN can manage users */}
      <PermissionGuard permission="manage_users">
        <Button variant="warning">Manage Users</Button>
      </PermissionGuard>
    </div>
  );
};

// Example 2: Using Permission Hook Directly
const UserDashboard = () => {
  const { hasPermission, role, loading } = usePermissions();
  const { wheelGroupName, email } = useUserInfo();
  
  if (loading) {
    return <div>Loading permissions...</div>;
  }
  
  return (
    <div>
      <h3>User Dashboard</h3>
      <p>Welcome, {email}</p>
      <p>Wheel Group: {wheelGroupName}</p>
      <p>Role: {role}</p>
      
      <div>
        <h4>Available Actions:</h4>
        <ul>
          <li>View Wheels: ✓ (Everyone)</li>
          <li>Spin Wheels: ✓ (Everyone)</li>
          {hasPermission('create_wheel') && <li>Create Wheels: ✓</li>}
          {hasPermission('manage_participants') && <li>Manage Participants: ✓</li>}
          {hasPermission('delete_wheel') && <li>Delete Wheels: ✓</li>}
          {hasPermission('manage_users') && <li>Manage Users: ✓</li>}
          {hasPermission('rig_wheel') && <li>Rig Wheels: ✓</li>}
        </ul>
      </div>
    </div>
  );
};

// Example 3: Multiple Permissions (OR logic)
const ModeratorActions = () => {
  return (
    <div>
      <h3>Moderator Actions</h3>
      
      {/* Show if user has ANY of these permissions */}
      <PermissionGuard permission={['create_wheel', 'delete_wheel', 'manage_participants']}>
        <div className="alert alert-info">
          You have moderator privileges in this wheel group.
        </div>
      </PermissionGuard>
    </div>
  );
};

// Example 4: Multiple Permissions (AND logic)
const AdminOnlySection = () => {
  return (
    <div>
      <h3>Admin Section</h3>
      
      {/* Show only if user has ALL of these permissions */}
      <PermissionGuard 
        permission={['manage_users', 'manage_wheel_group']} 
        requireAll={true}
      >
        <div className="alert alert-warning">
          <h4>Wheel Group Administration</h4>
          <p>You have full administrative access to this wheel group.</p>
          <Button variant="danger">Delete Wheel Group</Button>
        </div>
      </PermissionGuard>
    </div>
  );
};

// Example 5: Permission Guard with Fallback
const ConditionalContent = () => {
  return (
    <div>
      <h3>Content Based on Role</h3>
      
      <PermissionGuard 
        permission="manage_users"
        fallback={
          <div className="alert alert-secondary">
            Contact your administrator to manage users.
          </div>
        }
      >
        <div className="alert alert-success">
          <h4>User Management</h4>
          <Button variant="primary">Add User</Button>
          <Button variant="warning">Edit Roles</Button>
        </div>
      </PermissionGuard>
    </div>
  );
};

export {
  WheelManagementExample,
  UserDashboard,
  ModeratorActions,
  AdminOnlySection,
  ConditionalContent
};
