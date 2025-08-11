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
import {Card, Table, Button, ButtonGroup, ButtonToolbar} from 'react-bootstrap';
import connect from 'react-redux-fetch';
import ParticipantRow from './participant_row';
import ParticipantModal from './participant_modal';
import ConfirmationModal from '../confirmation_modal';
import {WheelType, ParticipantType} from '../../types';
import {apiURL, getAuthHeaders} from '../../util';
import {LinkWrapper} from '../../util';
import PermissionGuard from '../PermissionGuard';

interface ParticipantTableProps {
  listParticipantsFetch: PropTypes.object;
  wheelFetch: PropTypes.object;
  createParticipantFetch: PropTypes.object;
  updateParticipantFetch: PropTypes.object;
  deleteParticipantFetch: PropTypes.object;
  rigParticipantFetch: PropTypes.object;
  unrigParticipantFetch: PropTypes.object;
  resetWheelFetch: PropTypes.object;

  dispatchListParticipantsGet: PropTypes.func;
  dispatchWheelGet: PropTypes.func;
  dispatchCreateParticipantPost: PropTypes.func;
  dispatchUpdateParticipantPut: PropTypes.func;
  dispatchDeleteParticipantDelete: PropTypes.func;
  dispatchRigParticipantPost: PropTypes.func;
  dispatchUnrigParticipantDelete: PropTypes.func;
  dispatchResetWheelPost: PropTypes.func;
}

interface Rigging {
  participant_id: string | undefined;
  hidden: boolean | undefined;
}

interface ParticipantTableState {
  wheel: WheelType | undefined;
  participants: ParticipantType[] | undefined;
  rigging: Rigging;
  resetModalOpen: boolean;
  participantModalOpen: boolean;
  createPending: boolean;
  deletePending: boolean;
  resetPending: boolean;
  fetchPending: boolean;
}

export class ParticipantTable extends Component<ParticipantTableProps, ParticipantTableState> {

  constructor(props) {
    super(props);
    this.state = {
      wheel: undefined,
      participants: undefined,
      rigging: {},
      resetModalOpen: false,
      participantModalOpen: false,
      createPending: false,
      updatePending: false,
      deletePending: false,
      resetPending: false,
      fetchPending: false,
      unrigCompleted: false,
    };
  }

  componentWillMount() {
    this.fetchWheelAndParticipants();
  }

  componentDidUpdate() {
    try {
      console.log('ParticipantTable componentDidUpdate:', {
        fetchPending: this.state.fetchPending,
        wheelFulfilled: this.props.wheelFetch.fulfilled,
        participantsFulfilled: this.props.listParticipantsFetch.fulfilled,
        wheelValue: this.props.wheelFetch.value,
        participantsValue: this.props.listParticipantsFetch.value
      });

      let updates = {};
      if (this.state.createPending && this.props.createParticipantFetch.fulfilled) {
        updates.createPending = false;
      }
      if (this.state.updatePending && this.props.updateParticipantFetch.fulfilled) {
        updates.updatePending = false;
      }
      if (this.state.deletePending && this.props.deleteParticipantFetch.fulfilled) {
        updates.deletePending = false;
      }
      if (this.state.resetPending && this.props.resetWheelFetch.fulfilled) {
        updates.resetPending = false;
      }
      if (Object.keys(updates).length > 0) {
        this.setState(updates);
        this.fetchWheelAndParticipants();
      }

      // Handle unrig completion - refresh wheel data to get updated rigging state
      if (this.props.unrigParticipantFetch.fulfilled && !this.state.fetchPending && !this.state.unrigCompleted) {
        this.setState({ unrigCompleted: true });
        this.fetchWheelAndParticipants();
      }

      if (this.state.fetchPending && this.props.wheelFetch.fulfilled && this.props.listParticipantsFetch.fulfilled) {
        const wheel = this.props.wheelFetch.value;
        // V2 API returns {participants: [...], count: ...} instead of directly the participants array
        const apiResponse = this.props.listParticipantsFetch.value;
        console.log('Processing participants API response:', apiResponse);
        const participants = JSON.parse(JSON.stringify(apiResponse.participants || apiResponse || []))
          .sort((a, b) => a.participant_name.localeCompare(b.participant_name));
        console.log('Processed participants:', participants);
        this.setState({
          fetchPending: false,
          participants,
          wheel,
          rigging: wheel.rigging || {},
        });
      }
    } catch (error) {
      console.error('Error in ParticipantTable componentDidUpdate:', error);
      // Set error state to prevent white screen
      this.setState({
        fetchPending: false,
        participants: [],
        wheel: { wheel_name: 'Error loading wheel' },
        rigging: {}
      });
    }
  }

  fetchWheelAndParticipants() {
    this.setState({fetchPending: true});
    this.props.dispatchWheelGet(this.props.match.params.wheel_id);
    this.props.dispatchListParticipantsGet(this.props.match.params.wheel_id);
  }

  toggleResetModal = () => {
    this.setState({resetModalOpen: !this.state.resetModalOpen});
  };

  toggleParticipantModal = () => {
    this.setState({participantModalOpen: !this.state.participantModalOpen});
  };

  handleCreateParticipant = (participant: ParticipantType) => {
    this.props.dispatchCreateParticipantPost(this.props.match.params.wheel_id, participant);
    this.setState({createPending: true});
  };

  handleUpdateParticipant = (participant: ParticipantType) => {
    this.props.dispatchUpdateParticipantPut(this.props.match.params.wheel_id, participant);
    this.setState({updatePending: true});
  };

  handleDeleteParticipant = (participant: ParticipantType) => {
    this.props.dispatchDeleteParticipantDelete(this.props.match.params.wheel_id, participant.participant_id);
    this.setState({deletePending: true});
  };

  handleRigParticipant = (participant: ParticipantType) => {
    let {participant_id} = this.state.rigging;

    // Do nothing if we're already rigged
    if (participant_id === participant.participant_id) {
      return;
    }

    // Rig this participant
    this.props.dispatchRigParticipantPost(this.props.match.params.wheel_id, participant.participant_id, false);
    this.setState({rigging: {participant_id: participant.participant_id, hidden: false}});
  };

  handleHiddenRigParticipant = (participant: ParticipantType) => {
    let {participant_id, hidden} = this.state.rigging;
    // Change the hidden rig state if this participant is already rigged, otherwise do nothing
    if (participant_id === participant.participant_id) {
      this.props.dispatchRigParticipantPost(this.props.match.params.wheel_id, participant.participant_id, !hidden);
      this.setState({rigging: {participant_id: participant.participant_id, hidden: !hidden}});
    }
  };

  unrigWheel = () => {
    this.props.dispatchUnrigParticipantDelete(this.props.match.params.wheel_id);
    this.setState({rigging: {}, unrigCompleted: false});
  };

  handleResetWheel = () => {
    this.props.dispatchResetWheelPost(this.props.match.params.wheel_id);
    this.setState({resetPending: true});
  };

  render() {
    const {participantModalOpen, resetModalOpen, rigging, wheel, participants} = this.state;
    const {wheelFetch, listParticipantsFetch} = this.props;
    let participantRows = [];
    let participantModal = undefined;
    let wheelName = '';
    let riggingNotifications = undefined;
    let unrigButton = <div></div>;

    // Create components that depend on listParticipantsFetch completed
    if (listParticipantsFetch.rejected) {
      participantRows = [<tr key='rejected'><td colSpan={6}>Oops... Could not fetch participants data!</td></tr>];
      participantModal = (<div>Oops... Could not fetch participants data!</div>);
    }

    if (participants === undefined) {
      participantRows.push(<tr key='fetching'><td colSpan={6}>Loading...</td></tr>);
      participantModal = (<div style={{padding: '15px'}}>Loading...</div>);
    } else {
      let totalParticipantWeight = participants.reduce((total, p) => (total + p.weight), 0)
      for (let participant of participants) {
        let isRig = rigging.participant_id === participant.participant_id;
        let isHidden = isRig && rigging.hidden;

        participantRows.push(<ParticipantRow key={participant.participant_id} participant={participant}
                                                       totalParticipantWeight={totalParticipantWeight}
                                                       rig={isRig}
                                                       hidden={isHidden}
                                                       onEdit={this.handleUpdateParticipant}
                                                       onDelete={this.handleDeleteParticipant}
                                                       onRig={this.handleRigParticipant}
                                                       onHidden={this.handleHiddenRigParticipant}
                                                       participantList={participants}/>);
      }

      participantModal = (<div className='pull-right'>
                            <ParticipantModal isOpen={participantModalOpen}
                                              onSubmit={this.handleCreateParticipant}
                                              onClose={this.toggleParticipantModal}
                                              participant={undefined}
                                              participantList={participants} />
                            <PermissionGuard permission="manage_participants">
                              <Button onClick={this.toggleParticipantModal} variant='primary' size='sm' className='float-end'>
                                Add New Participant
                              </Button>
                            </PermissionGuard>
                          </div>)
    }

    if (wheelFetch.fulfilled) {
      this.existingWheel = wheelFetch.value;
    }

    // Create components that depend on wheelFetch completed
    if (wheelFetch.rejected) {
      wheelName = 'Wheel information could not be loaded.';
      riggingNotifications = <div className='notification'>{wheelName}</div>;
    } else if (wheel === undefined) {
      wheelName = 'Loading Wheel information...';
      riggingNotifications = <div style={{padding: '15px'}}>Loading wheel information...</div>;
    } else {
      wheelName = wheel.wheel_name || wheel.name;
      if (rigging.participant_id !== undefined) {
        if (listParticipantsFetch.rejected) {
          riggingNotifications = <div className='notification'>Participant information could not be loaded.</div>;
        } else if (participants !== undefined) {
          const riggedParticipantName = participants.filter(p => p.participant_id === rigging.participant_id)[0].participant_name;

          riggingNotifications =
            <div className='notification'>{riggedParticipantName} is {rigging.hidden ? 'deceptively ' : 'comically '}
              rigged.</div>

          unrigButton =
            <Button onClick={this.unrigWheel} variant='primary' size='sm' className='float-end' >
            Un-rig
            </Button>;

        } else {
          riggingNotifications = <div className='notification'>Loading participant information...</div>
        }
      }
      else {
        riggingNotifications = <div className='notification'>Nothing is rigged.</div>
        unrigButton = <div></div>
      }
    }

    return (
      <div className='pageRoot'>
        <ConfirmationModal isModalOpen={resetModalOpen}
                           message={'Are you sure you want to reset this wheel\'s weights? This action can\'t be undone.'}
                           onConfirm={this.handleResetWheel}
                           closeModal={this.toggleResetModal}/>
        <h1 className='title'>
          <div className='title-text'>{wheelName}</div>
        </h1>
        <div className='container-fluid'>
          <Card>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}>
              <div style={{display: 'flex', gap: '10px'}}>
                <LinkWrapper to=''>
                  <Button size='sm' className='backButton'>
                    Back
                  </Button>
                </LinkWrapper>
                <LinkWrapper to={`wheel/${this.props.match.params.wheel_id}`}>
                  <Button size='sm'>
                    Go to Wheel
                  </Button>
                </LinkWrapper>
              </div>
              <div>
                {riggingNotifications}
              </div>
            </div>

            <div className='notification' id='notification' />
            <Card.Header>
              <div className='tableHeader'>
                Participants
                <ButtonToolbar className='float-end' style={{gap: '10px'}}>
                  <ButtonGroup>
                    {unrigButton}
                  </ButtonGroup>
                  <ButtonGroup>
                    {participantModal}
                  </ButtonGroup>
                  <PermissionGuard permission="manage_participants">
                    <ButtonGroup>
                      <Button onClick={this.toggleResetModal} variant='warning' size='sm' >
                        Reset Weights
                      </Button>
                    </ButtonGroup>
                  </PermissionGuard>
                </ButtonToolbar>
              </div>
            </Card.Header>
            {this.state.errorVisible ? <div className='errorNotification'>Participant already exists</div> : null}
            <Table striped hover>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>URL</th>
                  <th>Chance of Selection</th>
                  <th>Operations</th>
                  <th>Rig</th>
                  <th>Hidden Rig</th>
                </tr>
              </thead>
              <tbody>
                {participantRows}
              </tbody>
            </Table>
          </Card>
        </div>
      </div>
    )
  }
}

export default connect([
  {
    resource: 'wheel',
    request: (wheelId) => ({
      url: apiURL(`wheels/${wheelId}`),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'listParticipants',
    request: (wheelId) => ({
      url: apiURL(`wheels/${wheelId}/participants`),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'createParticipant',
    method: 'post',
    request: (wheelId, participant) => ({
      url: apiURL(`wheels/${wheelId}/participants`),
      headers: getAuthHeaders(),
      body: JSON.stringify(participant)
    })
  },
  {
    resource: 'updateParticipant',
    method: 'put',
    request: (wheelId, participant) => ({
      url: apiURL(`wheels/${wheelId}/participants/${participant.participant_id}`),
      headers: getAuthHeaders(),
      body: JSON.stringify(participant)
    })
  },
  {
    resource: 'deleteParticipant',
    method: 'delete',
    request: (wheelId, participantId) => ({
      url: apiURL(`wheels/${wheelId}/participants/${participantId}`),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'rigParticipant',
    method: 'post',
    request: (wheelId, participantId, hidden) => ({
      url: apiURL(`wheels/${wheelId}/participants/${participantId}/rig`),
      headers: getAuthHeaders(),
      body: JSON.stringify({
        hidden: hidden,
      })
    })
  },
  {
    resource: 'unrigParticipant',
    method: 'delete',
    request: (wheelId) => ({
      url: apiURL(`wheels/${wheelId}/unrig`),
      headers: getAuthHeaders()
    })
  },
  {
    resource: 'resetWheel',
    method: 'post',
    request: (wheelId) => ({
      url: apiURL(`wheels/${wheelId}/reset`),
      headers: getAuthHeaders()
    })
  }
])(ParticipantTable);
