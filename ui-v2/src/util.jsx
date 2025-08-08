/*
 * Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import React, {Component} from 'react';
import moment from 'moment';
import * as moment_tz from 'moment-timezone';
import {Link} from 'react-router-dom';

export const DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss';
export function formatDateTime(timestamp, withTimeZone) {
    if (withTimeZone) {
        const dateTimeFormat = 'YYYY-MM-DD HH:mm:ss z';
        return moment_tz.tz(timestamp, moment_tz.tz.guess()).format(dateTimeFormat);
    } else {
        return moment(timestamp).format(DATE_FORMAT);
    }
}

export const WHEEL_COLORS = [
    '#FF9900',
    '#007dbc',
    '#ec7211',
    '#FFFFFF',
    '#6aaf35',
    '#aab7b8',
    '#df3312',
    '#545b64',
    '#eaeded',
    '#eb5f07',
    '#FAFAFA',
    '#00a1c9',
    '#F2F4F4',
    '#1e8900',
    '#d5dbdb',
    '#ff5746',
];

// V2 API Configuration for Multi-tenant Architecture  
// Config is loaded dynamically from /app/config.json deployed by CloudFormation
let dynamicConfig = null;

export const apiURL = (urlSuffix) => {
  if (process.env.NODE_ENV === 'test') {
    return `http://localhost/app/api/${urlSuffix}`;
  }
  
  // Remove special case for config - treat it like other API calls
  // For API calls, use the base URL from loaded config
  if (dynamicConfig && dynamicConfig.API_BASE_URL) {
    return `${dynamicConfig.API_BASE_URL}/${urlSuffix}`;
  }
  
  // Fallback: use relative paths through CloudFront proxy
  return `/app/api/v2/${urlSuffix}`;
};

// Function to set the dynamic config once it's loaded
export const setAPIConfig = (config) => {
  dynamicConfig = config;
};

export const staticURL = (urlSuffix) => {
  const urlPrefix = (process.env.NODE_ENV === 'test') ? 'http://localhost' : '';
  return (`${urlPrefix}/app/static/${urlSuffix}`);
};

// Authentication utilities for JWT tokens
export const getAuthHeaders = () => {
  // First try the simple key (for compatibility)
  let idToken = localStorage.getItem('idToken');
  
  // If not found, look for Cognito-stored ID token
  if (!idToken) {
    // Find Cognito ID token in localStorage
    const cognitoKeys = Object.keys(localStorage).filter(key => 
      key.includes('CognitoIdentityServiceProvider') && key.endsWith('.idToken')
    );
    
    if (cognitoKeys.length > 0) {
      idToken = localStorage.getItem(cognitoKeys[0]);
    }
  }
  
  if (idToken) {
    return {
      'Authorization': `Bearer ${idToken}`,
      'Content-Type': 'application/json'
    };
  }
  return {
    'Content-Type': 'application/json'
  };
};

// Enhanced fetch wrapper with authentication
export const authenticatedFetch = async (url, options = {}) => {
  const headers = {
    ...getAuthHeaders(),
    ...(options.headers || {})
  };
  
  const fetchOptions = {
    ...options,
    headers
  };
  
  try {
    const response = await fetch(url, fetchOptions);
    
    // Handle authentication errors
    if (response.status === 401 || response.status === 403) {
      // Clear stored tokens and redirect to login
      localStorage.removeItem('idToken');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      window.location.href = '/app/login';
      return;
    }
    
    return response;
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
};

// Tenant context utilities
export const getTenantContext = () => {
  const idToken = localStorage.getItem('idToken');
  if (idToken) {
    try {
      // Decode JWT payload (this is safe for reading, not for validation)
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      return {
        tenant_id: payload['custom:tenant_id'],
        tenant_name: payload['custom:tenant_name'],
        role: payload['custom:role'],
        user_id: payload.sub
      };
    } catch (error) {
      console.error('Failed to decode tenant context:', error);
      return null;
    }
  }
  return null;
};

/* This is a wrapper around Link to disable Links while testing and apply a local route prefix.
   <Link> cannot exist outside of a router context (it triggers an Invariant), but creating a router
   context makes it very difficult to access the internals of the object via enzyme as it is wrapped by the
   <Router>.
*/
export class LinkWrapper extends Component {
  render () {
    let link;
    let props = Object.assign({}, this.props);
    const isRemote = props.remote === true;

    if (!isRemote)
      props.to = `/app/${props.to}`;

    if ('remote' in props)
      delete props.remote;

    if (process.env.NODE_ENV === 'test')
      link = <div> {props.to} {props.children} </div>;
    else {
      /* istanbul ignore next */
      if (isRemote) {
        // For external URLs, use regular anchor tag
        const {to, ...anchorProps} = props;
        link = <a href={to} {...anchorProps}>{props.children}</a>;
      } else {
        // For internal routes, use React Router Link
        link = <Link {...props}>{props.children}</Link>;
      }
    }

    return (
      <div>
        {link}
      </div>
    );
  }
}
