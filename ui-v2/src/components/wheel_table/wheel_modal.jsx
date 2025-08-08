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
import {WheelType} from '../../types';

export interface WheelModalProps {
  isModalOpen: bool;
  wheel: WheelType | undefined;
  onClose: PropTypes.func;
  onSubmit: PropTypes.func;
}

interface WheelModalState {
  wheel: WheelType;
  isAdd: bool;
}

const defaultWheel: WheelType = {
  id: '',
  name: '',
  participant_count: 0,
};

export default class WheelModal extends Component<WheelModalProps, WheelModalState> {
  constructor(props: WheelModalProps) {
    super(props);
    this.state = {
      wheel: Object.assign({}, defaultWheel),
      isAdd: false,
    };
    this.onChange = this.onChange.bind(this);
    this.onSubmit = this.onSubmit.bind(this);
    this.modalAfterOpen = this.modalAfterOpen.bind(this);
    this.onClose = this.onClose.bind(this);
  }

  onSubmit(event: React.MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    // For updates, only send the fields that can be updated
    const wheelData = this.state.isAdd ? {
      wheel_name: this.state.wheel.name
    } : {
      wheel_id: this.state.wheel.wheel_id,
      wheel_name: this.state.wheel.name
    };
    this.props.onSubmit(wheelData);
    this.onClose();
  };

  onClose() {
    this.props.onClose();
  }

  onChange(event: any) {
    const {wheel} = this.state;
    this.setState({wheel: Object.assign({}, wheel, {[event.target.name]: event.target.value})});
  };

  modalAfterOpen() {
    const {wheel} = this.props;
    // Convert API 'wheel_name' to frontend 'name' format for editing
    const wheelForEditing = wheel ? {
      ...wheel,
      name: wheel.wheel_name || wheel.name || ''
    } : defaultWheel;
    
    this.setState(
      {
        isAdd: wheel === undefined,
        wheel: Object.assign({}, wheelForEditing)
      });
  };

  render() {
    const {isModalOpen} = this.props;
    const {wheel, isAdd} = this.state;

    const heading: string = isAdd ? 'Add a new wheel' : 'Edit an existing wheel';
    const submitText: string = isAdd ? 'Add Wheel' : 'Update Wheel';

    return (
      <div>
        <Modal
          show={isModalOpen}
          onEntering={this.modalAfterOpen}
          onHide={this.onClose}
          size="lg"
        >
          <Modal.Header closeButton>
            <Modal.Title>{heading}</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <Form>
              <Form.Group className='mb-3'>
                <Form.Label htmlFor='wheel-name'>Wheel Name</Form.Label>
                <Form.Control
                  type='text'
                  name='name'
                  onChange={this.onChange}
                  value={wheel.name}
                />
              </Form.Group>
            </Form>
          </Modal.Body>
          <Modal.Footer>
                <Button
                  onClick={this.onClose}>
                  Cancel
                </Button>
                <Button
                  type='submit'
                  onClick={this.onSubmit}
                  variant='success'
                  disabled={!this.state.wheel.name}>
                  {submitText}
                </Button>
          </Modal.Footer>
        </Modal>
      </div>
    );
  };
}
