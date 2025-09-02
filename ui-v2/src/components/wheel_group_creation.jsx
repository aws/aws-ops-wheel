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
import { Alert, Button, Form, Container, Row, Col } from "react-bootstrap";
import { withRouter } from 'react-router-dom';
import { apiURL } from "../util";

// Wheel Group Creation Component Constants
const WHEEL_GROUP_CREATION_CONFIG = {
  MIN_PASSWORD_LENGTH: 8,
  MIN_USERNAME_LENGTH: 2,
  MIN_WHEEL_GROUP_NAME_LENGTH: 2,
  CONTAINER_PADDING: '60px 0',
  FORM_MAX_WIDTH: '480px',
  ERROR_MARGIN_TOP: '15px'
};

const WHEEL_GROUP_CREATION_MESSAGES = {
  CREATE_WHEEL_GROUP_BUTTON: 'Create Wheel Group',
  CREATING_WHEEL_GROUP: 'Creating Wheel Group...',
  USERNAME_LABEL: 'Admin Username',
  EMAIL_LABEL: 'Email Address', 
  PASSWORD_LABEL: 'Password',
  WHEEL_GROUP_NAME_LABEL: 'Wheel Group Name',
  BACK_TO_LOGIN: 'Back to Login',
  TITLE: 'Create New Wheel Group',
  SUBTITLE: 'Set up your organization and admin account'
};

const FORM_CONFIG = {
  USERNAME_FIELD: 'username',
  EMAIL_FIELD: 'email',
  PASSWORD_FIELD: 'password',
  WHEEL_GROUP_NAME_FIELD: 'wheelGroupName',
  CONTROL_SIZE: 'lg'
};

const ALERT_VARIANTS = {
  DANGER: 'danger',
  SUCCESS: 'success'
};

const WHEEL_GROUP_CREATION_STYLES = {
  container: {
    padding: WHEEL_GROUP_CREATION_CONFIG.CONTAINER_PADDING
  },
  form: {
    margin: '0 auto',
    maxWidth: WHEEL_GROUP_CREATION_CONFIG.FORM_MAX_WIDTH
  },
  title: {
    textAlign: 'center',
    marginBottom: '30px'
  },
  subtitle: {
    textAlign: 'center',
    marginBottom: '30px',
    color: '#666'
  },
  errorAlert: {
    marginTop: WHEEL_GROUP_CREATION_CONFIG.ERROR_MARGIN_TOP
  }
};

// PropTypes definitions
const WHEEL_GROUP_CREATION_PROP_TYPES = {
  onWheelGroupCreated: PropTypes.func,
  onBackToLogin: PropTypes.func
};

class WheelGroupCreation extends Component {
  static propTypes = WHEEL_GROUP_CREATION_PROP_TYPES;

  constructor(props) {
    super(props);

    this.state = {
      username: '',
      email: '',
      password: '',
      wheelGroupName: '',
      error: undefined,
      isInFlight: false,
    };
  }

  handleChange = (event) => {
    this.setState({[event.target.id]: event.target.value});
  };

  validateForm = () => {
    const { username, email, password, wheelGroupName } = this.state;
    
    if (username.length < WHEEL_GROUP_CREATION_CONFIG.MIN_USERNAME_LENGTH) {
      return 'Username must be at least 2 characters long';
    }
    
    if (!email || !email.includes('@')) {
      return 'Please enter a valid email address';
    }
    
    if (password.length < WHEEL_GROUP_CREATION_CONFIG.MIN_PASSWORD_LENGTH) {
      return 'Password must be at least 8 characters long';
    }
    
    if (wheelGroupName.length < WHEEL_GROUP_CREATION_CONFIG.MIN_WHEEL_GROUP_NAME_LENGTH) {
      return 'Wheel group name must be at least 2 characters long';
    }
    
    return null;
  };

  createTenant = async (event) => {
    event.preventDefault();
    
    const validationError = this.validateForm();
    if (validationError) {
      this.setState({ error: { message: validationError } });
      return;
    }

    this.setState({ isInFlight: true, error: undefined });

    try {
      const response = await fetch(`${apiURL('wheel-group/create-public')}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          wheel_group_name: this.state.wheelGroupName,
          admin_user: {
            username: this.state.username,
            email: this.state.email,
            password: this.state.password
          }
        })
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Failed to create wheel group');
      }

      // Wheel group created successfully
      this.setState({ 
        isInFlight: false,
        error: { 
          message: `Wheel group "${this.state.wheelGroupName}" created successfully! Use username "${this.state.username}" to log in.`,
          isSuccess: true 
        }
      });
      
      // Redirect to login after a short delay
      setTimeout(() => {
        if (this.props.onWheelGroupCreated) {
          this.props.onWheelGroupCreated(result, {
            email: this.state.email,
            password: this.state.password
          });
        }
      }, 2000);
      
    } catch (error) {
      console.error('Wheel group creation error:', error);
      this.setState({ 
        error: { message: error.message || 'Failed to create wheel group' },
        isInFlight: false 
      });
    }
  };

  render() {
    const { isInFlight, error } = this.state;
    const errorString = error ? error.message : '';

    const isFormValid = 
      this.state.username.length >= WHEEL_GROUP_CREATION_CONFIG.MIN_USERNAME_LENGTH &&
      this.state.email.includes('@') &&
      this.state.password.length >= WHEEL_GROUP_CREATION_CONFIG.MIN_PASSWORD_LENGTH &&
      this.state.wheelGroupName.length >= WHEEL_GROUP_CREATION_CONFIG.MIN_WHEEL_GROUP_NAME_LENGTH;

    return (
      <Container fluid>
        <Row className="justify-content-center">
          <Col xs={12} sm={8} md={6} lg={4}>
            <div className="WheelGroupCreation" style={WHEEL_GROUP_CREATION_STYLES.container}>
              <h2 style={WHEEL_GROUP_CREATION_STYLES.title}>{WHEEL_GROUP_CREATION_MESSAGES.TITLE}</h2>
              <p style={WHEEL_GROUP_CREATION_STYLES.subtitle}>{WHEEL_GROUP_CREATION_MESSAGES.SUBTITLE}</p>
              
              <form onSubmit={this.createTenant} style={WHEEL_GROUP_CREATION_STYLES.form}>
                <Form.Group controlId={FORM_CONFIG.WHEEL_GROUP_NAME_FIELD} className="mb-3">
                  <Form.Label>{WHEEL_GROUP_CREATION_MESSAGES.WHEEL_GROUP_NAME_LABEL}</Form.Label>
                  <Form.Control
                    autoFocus
                    type="text"
                    value={this.state.wheelGroupName}
                    onChange={this.handleChange}
                    size={FORM_CONFIG.CONTROL_SIZE}
                    placeholder="Your Organization Name"
                  />
                </Form.Group>

                <Form.Group controlId={FORM_CONFIG.USERNAME_FIELD} className="mb-3">
                  <Form.Label>{WHEEL_GROUP_CREATION_MESSAGES.USERNAME_LABEL}</Form.Label>
                  <Form.Control
                    type="text"
                    value={this.state.username}
                    onChange={this.handleChange}
                    size={FORM_CONFIG.CONTROL_SIZE}
                    placeholder="Admin Username"
                  />
                </Form.Group>

                <Form.Group controlId={FORM_CONFIG.EMAIL_FIELD} className="mb-3">
                  <Form.Label>{WHEEL_GROUP_CREATION_MESSAGES.EMAIL_LABEL}</Form.Label>
                  <Form.Control
                    type="email"
                    value={this.state.email}
                    onChange={this.handleChange}
                    size={FORM_CONFIG.CONTROL_SIZE}
                    placeholder="admin@yourorganization.com"
                  />
                </Form.Group>

                <Form.Group controlId={FORM_CONFIG.PASSWORD_FIELD} className="mb-3">
                  <Form.Label>{WHEEL_GROUP_CREATION_MESSAGES.PASSWORD_LABEL}</Form.Label>
                  <Form.Control
                    type="password"
                    value={this.state.password}
                    onChange={this.handleChange}
                    size={FORM_CONFIG.CONTROL_SIZE}
                    placeholder="Choose a secure password"
                  />
                </Form.Group>

                {errorString && (
                  <Alert variant={error?.isSuccess ? ALERT_VARIANTS.SUCCESS : ALERT_VARIANTS.DANGER} style={WHEEL_GROUP_CREATION_STYLES.errorAlert}>
                    {errorString}
                  </Alert>
                )}

                <Button
                  className="d-grid mb-3"
                  size={FORM_CONFIG.CONTROL_SIZE}
                  disabled={isInFlight || !isFormValid}
                  type="submit"
                >
                  {isInFlight ? WHEEL_GROUP_CREATION_MESSAGES.CREATING_WHEEL_GROUP : WHEEL_GROUP_CREATION_MESSAGES.CREATE_WHEEL_GROUP_BUTTON}
                </Button>

                <Button
                  className="d-grid"
                  size={FORM_CONFIG.CONTROL_SIZE}
                  variant="outline-secondary"
                  disabled={isInFlight}
                  onClick={() => this.props.history.push('/')}
                >
                  {WHEEL_GROUP_CREATION_MESSAGES.BACK_TO_LOGIN}
                </Button>
              </form>
            </div>
          </Col>
        </Row>
      </Container>
    );
  }
}

export default withRouter(WheelGroupCreation);
