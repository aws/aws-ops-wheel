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
import { Modal, Button } from 'react-bootstrap';
import PropTypes from 'prop-types';

// Modal Configuration Constants
const MODAL_CONFIG = {
  DEFAULT_SIZE: 'sm',
  BACKDROP: true,
  KEYBOARD: true,
  SHOW_CLOSE_BUTTON: false
};

const MODAL_MESSAGES = {
  DEFAULT_TITLE: 'Are you sure?',
  CONFIRM_BUTTON: 'Yes',
  CANCEL_BUTTON: 'Cancel'
};

const BUTTON_VARIANTS = {
  CONFIRM: 'danger',
  CANCEL: 'success',
  PRIMARY: 'primary',
  SECONDARY: 'secondary'
};

const BUTTON_SIZES = {
  SMALL: 'sm',
  MEDIUM: 'md',
  LARGE: 'lg'
};

// Standardized Modal Patterns
const MODAL_PATTERNS = {
  CONFIRMATION: {
    title: MODAL_MESSAGES.DEFAULT_TITLE,
    confirmVariant: BUTTON_VARIANTS.CONFIRM,
    cancelVariant: BUTTON_VARIANTS.CANCEL,
    confirmText: MODAL_MESSAGES.CONFIRM_BUTTON,
    cancelText: MODAL_MESSAGES.CANCEL_BUTTON
  },
  INFO: {
    title: 'Information',
    confirmVariant: BUTTON_VARIANTS.PRIMARY,
    cancelVariant: BUTTON_VARIANTS.SECONDARY,
    confirmText: 'OK',
    cancelText: 'Close'
  },
  WARNING: {
    title: 'Warning',
    confirmVariant: BUTTON_VARIANTS.CONFIRM,
    cancelVariant: BUTTON_VARIANTS.CANCEL,
    confirmText: 'Continue',
    cancelText: 'Cancel'
  }
};

// PropTypes definition
const CONFIRMATION_MODAL_PROP_TYPES = {
  message: PropTypes.string.isRequired,
  isModalOpen: PropTypes.bool.isRequired,
  onConfirm: PropTypes.func.isRequired,
  closeModal: PropTypes.func.isRequired,
  title: PropTypes.string,
  confirmText: PropTypes.string,
  cancelText: PropTypes.string,
  confirmVariant: PropTypes.string,
  cancelVariant: PropTypes.string,
  size: PropTypes.string,
  pattern: PropTypes.oneOf(['confirmation', 'info', 'warning'])
};

export default class ConfirmationModal extends React.Component {
  static propTypes = CONFIRMATION_MODAL_PROP_TYPES;

  static defaultProps = {
    title: MODAL_MESSAGES.DEFAULT_TITLE,
    confirmText: MODAL_MESSAGES.CONFIRM_BUTTON,
    cancelText: MODAL_MESSAGES.CANCEL_BUTTON,
    confirmVariant: BUTTON_VARIANTS.CONFIRM,
    cancelVariant: BUTTON_VARIANTS.CANCEL,
    size: BUTTON_SIZES.SMALL,
    pattern: 'confirmation'
  };

  constructor(props) {
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

  getModalConfig() {
    const { pattern } = this.props;
    return MODAL_PATTERNS[pattern.toUpperCase()] || MODAL_PATTERNS.CONFIRMATION;
  }

  render() {
    const { message, isModalOpen, size } = this.props;
    const modalConfig = this.getModalConfig();
    
    // Use pattern defaults or prop overrides
    const title = this.props.title || modalConfig.title;
    const confirmText = this.props.confirmText || modalConfig.confirmText;
    const cancelText = this.props.cancelText || modalConfig.cancelText;
    const confirmVariant = this.props.confirmVariant || modalConfig.confirmVariant;
    const cancelVariant = this.props.cancelVariant || modalConfig.cancelVariant;

    return (
      <Modal
        show={isModalOpen}
        onHide={this.close}
        backdrop={MODAL_CONFIG.BACKDROP}
        keyboard={MODAL_CONFIG.KEYBOARD}
      >
        <Modal.Header closeButton={MODAL_CONFIG.SHOW_CLOSE_BUTTON}>
          <Modal.Title>{title}</Modal.Title>
        </Modal.Header>
        <Modal.Body>{message}</Modal.Body>
        <Modal.Footer>
          <Button
            onClick={this.close}
            variant={cancelVariant}
            size={size}
          >
            {cancelText}
          </Button>
          <Button
            onClick={this.onConfirm}
            variant={confirmVariant}
            size={size}
          >
            {confirmText}
          </Button>
        </Modal.Footer>
      </Modal>
    );
  }
}

// Export constants for use by other modal components
export { MODAL_CONFIG, MODAL_MESSAGES, BUTTON_VARIANTS, BUTTON_SIZES, MODAL_PATTERNS };
