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
import {Navbar, Nav, NavItem} from 'react-bootstrap';
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
      <Navbar fluid={true}>
        <Navbar.Header>
          <Navbar.Brand>
            The Wheel
          </Navbar.Brand>
        </Navbar.Header>
        <Nav>
          <LinkContainer to="/">
            <NavItem eventKey={1}>Wheels</NavItem>
          </LinkContainer>
        </Nav>
        <Nav pullRight>
            <NavItem eventKey={3} onClick={this.props.userLogout}>Logout</NavItem>
        </Nav>
        <Navbar.Text pullRight>
          Signed in as: <strong>{username}</strong>
        </Navbar.Text>
      </Navbar>
    )
  }
}

export default Navigation;
