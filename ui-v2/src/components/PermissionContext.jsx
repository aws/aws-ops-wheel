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
  'DEPLOYMENT_ADMIN': {
    'view_all_wheel_groups': true,
    'delete_wheel_group': true,
    'manage_deployment': true,
    'create_wheel': false,
    'delete_wheel': false,
    'manage_participants': false,
    'spin_wheel': false,
    'view_wheels': false,
    'manage_users': false,
    'manage_wheel_group': false,
    'rig_wheel': false
  },
  'ADMIN': {
    'create_wheel': true,
    'delete_wheel': true,
    'manage_participants': true,
    'spin_wheel': true,
    'view_wheels': true,
    'manage_users': true,
    'manage_wheel_group': true,
    'rig_wheel': true
  },
  'WHEEL_ADMIN': {
    'create_wheel': true,
    'delete_wheel': true,
    'manage_participants': true,
    'spin_wheel': true,
    'view_wheels': true,
    'manage_users': false,
    'manage_wheel_group': false,
    'rig_wheel': true
  },
  'USER': {
    'create_wheel': false,
    'delete_wheel': false,
    'manage_participants': false,
    'spin_wheel': true,
    'view_wheels': true,
    'manage_users': false,
    'manage_wheel_group': false,
    'rig_wheel': false
  }
};

const PermissionContext = createContext({
  permissions: {},
  role: null,
  wheelGroupId: null,
  wheelGroupName: null,
  userId: null,
  email: null,
  name: null,
  loading: true,
  error: null,
  hasPermission: () => false,
  isRole: () => false,
  refreshPermissions: () => {}
});

export const PermissionProvider = ({ children, validateWithBackend = false }) => {
  const [state, setState] = useState({
    permissions: {},
    role: null,
    wheelGroupId: null,
    wheelGroupName: null,
    userId: null,
    email: null,
    name: null,
    loading: true,
    error: null
  });

  const loadingRef = React.useRef(false);

  const loadPermissions = async () => {
    if (loadingRef.current) {
      return;
    }
    
    loadingRef.current = true;
    
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      let tokenInfo = null;
      try {
        tokenInfo = extractUserInfoFromToken();
      } catch (error) {
        console.warn('Failed to extract user info from token:', error);
        localStorage.removeItem('idToken');
        window.location.href = '/app/login';
        return;
      }

      if (!tokenInfo) {
        window.location.href = '/app/login';
        return;
      }

      // For deployment admin, skip backend API call and use token info directly
      let userInfo = tokenInfo;
      
      if (tokenInfo.deployment_admin) {
        userInfo = tokenInfo;
      } else {
        // For regular users, fetch from backend API
        try {
          const response = await authenticatedFetch(apiURL('auth/me'));
          
          if (response && response.ok) {
            const backendUserInfo = await response.json();
            
            userInfo = { 
              ...tokenInfo, 
              ...backendUserInfo,
              role: backendUserInfo.role || 'USER',
              permissions: backendUserInfo.permissions || {}
            };
          } else if (response && response.status === 401) {
            localStorage.removeItem('idToken');
            window.location.href = '/app/login';
            return;
          } else {
            userInfo = { ...tokenInfo, role: 'USER' };
          }
        } catch (error) {
          console.error('Backend API error, using token info with USER role:', error);
          userInfo = { ...tokenInfo, role: 'USER' };
        }
      }

      // Get permissions for the user's role
      const role = userInfo.role?.toUpperCase() || 'USER';
      const permissions = ROLE_PERMISSIONS[role] || ROLE_PERMISSIONS['USER'];

      setState({
        permissions,
        role: userInfo.role || 'USER',
        wheelGroupId: userInfo.wheel_group_id,
        wheelGroupName: userInfo.wheel_group_name,
        userId: userInfo.user_id || userInfo.sub,
        email: userInfo.email,
        name: userInfo.name || userInfo.email,
        loading: false,
        error: null
      });

    } catch (error) {
      console.error('loadPermissions failed:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error.message || 'Failed to load permissions'
      }));
    } finally {
      loadingRef.current = false;
    }
  };

  const extractUserInfoFromToken = () => {
    let idToken = localStorage.getItem('idToken');
    
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
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      
      const currentTime = Math.floor(Date.now() / 1000);
      if (payload.exp && payload.exp < currentTime) {
        localStorage.removeItem('idToken');
        return null;
      }

      const isDeploymentAdmin = payload['custom:deployment_admin'] === 'true';
      
      const userInfo = {
        wheel_group_id: payload['custom:wheel_group_id'],
        wheel_group_name: payload['custom:wheel_group_name'],
        role: isDeploymentAdmin ? 'DEPLOYMENT_ADMIN' : (payload['custom:role'] || 'USER'),
        user_id: payload.sub,
        email: payload.email,
        name: payload.name || payload.email,
        deployment_admin: isDeploymentAdmin
      };
      
      return userInfo;
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
    if (!loadingRef.current) {
      loadPermissions();
    }
  };

  // Load permissions on mount only
  useEffect(() => {
    loadPermissions();
  }, []);

  // Separate effect for storage changes
  useEffect(() => {
    const handleStorageChange = (event) => {
      if (event.key === 'idToken' && !loadingRef.current) {
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

export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissions must be used within a PermissionProvider');
  }
  return context;
};

export const useUserInfo = () => {
  const { wheelGroupId, wheelGroupName, userId, email, name, role, loading } = usePermissions();
  return { wheelGroupId, wheelGroupName, userId, email, name, role, loading };
};

export default PermissionProvider;
