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
import {LinkWrapper} from '../../util';
import WheelModal from './wheel_modal';
import ConfirmationModal from '../confirmation_modal';
import {Button, ButtonGroup, ButtonToolbar} from 'react-bootstrap';
import {formatDateTime} from '../../util';
import {WheelType} from '../../types';
import PermissionGuard from '../PermissionGuard';

// Constants
const INITIAL_STATE = {
  isWheelModalOpen: false,
  isConfirmationModalOpen: false,
};

const BUTTON_LABELS = {
  EDIT_NAME: 'Edit Name',
  EDIT_PARTICIPANTS: 'Edit Participants',
  DELETE_WHEEL: 'Delete Wheel'
};

const PERMISSIONS = {
  CREATE_WHEEL: 'create_wheel',
  MANAGE_PARTICIPANTS: 'manage_participants',
  DELETE_WHEEL: 'delete_wheel'
};

export default class WheelRow extends Component {
  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
  }

  toggleWheelModal = () => {
    this.setState({isWheelModalOpen: !this.state.isWheelModalOpen});
  }

  toggleConfirmationModal = () => {
      this.setState({isConfirmationModalOpen: !this.state.isConfirmationModalOpen});
  }

  handleWheelEdit = (wheel) => {
    this.props.onEdit(wheel);
  };

  handleWheelDelete = () => {
    this.props.onDelete(this.props.wheel);
  };

  render() {
    const {wheel} = this.props;
    const {isWheelModalOpen, isConfirmationModalOpen} = this.state;

    return (
      <tr>
        <td>
          <LinkWrapper to={`wheel/${wheel.wheel_id}`}>{wheel.wheel_name} </LinkWrapper>
        </td>
        <td>
          {wheel.participant_count || 0}
        </td>
        <td>
          {formatDateTime(wheel.updated_at, true)}
        </td>
        <td>
          {formatDateTime(wheel.created_at, true)}
        </td>
        <td>
          <WheelModal
              isModalOpen={isWheelModalOpen}
              onSubmit={this.handleWheelEdit}
              onClose={this.toggleWheelModal}
              wheel={wheel}/>
          <ConfirmationModal
              message={`This will delete \"${wheel.wheel_name}\" and the action can\'t be undone.`}
              isModalOpen={isConfirmationModalOpen}
              onConfirm={this.handleWheelDelete}
              closeModal={this.toggleConfirmationModal}
          />
          <ButtonToolbar style={{gap: '10px'}}>
            <PermissionGuard permission={PERMISSIONS.CREATE_WHEEL}>
              <ButtonGroup>
                <Button
                  variant='primary'
                  size='sm'
                  onClick={this.toggleWheelModal}
                >
                  {BUTTON_LABELS.EDIT_NAME}
                </Button>
              </ButtonGroup>
            </PermissionGuard>
            
            <PermissionGuard permission={PERMISSIONS.MANAGE_PARTICIPANTS}>
              <ButtonGroup>
                <LinkWrapper to={`wheel/${wheel.wheel_id}/participant`}>
                  <Button variant='primary' size='sm'>
                    {BUTTON_LABELS.EDIT_PARTICIPANTS}
                  </Button>
                </LinkWrapper>
              </ButtonGroup>
            </PermissionGuard>
            
            <PermissionGuard permission={PERMISSIONS.DELETE_WHEEL}>
              <ButtonGroup>
                <Button
                  onClick={this.toggleConfirmationModal}
                  variant='danger'
                  size='sm'
                  title='Delete the wheel'
                >
                  {BUTTON_LABELS.DELETE_WHEEL}
                </Button>
              </ButtonGroup>
            </PermissionGuard>
          </ButtonToolbar>
        </td>
      </tr>
    );
  }
}
