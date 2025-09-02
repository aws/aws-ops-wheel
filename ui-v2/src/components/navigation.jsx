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
import PropTypes from 'prop-types';
import {Navbar, Nav} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap';
import {CognitoUserPool} from 'amazon-cognito-identity-js';
import {apiURL, authenticatedFetch} from '../util';
import PermissionGuard from './PermissionGuard';

// Constants
const NAVIGATION_CONSTANTS = {
  APP_NAME: 'AWS Ops Wheel',
  MIN_HEIGHT: '56px',
  BACKGROUND_COLOR: '#EFEFEF'
};

const NAVIGATION_ROUTES = {
  WHEELS: '/app/wheels',
  USERS: '/app/users'
};

const NAV_LABELS = {
  WHEELS: 'Wheels',
  USERS: 'Users',
  LOGOUT: 'Logout'
};

const EVENT_KEYS = {
  WHEELS: 1,
  USERS: 2,
  LOGOUT: 3
};

const USER_INFO_LABELS = {
  SIGNED_IN: 'Signed in as:',
  WHEEL_GROUP: 'Wheel Group:'
};

const REQUIRED_PERMISSIONS = {
  MANAGE_USERS: 'manage_users'
};

class Navigation extends Component {
  constructor(props) {
    super(props);
    this.state = {
      wheelGroupName: null,
      loading: true
    };
  }

  componentDidMount() {
    this.fetchWheelGroupInfo();
  }

  fetchWheelGroupInfo = async () => {
    try {
      const response = await authenticatedFetch(apiURL('wheel-group'));
      if (response && response.ok) {
        const wheelGroup = await response.json();
        this.setState({
          wheelGroupName: wheelGroup.wheel_group_name,
          loading: false
        });
      } else {
        this.setState({ loading: false });
      }
    } catch (error) {
      console.error('Failed to fetch wheel group info:', error);
      this.setState({ loading: false });
    }
  };

  render() {
    const username = this.props.userPool.getCurrentUser().getUsername();
    const { wheelGroupName, loading } = this.state;

    return(
      <Navbar expand="lg" className="px-3" style={{backgroundColor: NAVIGATION_CONSTANTS.BACKGROUND_COLOR, minHeight: NAVIGATION_CONSTANTS.MIN_HEIGHT}}>
        <Nav style={{height: '100%'}}>
          <Navbar.Brand className="me-3">
            {NAVIGATION_CONSTANTS.APP_NAME}
          </Navbar.Brand>
          <LinkContainer to={NAVIGATION_ROUTES.WHEELS} className="navbar-tab-active">
            <Nav.Link eventKey={EVENT_KEYS.WHEELS}>{NAV_LABELS.WHEELS}</Nav.Link>
          </LinkContainer>
          <PermissionGuard permission={REQUIRED_PERMISSIONS.MANAGE_USERS}>
            <LinkContainer to={NAVIGATION_ROUTES.USERS}>
              <Nav.Link eventKey={EVENT_KEYS.USERS}>{NAV_LABELS.USERS}</Nav.Link>
            </LinkContainer>
          </PermissionGuard>
        </Nav>
        <Nav className="ms-auto">
          <Navbar.Text className="me-3">
            {USER_INFO_LABELS.SIGNED_IN} <strong>{username}</strong>
            {!loading && wheelGroupName && (
              <span> | {USER_INFO_LABELS.WHEEL_GROUP} <strong>{wheelGroupName}</strong></span>
            )}
          </Navbar.Text>
          <Nav.Link eventKey={EVENT_KEYS.LOGOUT} onClick={this.props.userLogout}>{NAV_LABELS.LOGOUT}</Nav.Link>
        </Nav>
      </Navbar>
    )
  }
}

export default Navigation;
