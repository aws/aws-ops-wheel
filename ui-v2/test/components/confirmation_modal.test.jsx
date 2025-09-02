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
import {expect} from 'chai';
import * as sinon from 'sinon';
import ConfirmationModal from '../../src/components/confirmation_modal';
import '../globals';
import {Button} from 'react-bootstrap';
import {mount, shallow} from 'enzyme';


describe('ConfirmationModal', function() {
  // sinon.sandbox lets us group these spies together and reset them after every test
  const sandbox = sinon.createSandbox();
  afterEach(() =>{
    sandbox.reset();
  });

  const props = {
    isModalOpen: true,
    message: 'test_message',
    closeModal: sandbox.spy(),
    onConfirm: sandbox.spy(),
  };

  it('Should mount and render with modal open in edit mode', () => {
    const wrapper = mount(<ConfirmationModal {...props} />);
    expect(wrapper.html()).to.contain('message');
  });

  it('Should call props.onSubmit() and props.onClose() upon submit', () => {
    const wrapper = shallow(<ConfirmationModal {...props} />);
    // Call modalAfterOpen to update state
    wrapper.find(Button).at(1).simulate('click', {preventDefault: () => {}});
    expect(props.onConfirm.calledOnce).to.be.true;
    expect(props.closeModal.calledOnce).to.be.true;
  });

});