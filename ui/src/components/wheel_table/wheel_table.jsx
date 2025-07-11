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
import {Well, Table, PageHeader, Button} from 'react-bootstrap';
import {WheelType} from '../../types';
// import '../../static_content/favicon.ico'; // Favicon handled by HTML template
import {apiURL} from '../../util';

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
    this.props.dispatchDeleteWheelDelete(wheel.id);
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
    const wheels = JSON.parse(JSON.stringify(this.existing.Items)).sort((a, b) => a.name.localeCompare(b.name));
    let wheelRows = wheels.map(
      item => <WheelRow key={item.id} wheel={item} onEdit={this.handleWheelEdit} onDelete={this.handleWheelDelete}/>);

    return (
      <div className='pageRoot'>
        <div className='container-fluid'>
          <Well>
            <PageHeader>
              <div className='tableHeader'>
                List of available Wheels
                <Button
                  bsStyle='primary'
                  bsSize='small'
                  onClick={this.toggleWheelModal}
                  className='pull-right'>
                  Add New Wheel
                </Button>
              </div>
            </PageHeader>
            <Table striped condensed hover>
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
          </Well>
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
    request: {
      url: apiURL('wheel'),
    }
  },
  {
    resource: 'createWheel',
    method: 'post',
    request: (wheel) => ({
      url: apiURL('wheel'),
      body: JSON.stringify(wheel)
    })
  },
  {
    resource: 'updateWheel',
    method: 'put',
    request: (wheel) => ({
      url: apiURL(`wheel/${wheel.id}`),
      body: JSON.stringify(wheel)
    })
  },
  {
    resource: 'deleteWheel',
    method: 'delete',
    request: (wheelId) => ({
      url: apiURL(`wheel/${wheelId}`),
      meta: {
        removeFromList: {
          idName: 'id',
          id: wheelId,
        }
      }
    })
  }
])(WheelTable);
