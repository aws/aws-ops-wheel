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
  isModalOpen: PropTypes.boolean;
  wheel: WheelType | undefined;
  onClose: PropTypes.func;
  onSubmit: PropTypes.func;
}

interface WheelModalState {
  wheel: WheelType;
  isAdd: PropTypes.boolean;
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
    this.props.onSubmit(this.state.wheel);
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
    this.setState(
      {
        isAdd: wheel === undefined,
        wheel: Object.assign({}, wheel || defaultWheel)

      });
  };

  render() {
    const {isModalOpen} = this.props;
    const {wheel, isAdd} = this.state;

    const heading: string = isAdd ? 'Add a new wheel' : 'Edit an existing wheel';
    const submitText: string = isAdd ? 'Add Wheel' : 'Update Wheel';
    const modalStyle = {
      position: 'fixed',
      zIndex: 1040,
      top: 0, bottom: 0, left: 0, right: 0
    };

    return (
      <div>
        <Modal
          show={isModalOpen}
          onEntering={this.modalAfterOpen}
          onHide={this.onClose}
          style={modalStyle}
        >
          <Modal.Header closeButton>
            <Modal.Title>{heading}</Modal.Title>
          </Modal.Header>
          <Modal.Body className='form-group'>
            <Form>
              <div className='form-group'>
                <label htmlFor='wheel-name' className='control-label'>Wheel Name</label>
                <input
                  type='text'
                  name='name'
                  className='form-control'
                  onChange={this.onChange}
                  value={wheel.name}
                />
              </div>
              <Modal.Footer>
                <Button
                  onClick={this.onClose}>
                  Cancel
                </Button>
                <Button
                  type='submit'
                  onClick={this.onSubmit}
                  className='btn btn-success'
                  disabled={!this.state.wheel.name}>
                  {submitText}
                </Button>
              </Modal.Footer>
            </Form>
          </Modal.Body>
        </Modal>
      </div>
    );
  };
}
