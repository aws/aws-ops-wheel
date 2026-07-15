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

import React, { Component } from "react";
import PropTypes from "prop-types";
import {Alert, Button, Form} from "react-bootstrap";
import {AuthenticationDetails, CognitoUser} from "amazon-cognito-identity-js";
import { withRouter } from 'react-router-dom';

// Login Component Constants
const LOGIN_CONFIG = {
  MIN_PASSWORD_LENGTH: 6,
  MIN_USERNAME_LENGTH: 1,
  CONTAINER_PADDING: '60px 0',
  FORM_MAX_WIDTH: '320px',
  INFO_MARGIN_TOP: '15px'
};

const LOGIN_MESSAGES = {
  LOGIN_BUTTON: 'Login',
  CREATE_WHEEL_GROUP_BUTTON: 'Create Wheel Group',
  USERNAME_LABEL: 'Username',
  PASSWORD_LABEL: 'Password',
  FIRST_TIME_TITLE: 'Account used for the first time.',
  FIRST_TIME_MESSAGE: 'You need to change your password.',
  INFO_MESSAGE: 'Use your username (not email) to log in. You can manage Users using the User Pool in AWS Cognito.'
};

const FORM_CONFIG = {
  USERNAME_FIELD: 'username',
  PASSWORD_FIELD: 'password',
  CONTROL_SIZE: 'lg'
};

const ALERT_VARIANTS = {
  WARNING: 'warning',
  DANGER: 'danger',
  INFO: 'info'
};

const LOGIN_STYLES = {
  container: {
    padding: LOGIN_CONFIG.CONTAINER_PADDING
  },
  form: {
    margin: '0 auto',
    maxWidth: LOGIN_CONFIG.FORM_MAX_WIDTH
  },
  infoAlert: {
    marginTop: LOGIN_CONFIG.INFO_MARGIN_TOP
  }
};

// PropTypes definitions (moved out of TypeScript interfaces)
const LOGIN_PROP_TYPES = {
  userHasAuthenticated: PropTypes.func,
  userPool: PropTypes.object,
  onCreateTenant: PropTypes.func
};

class Login extends Component {
  static propTypes = LOGIN_PROP_TYPES;
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
  newPasswordRequired = (userAttributes) => {
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

  handleCreateTenant = () => {
    // Navigate to wheel group creation page
    this.props.history.push('/app/createtenant');
  };

  handleForgotPassword = () => {
    // Navigate to forgot password page
    this.props.history.push('/forgot-password');
  };

  render() {
    const {isInFlight} = this.state;
    const errorString = this.state.error === undefined ? '' : this.state.error.message;
    let userElement, formSubmit;
    if (this.state.passwordChangeAttributes !== undefined) {
      formSubmit = this.submitNewPassword;
      userElement = <Alert variant={ALERT_VARIANTS.WARNING}>
                        <strong>{LOGIN_MESSAGES.FIRST_TIME_TITLE}</strong> <br />
                        {LOGIN_MESSAGES.FIRST_TIME_MESSAGE}
                      </Alert>

    } else {
      formSubmit = this.login;
      userElement = <Form.Group controlId={FORM_CONFIG.USERNAME_FIELD} className="mb-3">
        <Form.Label>{LOGIN_MESSAGES.USERNAME_LABEL}</Form.Label>
        <Form.Control
          autoFocus
          type={FORM_CONFIG.USERNAME_FIELD}
          value={this.state.username}
          onChange={this.handleChange}
          size={FORM_CONFIG.CONTROL_SIZE}
        />
      </Form.Group>;
    }

    let warning;

    if (errorString !== '') {
      warning = <div key='error' className={`alert alert-${ALERT_VARIANTS.DANGER}`}>{errorString}</div>
    }

    return (
      <div className="Login" style={LOGIN_STYLES.container}>
        <form onSubmit={formSubmit} style={LOGIN_STYLES.form}>
          {userElement}
          <Form.Group controlId={FORM_CONFIG.PASSWORD_FIELD} className="mb-3">
            <Form.Label>{LOGIN_MESSAGES.PASSWORD_LABEL}</Form.Label>
            <Form.Control
              value={this.state.password}
              onChange={this.handleChange}
              type={FORM_CONFIG.PASSWORD_FIELD}
              size={FORM_CONFIG.CONTROL_SIZE}
            />
          </Form.Group>

          {warning}

          <div className="d-flex gap-2">
            <Button
              className="flex-fill"
              size={FORM_CONFIG.CONTROL_SIZE}
              disabled={isInFlight || this.state.username.length < LOGIN_CONFIG.MIN_USERNAME_LENGTH || this.state.password.length < LOGIN_CONFIG.MIN_PASSWORD_LENGTH}
              type="submit"
            >
              {LOGIN_MESSAGES.LOGIN_BUTTON}
            </Button>

            {this.state.passwordChangeAttributes === undefined && (
              <Button
                className="flex-fill"
                size={FORM_CONFIG.CONTROL_SIZE}
                disabled={isInFlight}
                onClick={this.handleCreateTenant}
              >
                {LOGIN_MESSAGES.CREATE_WHEEL_GROUP_BUTTON}
              </Button>
            )}
          </div>

          {this.state.passwordChangeAttributes === undefined && (
            <div style={{ textAlign: 'center', marginTop: '15px' }}>
              <Button
                variant="link"
                size="sm"
                disabled={isInFlight}
                onClick={this.handleForgotPassword}
                style={{ textDecoration: 'none' }}
              >
                Forgot Password?
              </Button>
            </div>
          )}

          <div key='informationWindow' className={`alert alert-${ALERT_VARIANTS.INFO}`} style={LOGIN_STYLES.infoAlert}>
            {LOGIN_MESSAGES.INFO_MESSAGE}
          </div>
        </form>

      </div>
    );
  }
}

export default withRouter(Login);
