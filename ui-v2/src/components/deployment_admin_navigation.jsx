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

import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Navbar, Nav } from 'react-bootstrap';
import { LinkContainer } from 'react-router-bootstrap';

// Constants
const NAVIGATION_CONSTANTS = {
  APP_NAME: 'AWS Ops Wheel',
  MIN_HEIGHT: '56px',
  BACKGROUND_COLOR: '#EFEFEF'
};

const NAVIGATION_ROUTES = {
  WHEEL_GROUPS: '/app/wheelgroups'
};

const NAV_LABELS = {
  WHEEL_GROUPS: 'Wheel Groups',
  LOGOUT: 'Logout'
};

const EVENT_KEYS = {
  WHEEL_GROUPS: 1,
  LOGOUT: 2
};

const USER_INFO_LABELS = {
  SIGNED_IN: 'Signed in as:',
  DEPLOYMENT_ADMIN: 'DeploymentAdmin'
};

class DeploymentAdminNavigation extends Component {
  static propTypes = {
    userLogout: PropTypes.func.isRequired
  };

  render() {
    return (
      <Navbar expand="lg" className="px-3" style={{backgroundColor: NAVIGATION_CONSTANTS.BACKGROUND_COLOR, minHeight: NAVIGATION_CONSTANTS.MIN_HEIGHT}}>
        <Nav style={{height: '100%'}}>
          <Navbar.Brand className="me-3">
            {NAVIGATION_CONSTANTS.APP_NAME}
          </Navbar.Brand>
          <LinkContainer to={NAVIGATION_ROUTES.WHEEL_GROUPS} className="navbar-tab-active">
            <Nav.Link eventKey={EVENT_KEYS.WHEEL_GROUPS}>{NAV_LABELS.WHEEL_GROUPS}</Nav.Link>
          </LinkContainer>
        </Nav>
        <Nav className="ms-auto">
          <Navbar.Text className="me-3">
            {USER_INFO_LABELS.SIGNED_IN} <strong>{USER_INFO_LABELS.DEPLOYMENT_ADMIN}</strong>
          </Navbar.Text>
          <Nav.Link eventKey={EVENT_KEYS.LOGOUT} onClick={this.props.userLogout}>
            {NAV_LABELS.LOGOUT}
          </Nav.Link>
        </Nav>
      </Navbar>
    );
  }
}

export default DeploymentAdminNavigation;
