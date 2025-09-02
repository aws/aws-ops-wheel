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
import { Alert, Button, Form } from "react-bootstrap";
import { CognitoUser } from "amazon-cognito-identity-js";
import { withRouter } from 'react-router-dom';

// Forgot Password Component Constants
const FORGOT_PASSWORD_CONFIG = {
  MIN_USERNAME_LENGTH: 1,
  CONTAINER_PADDING: '60px 0',
  FORM_MAX_WIDTH: '320px',
  INFO_MARGIN_TOP: '15px'
};

const FORGOT_PASSWORD_MESSAGES = {
  SEND_CODE_BUTTON: 'Send Reset Code',
  BACK_TO_LOGIN_BUTTON: 'Back to Login',
  USERNAME_LABEL: 'Username',
  TITLE: 'Reset Your Password',
  SUBTITLE: 'Enter your username to receive a password reset code via email',
  SUCCESS_TITLE: 'Reset Code Sent!',
  SUCCESS_MESSAGE: 'Check your email for a verification code, then click the link below to reset your password.',
  CONTINUE_RESET_BUTTON: 'Enter Reset Code',
  INFO_MESSAGE: 'A 6-digit verification code will be sent to the email address associated with your username.'
};

const FORM_CONFIG = {
  USERNAME_FIELD: 'username',
  CONTROL_SIZE: 'lg'
};

const ALERT_VARIANTS = {
  SUCCESS: 'success',
  DANGER: 'danger',
  INFO: 'info'
};

const FORGOT_PASSWORD_STYLES = {
  container: {
    padding: FORGOT_PASSWORD_CONFIG.CONTAINER_PADDING
  },
  form: {
    margin: '0 auto',
    maxWidth: FORGOT_PASSWORD_CONFIG.FORM_MAX_WIDTH
  },
  infoAlert: {
    marginTop: FORGOT_PASSWORD_CONFIG.INFO_MARGIN_TOP
  },
  title: {
    textAlign: 'center',
    marginBottom: '20px'
  },
  subtitle: {
    textAlign: 'center',
    marginBottom: '30px',
    color: '#6c757d'
  }
};

// PropTypes definitions
const FORGOT_PASSWORD_PROP_TYPES = {
  userPool: PropTypes.object,
  history: PropTypes.object
};

class ForgotPassword extends Component {
  static propTypes = FORGOT_PASSWORD_PROP_TYPES;
  
  constructor(props) {
    super(props);

    this.state = {
      username: '',
      error: undefined,
      success: false,
      isInFlight: false
    };
  }

  handleChange = (event) => {
    this.setState({[event.target.id]: event.target.value});
  };

  handleBackToLogin = () => {
    this.props.history.push('/');
  };

  handleContinueToReset = () => {
    this.props.history.push('/reset-password', { username: this.state.username });
  };

  sendResetCode = (event) => {
    event.preventDefault();
    this.setState({isInFlight: true, error: undefined});
    
    const cognitoUser = new CognitoUser({
      Username: this.state.username,
      Pool: this.props.userPool
    });

    // Use forgotPassword directly - Cognito will handle email lookup internally
    this.proceedWithForgotPassword(cognitoUser, null);
  };

  proceedWithForgotPassword = (cognitoUser, userEmail) => {
    cognitoUser.forgotPassword({
      onSuccess: () => {
        this.setState({
          success: true,
          isInFlight: false,
          error: undefined,
          userEmail: userEmail
        });
      },
      onFailure: (error) => {
        console.error('Forgot password error:', error);
        let errorMessage = error.message;
        
        // Provide user-friendly error messages
        if (error.code === 'UserNotFoundException') {
          errorMessage = 'Username not found. Please check your username and try again.';
        } else if (error.code === 'InvalidParameterException') {
          errorMessage = 'Invalid username format. Please enter a valid username.';
        } else if (error.code === 'LimitExceededException') {
          errorMessage = 'Too many requests. Please wait before trying again.';
        } else if (error.code === 'UserNotConfirmedException') {
          errorMessage = 'User account is not confirmed. Please contact your administrator.';
        }
        
        this.setState({
          error: { message: errorMessage },
          isInFlight: false
        });
      },
      inputVerificationCode: () => {
        // This callback is called when the code is sent successfully
        this.setState({
          success: true,
          isInFlight: false,
          error: undefined,
          userEmail: userEmail
        });
      }
    });
  };

  render() {
    const { isInFlight, success, error } = this.state;
    const errorString = error === undefined ? '' : error.message;

    if (success) {
      const emailMessage = this.state.userEmail 
        ? `A verification code has been sent to ${this.state.userEmail}. Check your email and click the button below to reset your password.`
        : `A verification code has been sent to the email address associated with username "${this.state.username}". Check your email and click the button below to reset your password.`;

      return (
        <div className="ForgotPassword" style={FORGOT_PASSWORD_STYLES.container}>
          <div style={FORGOT_PASSWORD_STYLES.form}>
            <h2 style={FORGOT_PASSWORD_STYLES.title}>{FORGOT_PASSWORD_MESSAGES.SUCCESS_TITLE}</h2>
            
            <Alert variant={ALERT_VARIANTS.SUCCESS}>
              <strong>{emailMessage}</strong>
            </Alert>

            <div className="d-flex gap-2">
              <Button
                className="flex-fill"
                size={FORM_CONFIG.CONTROL_SIZE}
                variant="primary"
                onClick={this.handleContinueToReset}
              >
                {FORGOT_PASSWORD_MESSAGES.CONTINUE_RESET_BUTTON}
              </Button>
              
              <Button
                className="flex-fill"
                size={FORM_CONFIG.CONTROL_SIZE}
                variant="outline-secondary"
                onClick={this.handleBackToLogin}
              >
                {FORGOT_PASSWORD_MESSAGES.BACK_TO_LOGIN_BUTTON}
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="ForgotPassword" style={FORGOT_PASSWORD_STYLES.container}>
        <form onSubmit={this.sendResetCode} style={FORGOT_PASSWORD_STYLES.form}>
          <h2 style={FORGOT_PASSWORD_STYLES.title}>{FORGOT_PASSWORD_MESSAGES.TITLE}</h2>
          <p style={FORGOT_PASSWORD_STYLES.subtitle}>{FORGOT_PASSWORD_MESSAGES.SUBTITLE}</p>

          <Form.Group controlId={FORM_CONFIG.USERNAME_FIELD} className="mb-3">
            <Form.Label>{FORGOT_PASSWORD_MESSAGES.USERNAME_LABEL}</Form.Label>
            <Form.Control
              autoFocus
              type="text"
              value={this.state.username}
              onChange={this.handleChange}
              size={FORM_CONFIG.CONTROL_SIZE}
              placeholder="Enter your username"
            />
          </Form.Group>

          {errorString !== '' && (
            <div className={`alert alert-${ALERT_VARIANTS.DANGER}`}>{errorString}</div>
          )}

          <div className="d-flex gap-2">
            <Button
              className="flex-fill"
              size={FORM_CONFIG.CONTROL_SIZE}
              disabled={isInFlight || this.state.username.length < FORGOT_PASSWORD_CONFIG.MIN_USERNAME_LENGTH}
              type="submit"
            >
              {FORGOT_PASSWORD_MESSAGES.SEND_CODE_BUTTON}
            </Button>

            <Button
              className="flex-fill"
              size={FORM_CONFIG.CONTROL_SIZE}
              variant="outline-secondary"
              disabled={isInFlight}
              onClick={this.handleBackToLogin}
            >
              {FORGOT_PASSWORD_MESSAGES.BACK_TO_LOGIN_BUTTON}
            </Button>
          </div>

          <div className={`alert alert-${ALERT_VARIANTS.INFO}`} style={FORGOT_PASSWORD_STYLES.infoAlert}>
            {FORGOT_PASSWORD_MESSAGES.INFO_MESSAGE}
          </div>
        </form>
      </div>
    );
  }
}

export default withRouter(ForgotPassword);
