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

import React, { Component } from 'react';
import { Card, Table, Button, Alert } from 'react-bootstrap';
import connect from 'react-redux-fetch';
import DeleteWheelGroupModal from '../user_table/delete_wheel_group_modal';
import { apiURL, getAuthHeaders, formatDateTime } from '../../util';

// Constants
const INITIAL_STATE = {
  wheelGroups: [],
  loading: true,
  error: null,
  deleteModalOpen: false,
  wheelGroupToDelete: null,
  deletePending: false
};

const TABLE_HEADERS = [
  'Wheel Group Name',
  'Number of Users',
  'Number of Wheels',
  'Last Updated',
  'Created At',
  'Operations'
];

const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    return 'Invalid Date';
  }
};

export class WheelGroupsTable extends Component {
  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
  }

  componentDidMount() {
    this.fetchWheelGroups();
  }

  componentDidUpdate() {
    // Handle successful delete
    if (this.state.deletePending && this.props.deleteWheelGroupFetch.fulfilled) {
      this.setState({
        deletePending: false,
        deleteModalOpen: false,
        wheelGroupToDelete: null
      });
      this.fetchWheelGroups(); // Refresh the list
    }

    // Handle fetch completion
    if (this.state.loading && this.props.wheelGroupsFetch.fulfilled) {
      const response = this.props.wheelGroupsFetch.value;
      console.log('🔍 Wheel groups API response:', response);
      this.setState({
        wheelGroups: response.wheel_groups || [],
        loading: false,
        error: null
      });
    }

    // Handle fetch errors
    if (this.state.loading && this.props.wheelGroupsFetch.rejected) {
      const error = this.props.wheelGroupsFetch.reason;
      console.error('❌ Wheel groups API error:', error);
      
      let errorMessage = 'Failed to load wheel groups. Please try again.';
      
      // Provide more specific error messages
      if (error && error.status === 403) {
        errorMessage = 'Access denied. You need deployment admin privileges to view all wheel groups.';
      } else if (error && error.status === 401) {
        errorMessage = 'Authentication failed. Please log in again.';
      } else if (error && error.message) {
        errorMessage = `Failed to load wheel groups: ${error.message}`;
      }
      
      this.setState({
        wheelGroups: [],
        loading: false,
        error: errorMessage
      });
    }
  }

  fetchWheelGroups = () => {
    this.setState({ loading: true });
    this.props.dispatchWheelGroupsGet();
  };

  handleDeleteClick = (wheelGroup) => {
    this.setState({
      deleteModalOpen: true,
      wheelGroupToDelete: wheelGroup
    });
  };

  handleDeleteConfirm = () => {
    if (this.state.wheelGroupToDelete) {
      this.setState({ deletePending: true });
      this.props.dispatchDeleteWheelGroupDelete(this.state.wheelGroupToDelete.wheel_group_id);
    }
  };

  handleDeleteCancel = () => {
    if (!this.state.deletePending) {
      this.setState({
        deleteModalOpen: false,
        wheelGroupToDelete: null
      });
    }
  };

  renderTableContent = () => {
    const { wheelGroups, loading, error } = this.state;

    if (loading) {
      return (
        <tr>
          <td colSpan={6} className="text-center p-4">
            <div className="d-flex align-items-center justify-content-center">
              <div className="spinner-border spinner-border-sm me-2" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              Loading wheel groups...
            </div>
          </td>
        </tr>
      );
    }

    if (error) {
      return (
        <tr>
          <td colSpan={6} className="text-center p-4">
            <Alert variant="danger" className="mb-0">
              {error}
              <div className="mt-2">
                <Button variant="outline-danger" size="sm" onClick={this.fetchWheelGroups}>
                  Retry
                </Button>
              </div>
            </Alert>
          </td>
        </tr>
      );
    }

    if (wheelGroups.length === 0) {
      return (
        <tr>
          <td colSpan={6} className="text-center p-4">
            <div className="text-muted">
              <div className="mb-2">📂</div>
              <div>No wheel groups found</div>
              <small>Wheel groups will appear here once they are created.</small>
            </div>
          </td>
        </tr>
      );
    }

    return wheelGroups.map((wheelGroup) => (
      <tr key={wheelGroup.wheel_group_id}>
        <td className="fw-semibold">{wheelGroup.wheel_group_name}</td>
        <td>{wheelGroup.user_count || 0}</td>
        <td>{wheelGroup.wheel_count || 0}</td>
        <td>
          {formatDateTime(wheelGroup.last_updated, true)}
        </td>
        <td>
          {formatDateTime(wheelGroup.created_at, true)}
        </td>
        <td>
          <Button
            variant="danger"
            size="sm"
            onClick={() => this.handleDeleteClick(wheelGroup)}
            disabled={this.state.deletePending}
          >
            Delete
          </Button>
        </td>
      </tr>
    ));
  };

  render() {
    const { deleteModalOpen, wheelGroupToDelete, deletePending } = this.state;

    return (
      <div className="pageRoot">
        <DeleteWheelGroupModal
          isModalOpen={deleteModalOpen}
          onConfirm={this.handleDeleteConfirm}
          onClose={this.handleDeleteCancel}
          wheelGroupName={wheelGroupToDelete?.wheel_group_name}
          isDeleting={deletePending}
        />

        <h1 className="title">
          <div className="title-text">Deployment Administration</div>
        </h1>

        <div className="container-fluid">
          <Card>
            <Card.Header>
              <div className="d-flex justify-content-between align-items-center">
                <div className="tableHeader">
                  Wheel Groups
                  <small className="text-muted ms-2">
                    Manage all wheel groups in the system
                  </small>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={this.fetchWheelGroups}
                  disabled={this.state.loading}
                >
                  {this.state.loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-1" />
                      Refreshing...
                    </>
                  ) : (
                    'Refresh'
                  )}
                </Button>
              </div>
            </Card.Header>

            <Table striped hover responsive>
              <thead>
                <tr>
                  {TABLE_HEADERS.map((header, index) => (
                    <th key={index}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {this.renderTableContent()}
              </tbody>
            </Table>
          </Card>
        </div>
      </div>
    );
  }
}

export default connect([
  {
    resource: 'wheelGroups',
    method: 'get',
    request: () => ({
      url: apiURL('admin/wheel-groups'),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'deleteWheelGroup',
    method: 'delete',
    request: (wheelGroupId) => ({
      url: apiURL(`admin/wheel-groups/${wheelGroupId}`),
      headers: getAuthHeaders()
    })
  }
])(WheelGroupsTable);
