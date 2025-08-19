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
import PropTypes from 'prop-types';
import connect from 'react-redux-fetch';
import UserRow from './user_row';
import UserModal from './user_modal';
import DeleteWheelGroupModal from './delete_wheel_group_modal';
import {Card, Table, Button} from 'react-bootstrap';
import {apiURL, getAuthHeaders} from '../../util';
import PermissionGuard, { usePermissions } from '../PermissionGuard';

// Constants
const INITIAL_STATE = {
  isUserModalOpen: false,
  isDeleteWheelGroupModalOpen: false,
  create: false,
  edit: false,
  delete: false,
  deleteWheelGroup: false,
  isDeletingWheelGroup: false,
  wheelGroupName: null,
  currentUser: null
};

const TABLE_HEADERS = [
  'Email',
  'Username', 
  'Role',
  'Created At',
  'Last Login',
  'Operations'
];

export class UserTable extends Component {
  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
    this.cachedUsersData = null;
  }

  componentWillMount() {
    this.props.dispatchUsersGet();
    // Get wheel group info for delete modal
    this.fetchWheelGroupInfo();
    // Get current user info
    this.fetchCurrentUser();
  }

  fetchWheelGroupInfo = async () => {
    try {
      const response = await fetch(apiURL('wheel-group'), {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const wheelGroup = await response.json();
        this.setState({ wheelGroupName: wheelGroup.wheel_group_name });
      }
    } catch (error) {
      console.error('Failed to fetch wheel group info:', error);
    }
  };

  fetchCurrentUser = async () => {
    try {
      const response = await fetch(apiURL('auth/me'), {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const user = await response.json();
        this.setState({ currentUser: user });
      }
    } catch (error) {
      console.error('Failed to fetch current user info:', error);
    }
  };

  toggleUserModal = () => {
    this.setState({isUserModalOpen: !this.state.isUserModalOpen});
  };

  toggleDeleteWheelGroupModal = () => {
    this.setState({isDeleteWheelGroupModalOpen: !this.state.isDeleteWheelGroupModalOpen});
  };

  handleDeleteTenant = async () => {
    this.setState({ isDeletingTenant: true });
    
    try {
      // Make the delete request
      const response = await fetch(apiURL('wheel-group/delete-recursive'), {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const responseData = response.ok ? await response.json() : await response.json().catch(() => ({}));
      
      if (response.ok) {
        console.log('Wheel group deleted successfully:', responseData);
      } else {
        console.error('Failed to delete wheel group:', responseData);
      }

      // Regardless of success or failure, immediately log out the user
      // This prevents the redirect loop by clearing all authentication tokens
      // and ensuring the user is properly signed out from Cognito
      this.performCompleteLogout();
      
    } catch (error) {
      console.error('Error during wheel group deletion:', error);
      // Even on error, log out the user to prevent authentication issues
      this.performCompleteLogout();
    }
  };

  performCompleteLogout = () => {
    try {
      // Clear all possible authentication tokens
      localStorage.removeItem('userToken');
      localStorage.removeItem('idToken');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      
      // Clear any Cognito-related items that might exist
      Object.keys(localStorage).forEach(key => {
        if (key.includes('CognitoIdentityServiceProvider') || 
            key.includes('amplify') || 
            key.includes('aws') ||
            key.includes('cognito')) {
          localStorage.removeItem(key);
        }
      });

      // Clear session storage as well
      sessionStorage.clear();
      
      // Force a hard redirect to login to ensure clean state
      window.location.replace('/app/login');
      
    } catch (error) {
      console.error('Error during logout:', error);
      // As a last resort, force reload to clear everything
      window.location.reload();
    }
  };

  handleUserAdd = (user) => {
    this.props.dispatchCreateUserPost(user);
    this.setState({create: true});
  };

  handleUserEdit = (user) => {
    this.props.dispatchUpdateUserPut(user);
    this.setState({edit: true});
  };

  handleUserDelete = (user) => {
    this.props.dispatchDeleteUserDelete(user.user_id);
    this.setState({delete: true});
  };

  componentDidUpdate() {
    const updates = this.getStateUpdatesAfterOperations();
    if (Object.keys(updates).length > 0) {
      this.setState(updates);
      this.props.dispatchUsersGet();
    }
  }

  getStateUpdatesAfterOperations = () => {
    const updates = {};
    const { createUserFetch, updateUserFetch, deleteUserFetch } = this.props;
    
    if (this.state.create && createUserFetch.fulfilled) {
      updates.create = false;
    }
    if (this.state.edit && updateUserFetch.fulfilled) {
      updates.edit = false;
    }
    if (this.state.delete && deleteUserFetch.fulfilled) {
      updates.delete = false;
    }
    
    return updates;
  };

  getSortedUsers = (usersData) => {
    const users = usersData?.users || [];
    // Deep clone to avoid mutation and sort by email
    return JSON.parse(JSON.stringify(users)).sort((a, b) => 
      a.email.localeCompare(b.email)
    );
  };

  renderTableHeaders = () => {
    return (
      <thead>
        <tr>
          {TABLE_HEADERS.map(header => (
            <th key={header}>{header}</th>
          ))}
        </tr>
      </thead>
    );
  };

  renderUserRows = (users) => {
    const { currentUser } = this.state;
    return users.map(user => (
      <UserRow 
        key={user.user_id} 
        user={user} 
        currentUser={currentUser}
        onEdit={this.handleUserEdit} 
        onDelete={this.handleUserDelete}
      />
    ));
  };

  render() {
    const { usersFetch } = this.props;
    
    if (usersFetch.rejected) {
      return <div>Oops... Could not fetch the users data!</div>;
    }
    
    if (usersFetch.fulfilled) {
      this.cachedUsersData = usersFetch.value;
    }
    
    if (!this.cachedUsersData) {
      return <div style={{padding: '15px'}}>Loading...</div>;
    }

    const { isUserModalOpen, isDeleteWheelGroupModalOpen, isDeletingWheelGroup, wheelGroupName } = this.state;
    const users = this.getSortedUsers(this.cachedUsersData);
    const userRows = this.renderUserRows(users);

    return (
      <div className='pageRoot'>
        <div className='container-fluid' style={{marginTop: '1rem'}}>
          <Card>
            <Card.Header>
              <div className='tableHeader'>
                User Management
                <div className="float-end">
                  <PermissionGuard permission="manage_wheel_group">
                    <Button
                      variant='danger'
                      size='sm'
                      onClick={this.toggleDeleteWheelGroupModal}
                      className='me-2'
                      disabled={isDeletingWheelGroup}>
                      Delete Wheel Group
                    </Button>
                  </PermissionGuard>
                  <PermissionGuard permission="manage_users">
                    <Button
                      variant='primary'
                      size='sm'
                      onClick={this.toggleUserModal}>
                      Add New User
                    </Button>
                  </PermissionGuard>
                </div>
              </div>
            </Card.Header>
            <Table striped hover>
              {this.renderTableHeaders()}
              <tbody>
                {userRows}
              </tbody>
            </Table>
          </Card>
        </div>
        <UserModal
          isModalOpen={isUserModalOpen}
          onSubmit={this.handleUserAdd}
          onClose={this.toggleUserModal}
          user={undefined}/>
        <DeleteWheelGroupModal
          isModalOpen={isDeleteWheelGroupModalOpen}
          onConfirm={this.handleDeleteTenant}
          onClose={this.toggleDeleteWheelGroupModal}
          wheelGroupName={wheelGroupName}
          isDeleting={isDeletingWheelGroup}/>
      </div>
    );
  }
}

export default connect([
  {
    resource: 'users',
    method: 'get',
    request: () => ({
      url: apiURL('wheel-group/users'),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'createUser',
    method: 'post',
    request: (user) => ({
      url: apiURL('wheel-group/users'),
      headers: getAuthHeaders(),
      body: JSON.stringify(user)
    })
  },
  {
    resource: 'updateUser',
    method: 'put',
    request: (user) => ({
      url: apiURL(`wheel-group/users/${user.user_id}/role`),
      headers: getAuthHeaders(),
      body: JSON.stringify({role: user.role})
    })
  },
  {
    resource: 'deleteUser',
    method: 'delete',
    request: (userId) => ({
      url: apiURL(`wheel-group/users/${userId}`),
      headers: getAuthHeaders(),
      meta: {
        removeFromList: {
          idName: 'user_id',
          id: userId,
        }
      }
    })
  }
])(UserTable);
