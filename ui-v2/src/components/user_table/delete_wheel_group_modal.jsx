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

import React, { Component } from 'react';
import { Modal, Button, Form, Alert } from 'react-bootstrap';
import PropTypes from 'prop-types';

// Constants
const CONFIRMATION_TEXT = 'Delete Wheel Group';

const MODAL_CONFIG = {
  TITLE: 'Permanently Delete Wheel Group',
  WARNING_MESSAGE: 'This action cannot be undone! This will permanently delete:',
  ITEMS_TO_DELETE: [
    '• Your entire wheel group organization',
    '• All users in your wheel group',
    '• All wheels and their participants',
    '• All data associated with your wheel group'
  ],
  CONFIRMATION_INSTRUCTION: `Type "${CONFIRMATION_TEXT}" to confirm deletion:`,
  DELETE_BUTTON_TEXT: 'Delete Wheel Group Forever',
  CANCEL_BUTTON_TEXT: 'Cancel'
};

export default class DeleteTenantModal extends Component {
  static propTypes = {
    isModalOpen: PropTypes.bool.isRequired,
    onConfirm: PropTypes.func.isRequired,
    onClose: PropTypes.func.isRequired,
    wheelGroupName: PropTypes.string,
    isDeleting: PropTypes.bool
  };

  static defaultProps = {
    wheelGroupName: 'your wheel group',
    isDeleting: false
  };

  constructor(props) {
    super(props);
    this.state = {
      confirmationText: '',
      error: null
    };
  }

  // Reset state when modal opens/closes
  componentDidUpdate(prevProps) {
    if (this.props.isModalOpen !== prevProps.isModalOpen) {
      if (this.props.isModalOpen) {
        this.setState({ confirmationText: '', error: null });
      }
    }
  }

  handleConfirmationChange = (event) => {
    this.setState({ 
      confirmationText: event.target.value,
      error: null 
    });
  };

  handleSubmit = (event) => {
    event.preventDefault();
    
    if (this.state.confirmationText !== CONFIRMATION_TEXT) {
      this.setState({ 
        error: `Please type "${CONFIRMATION_TEXT}" exactly as shown to confirm deletion.` 
      });
      return;
    }

    this.props.onConfirm();
  };

  handleClose = () => {
    if (!this.props.isDeleting) {
      this.props.onClose();
    }
  };

  render() {
    const { isModalOpen, wheelGroupName, isDeleting } = this.props;
    const { confirmationText, error } = this.state;
    
    const isConfirmationValid = confirmationText === CONFIRMATION_TEXT;

    return (
      <Modal 
        show={isModalOpen} 
        onHide={this.handleClose}
        size="md"
        backdrop={isDeleting ? 'static' : true}
        keyboard={!isDeleting}
        centered
      >
        <Modal.Header closeButton={!isDeleting}>
          <Modal.Title className="text-danger">
            {MODAL_CONFIG.TITLE}
          </Modal.Title>
        </Modal.Header>

        <Modal.Body>
          <Alert variant="danger" className="mb-3">
            <Alert.Heading className="h6">
              {MODAL_CONFIG.WARNING_MESSAGE}
            </Alert.Heading>
            <ul className="mb-0 ps-3">
              {MODAL_CONFIG.ITEMS_TO_DELETE.map((item, index) => (
                <li key={index} className="mb-1">{item}</li>
              ))}
            </ul>
          </Alert>

          <div className="mb-3">
            <strong>Wheel Group to be deleted:</strong> "{wheelGroupName}"
          </div>

          <Form onSubmit={this.handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label className="fw-bold">
                {MODAL_CONFIG.CONFIRMATION_INSTRUCTION}
              </Form.Label>
              <Form.Control
                type="text"
                value={confirmationText}
                onChange={this.handleConfirmationChange}
                placeholder={CONFIRMATION_TEXT}
                disabled={isDeleting}
                autoFocus
                className={error ? 'is-invalid' : ''}
              />
              {error && (
                <div className="invalid-feedback">
                  {error}
                </div>
              )}
            </Form.Group>

            {isDeleting && (
              <Alert variant="warning" className="mb-3">
                <div className="d-flex align-items-center">
                  <div className="spinner-border spinner-border-sm me-2" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </div>
                  <span>Deleting wheel group and all associated data... Please wait.</span>
                </div>
              </Alert>
            )}
          </Form>
        </Modal.Body>

        <Modal.Footer>
          <Button 
            variant="secondary" 
            onClick={this.handleClose}
            disabled={isDeleting}
          >
            {MODAL_CONFIG.CANCEL_BUTTON_TEXT}
          </Button>
          <Button 
            variant="danger" 
            onClick={this.handleSubmit}
            disabled={!isConfirmationValid || isDeleting}
            className="text-white"
          >
            {isDeleting ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status">
                  <span className="visually-hidden">Loading...</span>
                </span>
                Deleting...
              </>
            ) : (
              MODAL_CONFIG.DELETE_BUTTON_TEXT
            )}
          </Button>
        </Modal.Footer>
      </Modal>
    );
  }
}
