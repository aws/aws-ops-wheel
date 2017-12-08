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
import {LinkWrapper} from '../../util';
import WheelModal from './wheel_modal';
import ConfirmationModal from '../confirmation_modal';
import {Button, ButtonGroup, ButtonToolbar} from 'react-bootstrap';
import {formatDateTime} from '../../util';
import {WheelType} from '../../types';

export interface WheelRowState {
  isWheelModalOpen: PropTypes.boolean;
  isConfirmationModalOpen: PropTypes.boolean;
}

export interface WheelRowProps {
  wheel: WheelType;
  onEdit: PropTypes.func;
  onDelete: PropTypes.func;
}

export default class WheelRow extends Component<WheelRowProps, WheelRowState> {
  constructor(props: WheelRowProps) {
    super(props);
    this.state = {
      isWheelModalOpen: false,
      isConfirmationModalOpen: false,
    };
  }

  toggleWheelModal = () => {
    this.setState({isWheelModalOpen: !this.state.isWheelModalOpen});
  }

  toggleConfirmationModal = () => {
      this.setState({isConfirmationModalOpen: !this.state.isConfirmationModalOpen});
  }

  handleWheelEdit = (wheel: WheelType) => {
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
          <LinkWrapper to={`wheel/${wheel.id}`}>{wheel.name} </LinkWrapper>
        </td>
        <td>
          {wheel.participant_count}
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
              message={`This will delete \"${wheel.name}\" and the action can\'t be undone.`}
              isModalOpen={isConfirmationModalOpen}
              onConfirm={this.handleWheelDelete}
              closeModal={this.toggleConfirmationModal}
          />
          <ButtonToolbar>
            <ButtonGroup>
              <Button
                bsStyle='primary'
                bsSize='small'
                onClick={this.toggleWheelModal}
              >
                Edit Name
              </Button>
            </ButtonGroup>
            <ButtonGroup>
              <LinkWrapper to={`wheel/${wheel.id}/participant`}>
                <Button bsStyle='primary' bsSize='small'>
                  Edit Participants
                </Button>
              </LinkWrapper>
            </ButtonGroup>
            <ButtonGroup>
              <Button
                onClick={this.toggleConfirmationModal}
                bsStyle='danger'
                bsSize='small'
                title='Delete the wheel'
              >Delete Wheel</Button>
            </ButtonGroup>
          </ButtonToolbar>
        </td>
      </tr>
    );
  }
}