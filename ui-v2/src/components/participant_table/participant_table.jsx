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
import {Card, Table, Button, ButtonGroup, ButtonToolbar} from 'react-bootstrap';
import connect from 'react-redux-fetch';
import ParticipantRow from './participant_row';
import ParticipantModal from './participant_modal';
import ConfirmationModal from '../confirmation_modal';
import {apiURL, getAuthHeaders} from '../../util';
import {LinkWrapper} from '../../util';
import PermissionGuard from '../PermissionGuard';

// Constants
const INITIAL_STATE = {
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
  showLastParticipantMessage: false,
};

const TABLE_HEADERS = [
  'Name',
  'URL',
  'Chance of Selection',
  'Operations',
  'Rig',
  'Hidden Rig'
];

const BUTTON_LABELS = {
  BACK: 'Back',
  GO_TO_WHEEL: 'Go to Wheel',
  ADD_PARTICIPANT: 'Add New Participant',
  RESET_WEIGHTS: 'Reset Weights',
  UNRIG: 'Un-rig'
};

const PERMISSIONS = {
  MANAGE_PARTICIPANTS: 'manage_participants'
};

export class ParticipantTable extends Component {

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
    // Safety check before calling fetchWheelAndParticipants
    if (!this.props.match || !this.props.match.params || !this.props.match.params.wheel_id) {
      console.error('componentWillMount: Missing route parameters:', {
        match: this.props.match,
        params: this.props.match?.params,
        wheel_id: this.props.match?.params?.wheel_id
      });
      this.setState({
        fetchPending: false,
        participants: [],
        wheel: { wheel_name: 'Error: Missing wheel ID in componentWillMount' },
        rigging: {}
      });
      return;
    }
    this.fetchWheelAndParticipants();
  }

  componentDidUpdate() {
    try {
      // Safety check - if no route params, don't do anything
      if (!this.props.match?.params?.wheel_id) {
        console.warn('componentDidUpdate: No wheel_id available, skipping updates');
        return;
      }

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
    
    // Safety check for props.match
    if (!this.props.match || !this.props.match.params || !this.props.match.params.wheel_id) {
      console.error('Missing route parameters:', {
        match: this.props.match,
        params: this.props.match?.params,
        wheel_id: this.props.match?.params?.wheel_id
      });
      this.setState({
        fetchPending: false,
        participants: [],
        wheel: { wheel_name: 'Error: Missing wheel ID' },
        rigging: {}
      });
      return;
    }
    
    this.props.dispatchWheelGet(this.props.match.params.wheel_id);
    this.props.dispatchListParticipantsGet(this.props.match.params.wheel_id);
  }

  toggleResetModal = () => {
    this.setState({resetModalOpen: !this.state.resetModalOpen});
  };

  toggleParticipantModal = () => {
    this.setState({participantModalOpen: !this.state.participantModalOpen});
  };

  handleCreateParticipant = (participant) => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot create participant: missing wheel_id');
      return;
    }
    this.props.dispatchCreateParticipantPost(this.props.match.params.wheel_id, participant);
    this.setState({createPending: true});
  };

  handleUpdateParticipant = (participant) => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot update participant: missing wheel_id');
      return;
    }
    this.props.dispatchUpdateParticipantPut(this.props.match.params.wheel_id, participant);
    this.setState({updatePending: true});
  };

  handleDeleteParticipant = (participant) => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot delete participant: missing wheel_id');
      return;
    }
    
    // Check if this is the last participant
    if (this.state.participants && this.state.participants.length <= 1) {
      this.showLastParticipantMessage();
      return;
    }
    
    this.props.dispatchDeleteParticipantDelete(this.props.match.params.wheel_id, participant.participant_id);
    this.setState({deletePending: true});
  };

  showLastParticipantMessage = () => {
    this.setState({showLastParticipantMessage: true});
    // Hide the message after 2 seconds
    setTimeout(() => {
      this.setState({showLastParticipantMessage: false});
    }, 2000);
  };

  handleRigParticipant = (participant) => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot rig participant: missing wheel_id');
      return;
    }

    let {participant_id} = this.state.rigging;

    // Do nothing if we're already rigged
    if (participant_id === participant.participant_id) {
      return;
    }

    // Rig this participant
    this.props.dispatchRigParticipantPost(this.props.match.params.wheel_id, participant.participant_id, false);
    this.setState({rigging: {participant_id: participant.participant_id, hidden: false}});
  };

  handleHiddenRigParticipant = (participant) => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot toggle hidden rig: missing wheel_id');
      return;
    }

    let {participant_id, hidden} = this.state.rigging;
    // Change the hidden rig state if this participant is already rigged, otherwise do nothing
    if (participant_id === participant.participant_id) {
      this.props.dispatchRigParticipantPost(this.props.match.params.wheel_id, participant.participant_id, !hidden);
      this.setState({rigging: {participant_id: participant.participant_id, hidden: !hidden}});
    }
  };

  unrigWheel = () => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot unrig wheel: missing wheel_id');
      return;
    }
    this.props.dispatchUnrigParticipantDelete(this.props.match.params.wheel_id);
    this.setState({rigging: {}, unrigCompleted: false});
  };

  handleResetWheel = () => {
    if (!this.props.match?.params?.wheel_id) {
      console.error('Cannot reset wheel: missing wheel_id');
      return;
    }
    this.props.dispatchResetWheelPost(this.props.match.params.wheel_id);
    this.setState({resetPending: true});
  };

  render() {
    // Safety check for routing props
    if (!this.props.match || !this.props.match.params || !this.props.match.params.wheel_id) {
      return (
        <div className='pageRoot'>
          <h1 className='title'>
            <div className='title-text'>Error: Invalid Route</div>
          </h1>
          <div className='container-fluid'>
            <div className='alert alert-danger'>
              Unable to load participant data. Please navigate back and try again.
              <br />
              Debug info: {JSON.stringify({
                hasMatch: !!this.props.match,
                hasParams: !!this.props.match?.params,
                wheelId: this.props.match?.params?.wheel_id
              })}
            </div>
          </div>
        </div>
      );
    }

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
                <LinkWrapper to={`wheel/${this.props.match?.params?.wheel_id || ''}`}>
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
        
        {/* Popup message for last participant deletion attempt */}
        {this.state.showLastParticipantMessage && (
          <div style={{
            position: 'fixed',
            bottom: '20px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#dc3545',
            color: 'white',
            padding: '12px 24px',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            zIndex: 9999,
            fontSize: '14px',
            fontWeight: '500'
          }}>
            Cannot delete the last participant from a wheel
          </div>
        )}
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
