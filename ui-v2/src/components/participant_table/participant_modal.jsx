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
import {Modal, Button, Form} from 'react-bootstrap';
import {validate} from 'validate.js';

validate.options = {format: 'flat'};
validate.validators.uniqueName = function(participant, participantList, key, attributes) {
  const participantWithName = participantList.filter(existingParticipant => existingParticipant.participant_name === participant.participant_name);
  if(participantWithName.length > 0 && participantWithName[0].participant_id !== participant.participant_id) {
    return 'Name is already taken';
  }
  return undefined;
};

const defaultParticipant = {
  participant_id: '',
  participant_name: '',
  participant_url: '',
  weight: 1
};

export default class ParticipantModal extends Component {
  constructor(props) {
    super(props);
    this.state = {
      participant: Object.assign({}, defaultParticipant),
      isAdd: false,
    };
    this.onChange = this.onChange.bind(this);
    this.onSubmit = this.onSubmit.bind(this);
    this.modalAfterOpen = this.modalAfterOpen.bind(this);
    this.modalOnClose = this.modalOnClose.bind(this);
  }

  onChange(event) {
    this.setState({participant: Object.assign({}, this.state.participant, {[event.target.name]: event.target.value})});
  }

  onSubmit(event) {
    event.preventDefault();
    
    if (this.state.isAdd) {
      // For new participants, don't include participant_id
      const participantData = {
        participant_name: this.state.participant.participant_name,
        participant_url: this.state.participant.participant_url,
        weight: this.state.participant.weight
      };
      this.props.onSubmit(participantData);
    } else {
      // For updates, include participant_id so the API call can build the URL correctly
      const participantData = {
        participant_id: this.state.participant.participant_id,
        participant_name: this.state.participant.participant_name,
        participant_url: this.state.participant.participant_url,
        weight: this.state.participant.weight
      };
      this.props.onSubmit(participantData);
    }
    
    this.modalOnClose();
  }

  modalAfterOpen() {
    const {participant} = this.props;
    console.log('Modal opening with participant:', participant);
    
    if (participant && participant.participant_id) {
      // Ensure participant has the correct field structure
      const participantToEdit = {
        participant_id: participant.participant_id || '',
        participant_name: participant.participant_name || '',
        participant_url: participant.participant_url || '',
        weight: participant.weight || 1
      };
      
      console.log('Setting participant state to:', participantToEdit);
      this.setState({isAdd: false, participant: participantToEdit});
    } else {
      console.log('Setting default participant for new participant');
      this.setState({isAdd: true, participant: Object.assign({}, defaultParticipant)});
    }
  }

  componentDidUpdate(prevProps) {
    // Also update state if props change while modal is open
    if (this.props.isOpen && this.props.participant && 
        (!prevProps.participant || prevProps.participant.participant_id !== this.props.participant.participant_id)) {
      
      const participantToEdit = {
        participant_id: this.props.participant.participant_id || '',
        participant_name: this.props.participant.participant_name || '',
        participant_url: this.props.participant.participant_url || '',
        weight: this.props.participant.weight || 1
      };
      
      console.log('Updating participant state from componentDidUpdate:', participantToEdit);
      this.setState({isAdd: false, participant: participantToEdit});
    }
  }

  modalOnClose() {
    this.props.onClose();
  }

  getErrors() {
    const {participantList} = this.props;
    const {participant_name, participant_url} = this.state.participant;

    // Only validate if we have participant data loaded
    if (!participant_name && participant_name !== '') {
      return [];
    }

    const constraints = {
      participant_name: {
        presence: {
          allowEmpty: false,
          message: 'Name can\'t be blank'
        }
      },
      participant_url: {
        url: {
          allowEmpty: true,
          message: 'URL must be valid'
        }
      }
    };

    let errors = validate({participant_name: participant_name, participant_url: participant_url}, constraints) || [];
    
    // Check for unique name
    if (participantList && participantList.length > 0) {
      const uniqueNameError = validate({participant: this.state.participant}, {participant: {uniqueName: participantList}}, {fullMessages: false});
      if (uniqueNameError) {
        errors.push(uniqueNameError[0]);
      }
    }

    return errors.map(error => <div key={error}>{error}</div>);
  }

  render() {
    const {isOpen} = this.props;
    const {participant, isAdd} = this.state;

    console.log('Modal render - participant state:', participant);
    console.log('Modal render - isAdd:', isAdd);
    console.log('Modal render - props participant:', this.props.participant);

    const heading = isAdd ? 'Add a new participant' : 'Edit an existing participant';
    const submitText = isAdd ? 'Add Participant' : 'Update Participant';

    const errors = isOpen ? this.getErrors() : [<div key='closedModal'>Modal is closed.</div>];
    const isDisabled = errors.length > 0;

    // Use state participant values directly
    const participantName = participant ? participant.participant_name || '' : '';
    const participantUrl = participant ? participant.participant_url || '' : '';
    
    // Create unique IDs to avoid conflicts when multiple modals exist
    const participantNameId = isAdd ? 'participant-name-add' : `participant-name-edit-${participant.participant_id || 'new'}`;
    const participantUrlId = isAdd ? 'participant-url-add' : `participant-url-edit-${participant.participant_id || 'new'}`;

    return (
      <div>
        <Modal show={isOpen} onEntering={this.modalAfterOpen} onHide={this.modalOnClose} size="lg">
          <Form>
            <Modal.Header closeButton>
              <Modal.Title>{heading}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
              <Form.Group className='mb-3'>
                <Form.Label htmlFor={participantNameId}>Participant Name</Form.Label>
                <Form.Control 
                  id={participantNameId}
                  type='text' 
                  name='participant_name' 
                  value={participantName} 
                  onChange={this.onChange}
                  placeholder="Enter participant name"
                />
              </Form.Group>
              <Form.Group className='mb-3'>
                <Form.Label htmlFor={participantUrlId}>Participant URL</Form.Label>
                <Form.Control 
                  id={participantUrlId}
                  type='text' 
                  name='participant_url' 
                  value={participantUrl} 
                  onChange={this.onChange}
                  placeholder="Enter participant URL"
                />
              </Form.Group>
            </Modal.Body>
            <Modal.Footer>
              <div>{errors}</div>
              <Button onClick={this.modalOnClose}>Cancel</Button>
              <Button type='submit' onClick={this.onSubmit} variant='success' disabled={isDisabled}>{submitText}</Button>
            </Modal.Footer>
          </Form>
        </Modal>
      </div>
    );
  }
}
