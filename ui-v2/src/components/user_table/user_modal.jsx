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

import React, {PropTypes, Component} from 'react';
import {Modal, Button, Form, Alert} from 'react-bootstrap';
import {apiURL, getAuthHeaders} from '../../util';

const defaultUser = {
  user_id: '',
  username: '',
  email: '',
  role: 'USER'
};

const roleOptions = [
  { value: 'ADMIN', label: 'Admin' },
  { value: 'WHEEL_ADMIN', label: 'Wheel Admin' },
  { value: 'USER', label: 'User' }
];

export default class UserModal extends Component {
  constructor(props) {
    super(props);
    this.state = {
      user: Object.assign({}, defaultUser),
      isAdd: false,
      usernameValidation: {
        isChecking: false,
        isValid: true,
        message: ''
      }
    };
    this.onChange = this.onChange.bind(this);
    this.onUsernameChange = this.onUsernameChange.bind(this);
    this.onSubmit = this.onSubmit.bind(this);
    this.modalAfterOpen = this.modalAfterOpen.bind(this);
    this.onClose = this.onClose.bind(this);
    this.checkUsernameUniqueness = this.checkUsernameUniqueness.bind(this);
    this.usernameCheckTimeout = null;
  }

  onSubmit(event) {
    event.preventDefault();
    // For updates, only send the role that can be updated
    const userData = this.state.isAdd ? {
      username: this.state.user.username,
      email: this.state.user.email,
      role: this.state.user.role
    } : {
      user_id: this.state.user.user_id,
      role: this.state.user.role
    };
    this.props.onSubmit(userData);
    this.onClose();
  };

  onClose() {
    this.props.onClose();
  }

  onChange(event) {
    const {user} = this.state;
    this.setState({user: Object.assign({}, user, {[event.target.name]: event.target.value})});
  };

  onUsernameChange(event) {
    this.onChange(event);
    
    // Debounce username validation
    if (this.usernameCheckTimeout) {
      clearTimeout(this.usernameCheckTimeout);
    }
    
    const username = event.target.value;
    if (username && username.length >= 2) {
      this.setState({
        usernameValidation: {
          isChecking: true,
          isValid: true,
          message: ''
        }
      });
      
      this.usernameCheckTimeout = setTimeout(() => {
        this.checkUsernameUniqueness(username);
      }, 500);
    } else {
      this.setState({
        usernameValidation: {
          isChecking: false,
          isValid: true,
          message: ''
        }
      });
    }
  };

  async checkUsernameUniqueness(username) {
    try {
      const response = await fetch(apiURL('tenant/users'), {
        method: 'GET',
        headers: getAuthHeaders()
      });
      
      if (response.ok) {
        const data = await response.json();
        const existingUsernames = data.users.map(u => u.name.toLowerCase());
        const isUnique = !existingUsernames.includes(username.toLowerCase());
        
        this.setState({
          usernameValidation: {
            isChecking: false,
            isValid: isUnique,
            message: isUnique ? '' : 'Username already exists'
          }
        });
      }
    } catch (error) {
      // If check fails, don't block the user
      this.setState({
        usernameValidation: {
          isChecking: false,
          isValid: true,
          message: ''
        }
      });
    }
  };

  modalAfterOpen() {
    const {user} = this.props;
    const userForEditing = user ? {...user, password: ''} : defaultUser; // Don't pre-fill password
    
    this.setState({
      isAdd: user === undefined,
      user: Object.assign({}, userForEditing),
      usernameValidation: {
        isChecking: false,
        isValid: true,
        message: ''
      }
    });
  };

  render() {
    const {isModalOpen} = this.props;
    const {user, isAdd, usernameValidation} = this.state;

    const heading = isAdd ? 'Add a new user' : 'Edit user role';
    const submitText = isAdd ? 'Add User' : 'Update Role';
    
    // Create unique IDs to avoid conflicts when multiple modals exist
    const userUsernameId = isAdd ? 'user-username-add' : `user-username-edit-${user.user_id || 'new'}`;
    const userEmailId = isAdd ? 'user-email-add' : `user-email-edit-${user.user_id || 'new'}`;
    const userPasswordId = isAdd ? 'user-password-add' : `user-password-edit-${user.user_id || 'new'}`;
    const userRoleId = isAdd ? 'user-role-add' : `user-role-edit-${user.user_id || 'new'}`;

    const isValid = isAdd ? (user.username && user.email && user.role && usernameValidation.isValid && !usernameValidation.isChecking) : user.role;

    return (
      <div>
        <Modal
          show={isModalOpen}
          onEntering={this.modalAfterOpen}
          onHide={this.onClose}
          size="lg"
        >
          <Modal.Header closeButton>
            <Modal.Title>{heading}</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <Form>
              {isAdd && (
                <>
                  <Form.Group className='mb-3'>
                    <Form.Label htmlFor={userUsernameId}>Username</Form.Label>
                    <Form.Control
                      id={userUsernameId}
                      type='text'
                      name='username'
                      onChange={this.onUsernameChange}
                      value={user.username}
                      placeholder="username"
                      required
                      isInvalid={!usernameValidation.isValid}
                    />
                    {usernameValidation.isChecking && (
                      <Form.Text className="text-info">
                        Checking username availability...
                      </Form.Text>
                    )}
                    {!usernameValidation.isChecking && usernameValidation.message && (
                      <Form.Text className={usernameValidation.isValid ? "text-success" : "text-danger"}>
                        {usernameValidation.message}
                      </Form.Text>
                    )}
                    {!usernameValidation.message && !usernameValidation.isChecking && (
                      <Form.Text className="text-muted">
                        Username will be used for login
                      </Form.Text>
                    )}
                  </Form.Group>
                  <Form.Group className='mb-3'>
                    <Form.Label htmlFor={userEmailId}>Email Address</Form.Label>
                    <Form.Control
                      id={userEmailId}
                      type='email'
                      name='email'
                      onChange={this.onChange}
                      value={user.email}
                      placeholder="user@example.com"
                      required
                    />
                  </Form.Group>
                  <div className="mb-3">
                    <div className="alert alert-info">
                      <strong>Note:</strong> User will receive a temporary password (TempPass123!) and must change it on first login.
                    </div>
                  </div>
                </>
              )}
              {!isAdd && (
                <div className="mb-3">
                  <p><strong>Username:</strong> {user.name || user.username}</p>
                </div>
              )}
              <Form.Group className='mb-3'>
                <Form.Label htmlFor={userRoleId}>Role</Form.Label>
                <Form.Select
                  id={userRoleId}
                  name='role'
                  onChange={this.onChange}
                  value={user.role}
                  required
                >
                  {roleOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Form.Select>
                <Form.Text className="text-muted">
                  {user.role === 'ADMIN' && 'Can manage all tenant settings and users'}
                  {user.role === 'WHEEL_ADMIN' && 'Can manage wheels and participants'}
                  {user.role === 'USER' && 'Can view and spin wheels'}
                </Form.Text>
              </Form.Group>
            </Form>
          </Modal.Body>
          <Modal.Footer>
                <Button
                  onClick={this.onClose}>
                  Cancel
                </Button>
                <Button
                  type='submit'
                  onClick={this.onSubmit}
                  variant='success'
                  disabled={!isValid}>
                  {submitText}
                </Button>
          </Modal.Footer>
        </Modal>
      </div>
    );
  };
}
