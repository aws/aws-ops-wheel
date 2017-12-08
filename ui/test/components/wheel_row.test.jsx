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
import WheelRow from '../../src/components/wheel_table/wheel_row';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';
import {mount} from 'enzyme';


describe('WheelRow', function() {
  const sandbox = sinon.sandbox.create();
  afterEach(() => {
    sandbox.reset();
  });

  const wheel = shimData.wheels[0];

  const props = {
    wheel: wheel,
    onEdit: sandbox.spy(),
    onDelete: sandbox.spy(),
  };

  it('Should render and display wheel name', () => {
    const wrapper = mount(<WheelRow {...props} />);
    expect(wrapper.html()).to.contain(wheel.name);
  });

  it('Should toggle isWheelModalOpen state on click of Edit button', () => {
    const wrapper = mount(<WheelRow {...props} />);
    expect(wrapper.instance().state.isWheelModalOpen).to.be.false;
    wrapper.find(Button).at(0).simulate('click');
    expect(wrapper.instance().state.isWheelModalOpen).to.be.true;
  });

  it('Should toggle isConfirmationModalOpen state on click of Delete button', () => {
    const wrapper = mount(<WheelRow {...props} />);
    expect(wrapper.instance().state.isConfirmationModalOpen).to.be.false;
    wrapper.find(Button).at(2).simulate('click');
    expect(wrapper.instance().state.isConfirmationModalOpen).to.be.true;
  });

  it('Should call props.onEdit upon call to handleWheelEdit()', () => {
    const wrapper = mount(<WheelRow {...props} />);
    wrapper.instance().handleWheelEdit(wheel);
    expect(props.onEdit.calledWith(wheel)).to.be.true;
  });

  it('Should call props.onDelete upon call to handleWheelDelete()', () => {
    const wrapper = mount(<WheelRow {...props} />);
    wrapper.instance().handleWheelDelete(wheel);
    expect(props.onDelete.calledWith(wheel)).to.be.true;
  });


});
