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

// Reset Password Component Constants
const RESET_PASSWORD_CONFIG = {
  MIN_CODE_LENGTH: 6,
  MIN_PASSWORD_LENGTH: 8,
  CONTAINER_PADDING: '60px 0',
  FORM_MAX_WIDTH: '320px',
  INFO_MARGIN_TOP: '15px'
};

const RESET_PASSWORD_MESSAGES = {
  RESET_PASSWORD_BUTTON: 'Reset Password',
  BACK_TO_LOGIN_BUTTON: 'Back to Login',
  BACK_TO_FORGOT_BUTTON: 'Back to Reset Request',
  CODE_LABEL: 'Verification Code',
  PASSWORD_LABEL: 'New Password',
  CONFIRM_PASSWORD_LABEL: 'Confirm New Password',
  TITLE: 'Enter Reset Code',
  SUBTITLE: 'Enter the 6-digit code sent to your email and your new password',
  SUCCESS_TITLE: 'Password Reset Successful!',
  SUCCESS_MESSAGE: 'Your password has been updated successfully. You can now log in with your new password.',
  LOGIN_BUTTON: 'Go to Login',
  INFO_MESSAGE: 'The verification code expires after 1 hour. If you didn\'t receive the code, go back and request a new one.',
  PASSWORD_REQUIREMENTS: 'Password must be at least 8 characters long and contain uppercase, lowercase, and numbers.'
};

const FORM_CONFIG = {
  CODE_FIELD: 'code',
  PASSWORD_FIELD: 'password',
  CONFIRM_PASSWORD_FIELD: 'confirmPassword',
  CONTROL_SIZE: 'lg'
};

const ALERT_VARIANTS = {
  SUCCESS: 'success',
  DANGER: 'danger',
  INFO: 'info'
};

const RESET_PASSWORD_STYLES = {
  container: {
    padding: RESET_PASSWORD_CONFIG.CONTAINER_PADDING
  },
  form: {
    margin: '0 auto',
    maxWidth: RESET_PASSWORD_CONFIG.FORM_MAX_WIDTH
  },
  infoAlert: {
    marginTop: RESET_PASSWORD_CONFIG.INFO_MARGIN_TOP
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
const RESET_PASSWORD_PROP_TYPES = {
  userPool: PropTypes.object,
  history: PropTypes.object,
  location: PropTypes.object
};

class ResetPassword extends Component {
  static propTypes = RESET_PASSWORD_PROP_TYPES;
  
  constructor(props) {
    super(props);

    // Get username either from navigation state or redirect to forgot password if missing
    const username = this.props.location.state?.username;
    if (!username) {
      this.props.history.push('/forgot-password');
      return;
    }

    this.state = {
      username: username,
      code: '',
      password: '',
      confirmPassword: '',
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

  handleBackToForgot = () => {
    this.props.history.push('/forgot-password');
  };

  validateForm = () => {
    // Check if passwords match
    if (this.state.password !== this.state.confirmPassword) {
      this.setState({
        error: { message: 'Passwords do not match. Please enter the same password in both fields.' }
      });
      return false;
    }

    // Check password length
    if (this.state.password.length < RESET_PASSWORD_CONFIG.MIN_PASSWORD_LENGTH) {
      this.setState({
        error: { message: `Password must be at least ${RESET_PASSWORD_CONFIG.MIN_PASSWORD_LENGTH} characters long.` }
      });
      return false;
    }

    // Check password complexity (basic check)
    const hasUpperCase = /[A-Z]/.test(this.state.password);
    const hasLowerCase = /[a-z]/.test(this.state.password);
    const hasNumbers = /\d/.test(this.state.password);

    if (!hasUpperCase || !hasLowerCase || !hasNumbers) {
      this.setState({
        error: { message: 'Password must contain at least one uppercase letter, one lowercase letter, and one number.' }
      });
      return false;
    }

    return true;
  };

  resetPassword = (event) => {
    event.preventDefault();
    
    if (!this.validateForm()) {
      return;
    }

    this.setState({isInFlight: true, error: undefined});
    
    const cognitoUser = new CognitoUser({
      Username: this.state.username,
      Pool: this.props.userPool
    });

    cognitoUser.confirmPassword(this.state.code, this.state.password, {
      onSuccess: () => {
        this.setState({
          success: true,
          isInFlight: false,
          error: undefined
        });
      },
      onFailure: (error) => {
        console.error('Reset password error:', error);
        let errorMessage = error.message;
        
        // Provide user-friendly error messages
        if (error.code === 'CodeMismatchException') {
          errorMessage = 'Invalid verification code. Please check the code and try again.';
        } else if (error.code === 'ExpiredCodeException') {
          errorMessage = 'Verification code has expired. Please request a new code.';
        } else if (error.code === 'InvalidPasswordException') {
          errorMessage = 'Password does not meet requirements. Please choose a stronger password.';
        } else if (error.code === 'LimitExceededException') {
          errorMessage = 'Too many attempts. Please wait before trying again.';
        } else if (error.code === 'UserNotFoundException') {
          errorMessage = 'User not found. Please start the password reset process again.';
        } else if (error.code === 'InvalidParameterException') {
          errorMessage = 'Invalid code or password format. Please check your input.';
        }
        
        this.setState({
          error: { message: errorMessage },
          isInFlight: false
        });
      }
    });
  };

  render() {
    const { isInFlight, success, error } = this.state;
    const errorString = error === undefined ? '' : error.message;

    if (success) {
      return (
        <div className="ResetPassword" style={RESET_PASSWORD_STYLES.container}>
          <div style={RESET_PASSWORD_STYLES.form}>
            <h2 style={RESET_PASSWORD_STYLES.title}>{RESET_PASSWORD_MESSAGES.SUCCESS_TITLE}</h2>
            
            <Alert variant={ALERT_VARIANTS.SUCCESS}>
              <strong>{RESET_PASSWORD_MESSAGES.SUCCESS_MESSAGE}</strong>
            </Alert>

            <Button
              className="w-100"
              size={FORM_CONFIG.CONTROL_SIZE}
              variant="primary"
              onClick={this.handleBackToLogin}
            >
              {RESET_PASSWORD_MESSAGES.LOGIN_BUTTON}
            </Button>
          </div>
        </div>
      );
    }

    const isFormValid = this.state.code.length >= RESET_PASSWORD_CONFIG.MIN_CODE_LENGTH &&
                       this.state.password.length >= RESET_PASSWORD_CONFIG.MIN_PASSWORD_LENGTH &&
                       this.state.confirmPassword.length >= RESET_PASSWORD_CONFIG.MIN_PASSWORD_LENGTH;

    return (
      <div className="ResetPassword" style={RESET_PASSWORD_STYLES.container}>
        <form onSubmit={this.resetPassword} style={RESET_PASSWORD_STYLES.form}>
          <h2 style={RESET_PASSWORD_STYLES.title}>{RESET_PASSWORD_MESSAGES.TITLE}</h2>
          <p style={RESET_PASSWORD_STYLES.subtitle}>{RESET_PASSWORD_MESSAGES.SUBTITLE}</p>

          <Form.Group controlId={FORM_CONFIG.CODE_FIELD} className="mb-3">
            <Form.Label>{RESET_PASSWORD_MESSAGES.CODE_LABEL}</Form.Label>
            <Form.Control
              autoFocus
              type="text"
              value={this.state.code}
              onChange={this.handleChange}
              size={FORM_CONFIG.CONTROL_SIZE}
              placeholder="Enter 6-digit code"
              maxLength="6"
            />
          </Form.Group>

          <Form.Group controlId={FORM_CONFIG.PASSWORD_FIELD} className="mb-3">
            <Form.Label>{RESET_PASSWORD_MESSAGES.PASSWORD_LABEL}</Form.Label>
            <Form.Control
              type="password"
              value={this.state.password}
              onChange={this.handleChange}
              size={FORM_CONFIG.CONTROL_SIZE}
              placeholder="Enter new password"
            />
          </Form.Group>

          <Form.Group controlId={FORM_CONFIG.CONFIRM_PASSWORD_FIELD} className="mb-3">
            <Form.Label>{RESET_PASSWORD_MESSAGES.CONFIRM_PASSWORD_LABEL}</Form.Label>
            <Form.Control
              type="password"
              value={this.state.confirmPassword}
              onChange={this.handleChange}
              size={FORM_CONFIG.CONTROL_SIZE}
              placeholder="Confirm new password"
            />
          </Form.Group>

          {errorString !== '' && (
            <div className={`alert alert-${ALERT_VARIANTS.DANGER}`}>{errorString}</div>
          )}

          <div className="d-flex gap-2 mb-3">
            <Button
              className="flex-fill"
              size={FORM_CONFIG.CONTROL_SIZE}
              disabled={isInFlight || !isFormValid}
              type="submit"
            >
              {RESET_PASSWORD_MESSAGES.RESET_PASSWORD_BUTTON}
            </Button>

            <Button
              className="flex-fill"
              size={FORM_CONFIG.CONTROL_SIZE}
              variant="outline-secondary"
              disabled={isInFlight}
              onClick={this.handleBackToForgot}
            >
              {RESET_PASSWORD_MESSAGES.BACK_TO_FORGOT_BUTTON}
            </Button>
          </div>

          <Button
            className="w-100 mb-3"
            size={FORM_CONFIG.CONTROL_SIZE}
            variant="outline-primary"
            disabled={isInFlight}
            onClick={this.handleBackToLogin}
          >
            {RESET_PASSWORD_MESSAGES.BACK_TO_LOGIN_BUTTON}
          </Button>

          <div className={`alert alert-${ALERT_VARIANTS.INFO}`} style={RESET_PASSWORD_STYLES.infoAlert}>
            <small>
              <strong>Requirements:</strong><br />
              {RESET_PASSWORD_MESSAGES.PASSWORD_REQUIREMENTS}<br /><br />
              <strong>Note:</strong><br />
              {RESET_PASSWORD_MESSAGES.INFO_MESSAGE}
            </small>
          </div>
        </form>
      </div>
    );
  }
}

export default withRouter(ResetPassword);
