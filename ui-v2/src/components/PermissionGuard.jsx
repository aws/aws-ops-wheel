/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *   http://aws.amazon.com/apache2.0/
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */

import React from 'react';
import { usePermissions } from './PermissionContext';

/**
 * PermissionGuard component that conditionally renders children based on user permissions
 * 
 * @param {string} permission - Required permission name (e.g., 'create_wheel', 'manage_users')
 * @param {React.ReactNode} children - Content to render if user has permission
 * @param {React.ReactNode} fallback - Content to render if user lacks permission (default: null)
 * @param {boolean} requireAll - If checking multiple permissions, require all (default: false)
 * 
 * @example
 * // Simple usage - hide button if user can't create wheels
 * <PermissionGuard permission="create_wheel">
 *   <Button onClick={createWheel}>Add New Wheel</Button>
 * </PermissionGuard>
 * 
 * @example  
 * // With fallback content
 * <PermissionGuard 
 *   permission="manage_users" 
 *   fallback={<div>Contact your admin to manage users</div>}
 * >
 *   <UserManagementPanel />
 * </PermissionGuard>
 * 
 * @example
 * // Multiple permissions (any one is sufficient)
 * <PermissionGuard permission={['create_wheel', 'delete_wheel']}>
 *   <WheelActions />
 * </PermissionGuard>
 * 
 * @example
 * // Multiple permissions (all required)
 * <PermissionGuard permission={['create_wheel', 'manage_participants']} requireAll={true}>
 *   <AdvancedWheelControls />
 * </PermissionGuard>
 */
export const PermissionGuard = ({ 
  permission, 
  children, 
  fallback = null, 
  requireAll = false 
}) => {
  const { hasPermission, loading } = usePermissions();
  
  // Show nothing while loading permissions
  if (loading) {
    return null;
  }
  
  // Handle single permission
  if (typeof permission === 'string') {
    return hasPermission(permission) ? children : fallback;
  }
  
  // Handle array of permissions
  if (Array.isArray(permission)) {
    const hasRequiredPermissions = requireAll
      ? permission.every(perm => hasPermission(perm))  // All permissions required
      : permission.some(perm => hasPermission(perm));  // Any permission sufficient
      
    return hasRequiredPermissions ? children : fallback;
  }
  
  // Invalid permission type
  console.warn('PermissionGuard: permission must be string or array of strings');
  return fallback;
};

/**
 * Hook to check permissions directly in components
 * 
 * @example
 * const MyComponent = () => {
 *   const { hasPermission, permissions, role } = usePermissions();
 *   
 *   const canEdit = hasPermission('create_wheel');
 *   const isAdmin = role === 'ADMIN';
 *   
 *   return (
 *     <div>
 *       {canEdit && <EditButton />}
 *       {isAdmin && <AdminPanel />}
 *     </div>
 *   );
 * };
 */
export { usePermissions };

export default PermissionGuard;
