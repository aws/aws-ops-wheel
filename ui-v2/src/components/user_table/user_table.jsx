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
import connect from 'react-redux-fetch';
import UserRow from './user_row';
import UserModal from './user_modal';
import {Card, Table, Button} from 'react-bootstrap';
import {apiURL, getAuthHeaders} from '../../util';
import PermissionGuard from '../PermissionGuard';

// Constants
const INITIAL_STATE = {
  isUserModalOpen: false,
  create: false,
  edit: false,
  delete: false,
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
  }

  toggleUserModal = () => {
    this.setState({isUserModalOpen: !this.state.isUserModalOpen});
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
    return users.map(user => (
      <UserRow 
        key={user.user_id} 
        user={user} 
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

    const { isUserModalOpen } = this.state;
    const users = this.getSortedUsers(this.cachedUsersData);
    const userRows = this.renderUserRows(users);

    return (
      <div className='pageRoot'>
        <div className='container-fluid' style={{marginTop: '1rem'}}>
          <Card>
            <Card.Header>
              <div className='tableHeader'>
                User Management
                <PermissionGuard permission="manage_users">
                  <Button
                    variant='primary'
                    size='sm'
                    onClick={this.toggleUserModal}
                    className='float-end'>
                    Add New User
                  </Button>
                </PermissionGuard>
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
      </div>
    );
  }
}

export default connect([
  {
    resource: 'users',
    method: 'get',
    request: () => ({
      url: apiURL('tenant/users'),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'createUser',
    method: 'post',
    request: (user) => ({
      url: apiURL('tenant/users'),
      headers: getAuthHeaders(),
      body: JSON.stringify(user)
    })
  },
  {
    resource: 'updateUser',
    method: 'put',
    request: (user) => ({
      url: apiURL(`tenant/users/${user.user_id}/role`),
      headers: getAuthHeaders(),
      body: JSON.stringify({role: user.role})
    })
  },
  {
    resource: 'deleteUser',
    method: 'delete',
    request: (userId) => ({
      url: apiURL(`tenant/users/${userId}`),
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
