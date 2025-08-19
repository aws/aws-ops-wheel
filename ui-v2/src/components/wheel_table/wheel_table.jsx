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
import connect from 'react-redux-fetch';
import WheelRow from './wheel_row';
import WheelModal from './wheel_modal';
import {Card, Table, Button} from 'react-bootstrap';
// import '../../static_content/favicon.ico'; // Favicon handled by HTML template
import {apiURL, getAuthHeaders} from '../../util';
import PermissionGuard from '../PermissionGuard';

// Constants
const INITIAL_STATE = {
  isWheelModalOpen: false,
  create: false,
  edit: false,
  delete: false,
};

const TABLE_HEADERS = [
  'Wheel Name',
  'Number of Participants', 
  'Last Updated',
  'Created At',
  'Operations'
];

export class WheelTable extends Component {
  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
    this.cachedWheelsData = null;
  }

  componentWillMount() {
    this.props.dispatchWheelsGet();
  }

  toggleWheelModal = () => {
    this.setState({isWheelModalOpen: !this.state.isWheelModalOpen});
  };

  handleWheelAdd = (wheel) => {
    this.props.dispatchCreateWheelPost(wheel);
    this.setState({create: true});
  };

  handleWheelEdit = (wheel) => {
    this.props.dispatchUpdateWheelPut(wheel);
    this.setState({edit: true});
  };

  handleWheelDelete = (wheel) => {
    // V2 API uses wheel_id instead of id
    this.props.dispatchDeleteWheelDelete(wheel.wheel_id);
    this.setState({delete: true});
  };

  componentDidUpdate() {
    const updates = this.getStateUpdatesAfterOperations();
    if (Object.keys(updates).length > 0) {
      this.setState(updates);
      this.props.dispatchWheelsGet();
    }
  }

  getStateUpdatesAfterOperations = () => {
    const updates = {};
    const { createWheelFetch, updateWheelFetch, deleteWheelFetch } = this.props;
    
    if (this.state.create && createWheelFetch.fulfilled) {
      updates.create = false;
    }
    if (this.state.edit && updateWheelFetch.fulfilled) {
      updates.edit = false;
    }
    if (this.state.delete && deleteWheelFetch.fulfilled) {
      updates.delete = false;
    }
    
    return updates;
  };

  getSortedWheels = (wheelsData) => {
    const wheels = wheelsData?.wheels || [];
    // Deep clone to avoid mutation and sort by wheel name
    return JSON.parse(JSON.stringify(wheels)).sort((a, b) => 
      a.wheel_name.localeCompare(b.wheel_name)
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

  renderWheelRows = (wheels) => {
    return wheels.map(wheel => (
      <WheelRow 
        key={wheel.wheel_id} 
        wheel={wheel} 
        onEdit={this.handleWheelEdit} 
        onDelete={this.handleWheelDelete}
      />
    ));
  };

  render() {
    const { wheelsFetch } = this.props;
    
    if (wheelsFetch.rejected) {
      return <div>Oops... Could not fetch the wheels data!</div>;
    }
    
    if (wheelsFetch.fulfilled) {
      this.cachedWheelsData = wheelsFetch.value;
    }
    
    if (!this.cachedWheelsData) {
      return <div style={{padding: '15px'}}>Loading...</div>;
    }

    const { isWheelModalOpen } = this.state;
    const wheels = this.getSortedWheels(this.cachedWheelsData);
    const wheelRows = this.renderWheelRows(wheels);

    return (
      <div className='pageRoot'>
        <div className='container-fluid' style={{marginTop: '1rem'}}>
          <Card>
            <Card.Header>
              <div className='tableHeader'>
                List of available Wheels
                <PermissionGuard permission="create_wheel">
                  <Button
                    variant='primary'
                    size='sm'
                    onClick={this.toggleWheelModal}
                    className='float-end'>
                    Add New Wheel
                  </Button>
                </PermissionGuard>
              </div>
            </Card.Header>
            <Table striped hover>
              {this.renderTableHeaders()}
              <tbody>
                {wheelRows}
              </tbody>
            </Table>
          </Card>
        </div>
        <WheelModal
          isModalOpen={isWheelModalOpen}
          onSubmit={this.handleWheelAdd}
          onClose={this.toggleWheelModal}
          wheel={undefined}/>
      </div>
    );
  }
}

export default connect([
  {
    resource: 'wheels',
    method: 'get',
    request: () => ({
      url: apiURL('wheels'),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'createWheel',
    method: 'post',
    request: (wheel) => ({
      url: apiURL('wheels'),
      headers: getAuthHeaders(),
      body: JSON.stringify(wheel)
    })
  },
  {
    resource: 'updateWheel',
    method: 'put',
    request: (wheel) => ({
      url: apiURL(`wheels/${wheel.wheel_id}`),
      headers: getAuthHeaders(),
      body: JSON.stringify(wheel)
    })
  },
  {
    resource: 'deleteWheel',
    method: 'delete',
    request: (wheelId) => ({
      url: apiURL(`wheels/${wheelId}`),
      headers: getAuthHeaders(),
      meta: {
        removeFromList: {
          idName: 'wheel_id',
          id: wheelId,
        }
      }
    })
  }
])(WheelTable);
