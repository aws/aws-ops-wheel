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

import * as React from 'react';
import {Modal, Button} from 'react-bootstrap';

interface ConfirmationModalProps {
  message: string;
  isModalOpen: boolean;
  onConfirm: () => void;
  closeModal: () => void;
}

export default class ConfirmationModal extends React.Component<ConfirmationModalProps, {}> {
  constructor(props: ConfirmationModalProps) {
    super(props);
    this.close = this.close.bind(this);
    this.onConfirm = this.onConfirm.bind(this);
  }

  close() {
    this.props.closeModal();
  }

  onConfirm() {
    this.props.onConfirm();
    this.close();
  }

  render() {
    const {message, isModalOpen} = this.props;
    return (
      <Modal
        show={isModalOpen}
        onHide={this.close}
      >
        <Modal.Header>
          <Modal.Title>Are you sure?</Modal.Title>
        </Modal.Header>
        <Modal.Body>{message}</Modal.Body>
        <Modal.Footer>
          <Button
            onClick={this.close}
            variant='success'
            size='sm'
          >
            Cancel
          </Button>
          <Button
            onClick={this.onConfirm}
            variant='danger'
            size='sm'
          >
            Yes
          </Button>
        </Modal.Footer>
      </Modal>
    );
  }
}
