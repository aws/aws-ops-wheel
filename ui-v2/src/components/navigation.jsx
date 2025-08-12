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

import React, {Component, PropTypes} from 'react';
import {Navbar, Nav} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap';
import {CognitoUserPool} from 'amazon-cognito-identity-js';
import {apiURL, authenticatedFetch} from '../util';
import PermissionGuard from './PermissionGuard';

interface NavigationProps {
  userPool: CognitoUserPool,
  userLogout: PropTypes.func,
}

class Navigation extends Component<NavigationProps> {
  constructor(props) {
    super(props);
    this.state = {
      tenantName: null,
      loading: true
    };
  }

  componentDidMount() {
    this.fetchTenantInfo();
  }

  fetchTenantInfo = async () => {
    try {
      const response = await authenticatedFetch(apiURL('tenant'));
      if (response && response.ok) {
        const tenant = await response.json();
        this.setState({
          tenantName: tenant.tenant_name,
          loading: false
        });
      } else {
        this.setState({ loading: false });
      }
    } catch (error) {
      console.error('Failed to fetch tenant info:', error);
      this.setState({ loading: false });
    }
  };

  render() {
    const username = this.props.userPool.getCurrentUser().getUsername();
    const { tenantName, loading } = this.state;

    return(
      <Navbar expand="lg" className="px-3" style={{backgroundColor: '#EFEFEF', minHeight: '56px'}}>
        <Nav style={{height: '100%'}}>
          <Navbar.Brand className="me-3">
            AWS Ops Wheel
          </Navbar.Brand>
          <LinkContainer to="/app" className="navbar-tab-active">
            <Nav.Link eventKey={1}>Wheels</Nav.Link>
          </LinkContainer>
          <PermissionGuard permission="manage_users">
            <LinkContainer to="/app/users">
              <Nav.Link eventKey={2}>Users</Nav.Link>
            </LinkContainer>
          </PermissionGuard>
        </Nav>
        <Nav className="ms-auto">
          <Navbar.Text className="me-3">
            Signed in as: <strong>{username}</strong>
            {!loading && tenantName && (
              <span> | Tenant: <strong>{tenantName}</strong></span>
            )}
          </Navbar.Text>
          <Nav.Link eventKey={3} onClick={this.props.userLogout}>Logout</Nav.Link>
        </Nav>
      </Navbar>
    )
  }
}

export default Navigation;
