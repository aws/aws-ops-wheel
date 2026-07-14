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
import {getStoredIdToken, clearStoredTokens} from './auth_storage';

export const DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss';

// Only absolute http/https URLs are safe to hand to window.open() or an <a href>.
// Everything else (javascript:, data:, vbscript:, file:, relative, malformed)
// is rejected to prevent stored XSS from a participant_url. This mirrors the
// server-side scheme allowlist in api-v2/participant_operations.py and is
// defense-in-depth: the frontend must never trust a stored URL is safe.
export function isSafeHttpUrl(url) {
  if (typeof url !== 'string' || url.length === 0) {
    return false;
  }
  let parsed;
  try {
    parsed = new URL(url);
  } catch (e) {
    return false;
  }
  return parsed.protocol === 'http:' || parsed.protocol === 'https:';
}
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

// V2 API Configuration for Multi-Wheel-Group Architecture
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
  // Read the ID token from the in-memory auth store (never localStorage) so a
  // stored-XSS payload cannot read it. See auth_storage.jsx.
  const idToken = getStoredIdToken();

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
      // Clear in-memory tokens and redirect to login. See auth_storage.jsx.
      clearStoredTokens();
      window.location.href = '/app/login';
      return;
    }
    
    return response;
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
};

// Wheel Group context utilities
export const getTenantContext = () => {
  const idToken = getStoredIdToken();
  if (idToken) {
    try {
      // Decode JWT payload (this is safe for reading, not for validation)
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      return {
      wheel_group_id: payload['custom:wheel_group_id'],
      wheel_group_name: payload['custom:wheel_group_name'],
        role: payload['custom:role'],
        user_id: payload.sub
      };
    } catch (error) {
      console.error('Failed to decode wheel group context:', error);
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
        // For external URLs, use regular anchor tag. Only render an href for
        // safe http/https URLs; anything else (javascript:, data:, ...) is
        // rendered as inert text so a stored malicious participant_url cannot
        // execute when clicked. rel prevents reverse-tabnabbing via window.opener.
        const {to, ...anchorProps} = props;
        if (isSafeHttpUrl(to)) {
          link = <a href={to} rel='noopener noreferrer' {...anchorProps}>{props.children}</a>;
        } else {
          const {target, ...safeProps} = anchorProps;
          link = <span {...safeProps}>{props.children}</span>;
        }
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
