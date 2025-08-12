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
import {Button, ButtonGroup, ButtonToolbar} from 'react-bootstrap';
import ParticipantModal from './participant_modal';
import ConfirmationModal from '../confirmation_modal';
import {ParticipantType} from '../../types';
import {LinkWrapper} from '../../util';

// Constants
const INITIAL_STATE = {
  participationModalOpen: false,
  confirmationModalOpen: false,
};

const BUTTON_LABELS = {
  EDIT: 'Edit',
  DELETE: 'Delete'
};

const INPUT_LABELS = {
  PUBLIC_RIG: 'public-rig',
  HIDDEN_UNRIG: 'hidden-unrig'
};

export default class ParticipantRow extends Component {

  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
  }

  toggleParticipationModal = () => {
    this.setState({participationModalOpen: !this.state.participationModalOpen});
  }

  toggleConfirmationModal = () => {
    this.setState({confirmationModalOpen: !this.state.confirmationModalOpen});
  }

  handleUpdateParticipant = (participant) => {
    this.props.onEdit(participant);
  }

  handleDeleteParticipant = () => {
    this.props.onDelete(this.props.participant);
  }

  handleRigParticipant = () => {
    this.props.onRig(this.props.participant);
  }
  
  handleHiddenRigParticipant = () => {
    this.props.onHidden(this.props.participant);
  }

  calculateSelectionPercentage = () => {
    const { participant, totalParticipantWeight } = this.props;
    return (participant.weight / totalParticipantWeight * 100).toFixed(2);
  }

  render(){
    const {participant, totalParticipantWeight} = this.props;
    const {participationModalOpen, confirmationModalOpen} = this.state;

    return (
      <tr key={participant.id}>
        <td>
          {participant.participant_name}
        </td>
        <td>
          <LinkWrapper to={participant.participant_url} remote={true} target='_blank'>{participant.participant_url}</LinkWrapper>
        </td>
        <td>
          {this.calculateSelectionPercentage()}%
        </td>
        <td>
          <ParticipantModal isOpen={participationModalOpen}
                                 onSubmit={this.handleUpdateParticipant}
                                 onClose={this.toggleParticipationModal}
                                 participant={participant}
                                 participantList={this.props.participantList}/>
          <ConfirmationModal isModalOpen={confirmationModalOpen}
                             message={`This will delete \"${participant.participant_name}\" and the action can\'t be undone.`}
                             onConfirm={this.handleDeleteParticipant}
                             closeModal={this.toggleConfirmationModal} />
          <ButtonToolbar>
            <ButtonGroup>
              <Button variant='primary'
                      size='sm'
                      onClick={this.toggleParticipationModal}>
                {BUTTON_LABELS.EDIT}
              </Button>
            </ButtonGroup>
            <ButtonGroup>
              <Button variant='danger'
                      size='sm'
                      onClick={this.toggleConfirmationModal}>
                {BUTTON_LABELS.DELETE}
              </Button>
            </ButtonGroup>
          </ButtonToolbar>
        </td>
        <td key={INPUT_LABELS.PUBLIC_RIG}>
          <input type='radio'
                 checked={this.props.rig}
                 onChange={this.handleRigParticipant} />
        </td>
        <td key={INPUT_LABELS.HIDDEN_UNRIG}>
          <input type='checkbox'
                 checked={this.props.hidden}
                 onChange={this.handleHiddenRigParticipant} />
        </td>
      </tr>
    );
  }
}
