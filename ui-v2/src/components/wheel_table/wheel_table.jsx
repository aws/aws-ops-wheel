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
import WheelRow from './wheel_row';
import WheelModal from './wheel_modal';
import {Card, Table, Button} from 'react-bootstrap';
import {WheelType} from '../../types';
// import '../../static_content/favicon.ico'; // Favicon handled by HTML template
import {apiURL, authenticatedFetch, getAuthHeaders} from '../../util';

interface WheelTableState {
  isWheelModalOpen: bool;
}

interface WheelTableProps {
  wheelsFetch: PropTypes.object;
  createWheelFetch: PropTypes.object;
  updateWheelFetch: PropTypes.object;
  deleteWheelFetch: PropTypes.object;
  dispatchWheelsGet: PropTypes.func;
  dispatchCreateWheelPost: PropTypes.func;
  dispatchUpdateWheelPut: PropTypes.func;
  dispatchDeleteWheelDelete: PropTypes.func;
}

export class WheelTable extends Component<WheelTableProps, WheelTableState> {

  existing: WheelType;

  constructor(props: WheelTableProps) {
    super(props);
    this.state = {
      isWheelModalOpen: false,
      create: false,
      edit: false,
      delete: false,
    };
    this.existing = undefined;
  }

  componentWillMount() {
    this.props.dispatchWheelsGet();
  }

  toggleWheelModal = () => {
    this.setState({isWheelModalOpen: !this.state.isWheelModalOpen});
  };

  handleWheelAdd = (wheel: WheelType) => {
    this.props.dispatchCreateWheelPost(wheel);
    this.setState({create: true});
  };

  handleWheelEdit = (wheel: WheelType) => {
    this.props.dispatchUpdateWheelPut(wheel);
    this.setState({edit: true});
  };

  handleWheelDelete = (wheel: WheelType) => {
    // V2 API uses wheel_id instead of id
    this.props.dispatchDeleteWheelDelete(wheel.wheel_id);
    this.setState({delete: true});
  };

  componentDidUpdate() {
    let updates = {};
    if (this.state.create && this.props.createWheelFetch.fulfilled) {
      updates.create = false;
    }
    if (this.state.edit && this.props.updateWheelFetch.fulfilled) {
      updates.edit = false;
    }
    if (this.state.delete && this.props.deleteWheelFetch.fulfilled) {
      updates.delete = false;
    }
    if (Object.keys(updates).length > 0) {
      this.setState(updates);
      this.props.dispatchWheelsGet();
    }
  }

  render() {
    const {wheelsFetch} = this.props;
    if (wheelsFetch.rejected) {
      return (<div>Oops... Could not fetch the wheels data!</div>);
    }
    if (wheelsFetch.fulfilled) {
      this.existing = wheelsFetch.value;
    }
    if (this.existing === undefined) {
      return (<div style={{padding: '15px'}}>Loading...</div>);
    }

    const {isWheelModalOpen} = this.state;
    // V2 API returns {wheels: [...], count: ...} instead of {Items: [...], Count: ...}
    const wheels = JSON.parse(JSON.stringify(this.existing.wheels || [])).sort((a, b) => a.wheel_name.localeCompare(b.wheel_name));
    let wheelRows = wheels.map(
      item => <WheelRow key={item.wheel_id} wheel={item} onEdit={this.handleWheelEdit} onDelete={this.handleWheelDelete}/>);

    return (
      <div className='pageRoot'>
        <div className='container-fluid' style={{marginTop: '1rem'}}>
          <Card>
            <Card.Header>
              <div className='tableHeader'>
                List of available Wheels
                <Button
                  variant='primary'
                  size='sm'
                  onClick={this.toggleWheelModal}
                  className='float-end'>
                  Add New Wheel
                </Button>
              </div>
            </Card.Header>
            <Table striped hover>
              <thead>
                <tr>
                  <th>Wheel Name</th>
                  <th>Number of Participants</th>
                  <th>Last Updated</th>
                  <th>Created At</th>
                  <th>Operations</th>
                </tr>
              </thead>
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
