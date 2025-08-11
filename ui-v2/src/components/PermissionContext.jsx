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

import React, { createContext, useContext, useEffect, useState } from 'react';
import { authenticatedFetch, apiURL } from '../util';

// Permission mappings matching backend role definitions
const ROLE_PERMISSIONS = {
  'ADMIN': {
    'create_wheel': true,
    'delete_wheel': true,
    'manage_participants': true,
    'spin_wheel': true,
    'view_wheels': true,
    'manage_users': true,
    'manage_tenant': true,
    'rig_wheel': true
  },
  'WHEEL_ADMIN': {
    'create_wheel': true,
    'delete_wheel': true,
    'manage_participants': true,
    'spin_wheel': true,
    'view_wheels': true,
    'manage_users': false,
    'manage_tenant': false,
    'rig_wheel': true
  },
  'USER': {
    'create_wheel': false,
    'delete_wheel': false,
    'manage_participants': false,
    'spin_wheel': true,
    'view_wheels': true,
    'manage_users': false,
    'manage_tenant': false,
    'rig_wheel': false
  }
};

const PermissionContext = createContext({
  permissions: {},
  role: null,
  tenantId: null,
  tenantName: null,
  userId: null,
  email: null,
  name: null,
  loading: true,
  error: null,
  hasPermission: () => false,
  isRole: () => false,
  refreshPermissions: () => {}
});

/**
 * PermissionProvider component that provides user permissions context to the app
 * 
 * This component:
 * 1. Extracts user info from JWT token stored in localStorage
 * 2. Optionally validates token with backend API
 * 3. Provides permission checking functions
 * 4. Handles permission loading states and errors
 */
export const PermissionProvider = ({ children, validateWithBackend = false }) => {
  const [state, setState] = useState({
    permissions: {},
    role: null,
    tenantId: null,
    tenantName: null,
    userId: null,
    email: null,
    name: null,
    loading: true,
    error: null
  });

  const loadPermissions = async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      // Method 1: Extract from JWT token (faster, offline-capable)
      let userInfo = null;
      try {
        userInfo = extractUserInfoFromToken();
      } catch (error) {
        console.warn('Failed to extract user info from token:', error);
        
        // Clear invalid tokens and redirect to login
        localStorage.removeItem('idToken');
        window.location.href = '/app/login';
        return;
      }

      if (!userInfo) {
        // No valid token found, redirect to login
        window.location.href = '/app/login';
        return;
      }

      // Method 2: Optionally validate with backend (slower, but authoritative)
      if (validateWithBackend) {
        try {
          const response = await authenticatedFetch(apiURL('auth/validate'));
          if (response && response.ok) {
            const backendUserInfo = await response.json();
            // Use backend info if available, fall back to token info
            userInfo = { ...userInfo, ...backendUserInfo };
          }
        } catch (error) {
          console.warn('Backend validation failed, using token info:', error);
          // Continue with token-based info
        }
      }

      // Get permissions for the user's role
      const permissions = ROLE_PERMISSIONS[userInfo.role?.toUpperCase()] || ROLE_PERMISSIONS['USER'];

      setState({
        permissions,
        role: userInfo.role,
        tenantId: userInfo.tenant_id,
        tenantName: userInfo.tenant_name,
        userId: userInfo.user_id || userInfo.sub,
        email: userInfo.email,
        name: userInfo.name || userInfo.email,
        loading: false,
        error: null
      });

    } catch (error) {
      console.error('Failed to load permissions:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error.message || 'Failed to load permissions'
      }));
    }
  };

  const extractUserInfoFromToken = () => {
    // First try the simple key (for compatibility)
    let idToken = localStorage.getItem('idToken');
    
    // If not found, look for Cognito-stored ID token
    if (!idToken) {
      const cognitoKeys = Object.keys(localStorage).filter(key => 
        key.includes('CognitoIdentityServiceProvider') && key.endsWith('.idToken')
      );
      
      if (cognitoKeys.length > 0) {
        idToken = localStorage.getItem(cognitoKeys[0]);
      }
    }

    if (!idToken) {
      return null;
    }

    try {
      // Decode JWT payload (safe for reading, not for validation)
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      
      // Check if token is expired
      const currentTime = Math.floor(Date.now() / 1000);
      if (payload.exp && payload.exp < currentTime) {
        console.warn('Token has expired');
        localStorage.removeItem('idToken');
        return null;
      }

      return {
        tenant_id: payload['custom:tenant_id'],
        tenant_name: payload['custom:tenant_name'],
        role: payload['custom:role'] || 'USER',
        user_id: payload.sub,
        email: payload.email,
        name: payload.name || payload.email
      };
    } catch (error) {
      console.error('Failed to decode JWT token:', error);
      throw new Error('Invalid token format');
    }
  };

  const hasPermission = (permission) => {
    if (!permission || state.loading) {
      return false;
    }
    return state.permissions[permission] === true;
  };

  const isRole = (role) => {
    if (!role || state.loading) {
      return false; 
    }
    if (Array.isArray(role)) {
      return role.includes(state.role);
    }
    return state.role === role;
  };

  const refreshPermissions = () => {
    loadPermissions();
  };

  // Load permissions on mount and when localStorage changes
  useEffect(() => {
    loadPermissions();

    // Listen for localStorage changes (e.g., login/logout in another tab)
    const handleStorageChange = (event) => {
      if (event.key === 'idToken') {
        loadPermissions();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const contextValue = {
    ...state,
    hasPermission,
    isRole,
    refreshPermissions
  };

  return (
    <PermissionContext.Provider value={contextValue}>
      {children}
    </PermissionContext.Provider>
  );
};

/**
 * Hook to access permission context
 * 
 * @example
 * const { hasPermission, role, loading, permissions } = usePermissions();
 * 
 * if (loading) return <div>Loading...</div>;
 * 
 * return (
 *   <div>
 *     <p>Role: {role}</p>
 *     {hasPermission('create_wheel') && <Button>Create Wheel</Button>}
 *   </div>
 * );
 */
export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissions must be used within a PermissionProvider');
  }
  return context;
};

/**
 * Hook to get current user info
 * 
 * @example
 * const { tenantId, tenantName, email, name, role } = useUserInfo();
 */
export const useUserInfo = () => {
  const { tenantId, tenantName, userId, email, name, role, loading } = usePermissions();
  return { tenantId, tenantName, userId, email, name, role, loading };
};

export default PermissionProvider;
