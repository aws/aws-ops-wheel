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
import {Modal, Button, Form} from 'react-bootstrap';
import {ParticipantType} from '../../types';
import {validate} from 'validate.js';

validate.options = {format: 'flat'};
validate.validators.uniqueName = function(participant, participantList, key, attributes) {
  const participantWithName = participantList.filter(existingParticipant => existingParticipant.name === participant.name);
  if(participantWithName.length > 0 && participantWithName[0].id !== participant.id) {
    return 'Name is already taken';
  }
  return undefined;
};

interface ParticipantModalProps {
  isOpen: boolean;
  onSubmit: Function;
  onClose: Function;
  participant: ParticipantType;
  participantList: ParticipantType[];
}

interface ParticipantModalState {
  participant: ParticipantType,
  isAdd: boolean,
}

const defaultParticipant = {
  id: '',
  name: '',
  url: '',
  weight: 1
};

export default class ParticipantModal extends Component<ParticipantModalProps, ParticipantModalState> {
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
    this.props.onSubmit(this.state.participant);
    this.modalOnClose();
  }

  modalAfterOpen() {
    const {participant} = this.props;
    this.setState({isAdd: participant === undefined, participant: Object.assign({}, participant || defaultParticipant)});
  }

  modalOnClose() {
    this.props.onClose();
  }

  getErrors() {
    const {participantList} = this.props;
    const {name, url} = this.state.participant;

    const constraints = {
      name: {
        presence: {
          allowEmpty: false
        }
      },
      url: {
        presence: {
          allowEmpty: false
        },
        url: true
      }
    };

    let errors = validate({name: name, url: url}, constraints) || [];
    const uniqueNameError = validate({participant: this.state.participant}, {participant: {uniqueName: participantList}}, {fullMessages: false});
    if (uniqueNameError) {
      errors.push(uniqueNameError[0]);
    }

    return errors.map(error => <div key={error}>{error}</div>);
  }

  render() {
    const {isOpen} = this.props;
    const {participant, isAdd} = this.state;

    const heading = isAdd ? 'Add a new participant' : 'Edit an existing participant';
    const submitText = isAdd ? 'Add Participant' : 'Update Participant';
    const modalStyle = {
      position: 'fixed',
      zIndex: 1040,
      top: 0, bottom: 0, left: 0, right: 0
    };

    const errors = isOpen ? this.getErrors() : [<div key='closedModal'>Modal is closed.</div>];
    const isDisabled = errors.length > 0;

    return (
      <div>
        <Modal show={isOpen} onEntering={this.modalAfterOpen} onHide={this.modalOnClose} style={modalStyle}>
          <Form>
            <Modal.Header closeButton>
              <Modal.Title>{heading}</Modal.Title>
            </Modal.Header>
            <Modal.Body className='form-group'>
              <div className='form-group'>
                <label htmlFor='participant-name' className='control-label'>Participant Name</label>
                <input type='text' name='name' className='form-control' value={participant.name} onChange={this.onChange} />
              </div>
              <div className='form-group'>
                <label htmlFor='participant-url' className='control-label'>Participant URL</label>
                <input type='text' name='url' className='form-control' value={participant.url} onChange={this.onChange} />
              </div>
            </Modal.Body>
            <Modal.Footer>
              <div>{errors}</div>
              <Button onClick={this.modalOnClose}>Cancel</Button>
              <Button type='submit' onClick={this.onSubmit} className='btn btn-success' disabled={isDisabled}>{submitText}</Button>
            </Modal.Footer>
          </Form>
        </Modal>
      </div>
    );
  }
}
