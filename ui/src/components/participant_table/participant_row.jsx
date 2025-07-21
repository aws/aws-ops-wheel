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

interface ParticipantRowProps {
  participant: ParticipantType;
  totalParticipantWeight: number;
  rig: boolean;
  hidden: boolean;
  onEdit: Function;
  onDelete: Function;
  onRig: Function;
  onHidden: Function;
  participantList: ParticipantType[];
}

export default class ParticipantRow extends Component<ParticipantRowProps> {

  constructor(props) {
    super(props);
    this.state = {
      participationModalOpen: false,
      confirmationModalOpen: false,
    };
  }

  toggleParticipationModal = () => {
    this.setState({participationModalOpen: !this.state.participationModalOpen});
  }

  toggleConfirmationModal = () => {
    this.setState({confirmationModalOpen: !this.state.confirmationModalOpen});
  }

  handleUpdateParticipant = (participant: ParticipantType) => {
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

  render(){
    const {participant, totalParticipantWeight} = this.props;
    const {participationModalOpen, confirmationModalOpen} = this.state;

    return (
      <tr key={participant.id}>
        <td>
          {participant.name}
        </td>
        <td>
          <LinkWrapper to={participant.url} remote={true} target='_blank'>{participant.url}</LinkWrapper>
        </td>
        <td>
          {(participant.weight / totalParticipantWeight * 100).toFixed(2)}%
        </td>
        <td>
          <ParticipantModal isOpen={participationModalOpen}
                                 onSubmit={this.handleUpdateParticipant}
                                 onClose={this.toggleParticipationModal}
                                 participant={participant}
                                 participantList={this.props.participantList}/>
          <ConfirmationModal isModalOpen={confirmationModalOpen}
                             message={`This will delete \"${participant.name}\" and the action can\'t be undone.`}
                             onConfirm={this.handleDeleteParticipant}
                             closeModal={this.toggleConfirmationModal} />
          <ButtonToolbar>
            <ButtonGroup>
              <Button variant='primary'
                      size='sm'
                      onClick={this.toggleParticipationModal}>
                Edit
              </Button>
            </ButtonGroup>
            <ButtonGroup>
              <Button variant='danger'
                      size='sm'
                      onClick={this.toggleConfirmationModal}>
                Delete
              </Button>
            </ButtonGroup>
          </ButtonToolbar>
        </td>
        <td key='public-rig'>
          <input type='radio'
                 checked={this.props.rig}
                 onChange={this.handleRigParticipant} />
        </td>
        <td key='hidden-unrig'>
          <input type='checkbox'
                 checked={this.props.hidden}
                 onChange={this.handleHiddenRigParticipant} />
        </td>
      </tr>
    );
  }
}
