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

interface NavigationProps {
  userPool: CognitoUserPool,
  userLogout: PropTypes.func,
}

class Navigation extends Component<NavigationProps> {
  render() {
    const username = this.props.userPool.getCurrentUser().getUsername();

    return(
      <Navbar expand="lg" className="px-3" style={{backgroundColor: '#EFEFEF', minHeight: '56px'}}>
        <Nav style={{height: '100%'}}>
          <Navbar.Brand className="me-3">
            The Wheel
          </Navbar.Brand>
          <LinkContainer to="/app" className="navbar-tab-active">
            <Nav.Link eventKey={1}>Wheels</Nav.Link>
          </LinkContainer>
        </Nav>
        <Nav className="ms-auto">
          <Navbar.Text className="me-3">
            Signed in as: <strong>{username}</strong>
          </Navbar.Text>
          <Nav.Link eventKey={3} onClick={this.props.userLogout}>Logout</Nav.Link>
        </Nav>
      </Navbar>
    )
  }
}

export default Navigation;
