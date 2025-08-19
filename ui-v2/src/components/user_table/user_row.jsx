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
import UserModal from './user_modal';
import ConfirmationModal from '../confirmation_modal';
import {Button, ButtonGroup, ButtonToolbar, Badge} from 'react-bootstrap';
import {formatDateTime} from '../../util';
import PermissionGuard from '../PermissionGuard';

// Constants
const INITIAL_STATE = {
  isUserModalOpen: false,
  isConfirmationModalOpen: false,
};

const ROLE_VARIANTS = {
  'ADMIN': 'danger',      // Red background for Admin
  'WHEEL_ADMIN': 'warning', // Yellow background for Wheel Admin
  'USER': 'primary',      // Blue background for User
};

const ROLE_DISPLAY_NAMES = {
  'ADMIN': 'Admin',
  'WHEEL_ADMIN': 'Wheel Admin',
  'USER': 'User',
};

export default class UserRow extends Component {
  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
  }

  toggleUserModal = () => {
    this.setState({isUserModalOpen: !this.state.isUserModalOpen});
  }

  toggleConfirmationModal = () => {
    this.setState({isConfirmationModalOpen: !this.state.isConfirmationModalOpen});
  }

  handleUserEdit = (user) => {
    this.props.onEdit(user);
  };

  handleUserDelete = () => {
    this.props.onDelete(this.props.user);
  };

  getRoleVariant = (role) => {
    return ROLE_VARIANTS[role] || 'secondary';
  };

  getRoleDisplayName = (role) => {
    return ROLE_DISPLAY_NAMES[role] || role.replace('_', ' ');
  };


  render() {
    const {user, currentUser} = this.props;
    const {isUserModalOpen, isConfirmationModalOpen} = this.state;
    
    // Check if this is the current user to hide delete button
    const isCurrentUser = currentUser && currentUser.user_id === user.user_id;

    return (
      <tr>
        <td>
          {user.email}
        </td>
        <td>
          {user.name || 'N/A'}
        </td>
        <td>
          <Badge bg={this.getRoleVariant(user.role)}>
            {this.getRoleDisplayName(user.role)}
          </Badge>
        </td>
        <td>
          {formatDateTime(user.created_at, true)}
        </td>
        <td>
          {user.last_login_at ? formatDateTime(user.last_login_at, true) : 'Never'}
        </td>
        <td>
          <UserModal
              isModalOpen={isUserModalOpen}
              onSubmit={this.handleUserEdit}
              onClose={this.toggleUserModal}
              user={user}/>
          <ConfirmationModal
              message={`This will delete user \"${user.email}\" and the action can\'t be undone.`}
              isModalOpen={isConfirmationModalOpen}
              onConfirm={this.handleUserDelete}
              closeModal={this.toggleConfirmationModal}
          />
          <ButtonToolbar style={{gap: '10px'}}>
            <PermissionGuard permission="manage_users">
              <ButtonGroup>
                <Button
                  variant='primary'
                  size='sm'
                  onClick={this.toggleUserModal}
                >
                  Edit Role
                </Button>
              </ButtonGroup>
            </PermissionGuard>
            
            {!isCurrentUser && (
              <PermissionGuard permission="manage_users">
                <ButtonGroup>
                  <Button
                    onClick={this.toggleConfirmationModal}
                    variant='danger'
                    size='sm'
                    title='Delete the user'
                  >Delete User</Button>
                </ButtonGroup>
              </PermissionGuard>
            )}
          </ButtonToolbar>
        </td>
      </tr>
    );
  }
}
