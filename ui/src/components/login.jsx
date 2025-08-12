l/*
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

import React, { Component, PropTypes } from "react";
import {Alert, Button, Form} from "react-bootstrap";
import {AuthenticationDetails, CognitoUser, CognitoUserPool} from "amazon-cognito-identity-js";

interface LoginProps {
  userHasAuthenticated: PropTypes.func,
  userPool: CognitoUserPool | undefined,
}

interface LoginState {
  username: string,
  password: string,
  passwordChangeAttributes: Object,
  error: Object,
  isInFlight: boolean,
  user: CognitoUser | undefined,
}

export default class Login extends Component<LoginProps, LoginState> {
  constructor(props) {
    super(props);

    this.state = {
      username: '',
      password: '',
      passwordChangeAttributes: undefined,
      error: undefined,
      isInFlight: false,
      user: undefined,
    };
  }

  // amazon-cognito-identity-js CognitoUser.authenticateUser() Callback
  onSuccess = () => {
    this.setState({passwordChangeAttributes: undefined, error: undefined, isInFlight: false});
    this.props.userHasAuthenticated(true);
  };

  // amazon-cognito-identity-js CognitoUser.authenticateUser() Callback
  onFailure = (error) => {
    this.setState({error, isInFlight: false});
  };

  // amazon-cognito-identity-js CognitoUser.authenticateUser() Callback
  newPasswordRequired = (userAttributes: Object) => {
    // User was signed up by an admin and must provide new
    // password and required attributes, if any, to complete
    // authentication.

    // the api doesn't accept this field back
    delete userAttributes.email_verified;
    delete userAttributes.email;
    this.setState({passwordChangeAttributes: userAttributes, error: undefined, password: '', isInFlight: false});
  };

  submitNewPassword = (event) => {
    event.preventDefault();
    this.setState({isInFlight: true});
    this.state.user.completeNewPasswordChallenge(this.state.password, this.state.passwordChangeAttributes, this);
  };

  handleChange = (event) => {
    this.setState({[event.target.id]: event.target.value});
  };

  login = (event) => {
    event.preventDefault();
    this.setState({isInFlight: true});
    const user = new CognitoUser({ Username: this.state.username, Pool: this.props.userPool });
    const authenticationData = { Username: this.state.username, Password: this.state.password };
    const authenticationDetails = new AuthenticationDetails(authenticationData);
    this.setState({user}, () => user.authenticateUser(authenticationDetails, this));
  };

  render() {
    const {isInFlight} = this.state;
    const errorString = this.state.error === undefined ? '' : this.state.error.message;
    let userElement, formSubmit;
    if (this.state.passwordChangeAttributes !== undefined) {
      formSubmit = this.submitNewPassword;
      userElement = <Alert
                      variant="warning">
                        <strong>Account used for the first time.</strong> <br />
                        You need to change your password.
                      </Alert>

    } else {
      formSubmit = this.login;
      userElement = <Form.Group controlId="username" className="mb-3">
        <Form.Label>Username</Form.Label>
        <Form.Control
          autoFocus
          type="username"
          value={this.state.username}
          onChange={this.handleChange}
          size="lg"
        />
      </Form.Group>;
    }

    let warning;

    if (errorString !== '') {
      warning = <div key='error' className='alert alert-danger'>{errorString}</div>
    }

    return (
      <div className="Login" style={{padding: '60px 0'}}>
        <form onSubmit={formSubmit} style={{margin: '0 auto', maxWidth: '320px'}}>
          {userElement}
          <Form.Group controlId="password" className="mb-3">
            <Form.Label>Password</Form.Label>
            <Form.Control
              value={this.state.password}
              onChange={this.handleChange}
              type="password"
              size="lg"
            />
          </Form.Group>

          {warning}

          <Button
            className="d-grid"
            size="lg"
            disabled={isInFlight || this.state.username.length === 0 || this.state.password.length < 6}
            type="submit"
          >
            Login
          </Button>

          <div key='informationWindow' className='alert alert-info' style={{marginTop: '15px'}}>
            You can manage Users using the User Pool in AWS Cognito.
          </div>
        </form>

      </div>
    );
  }
}
