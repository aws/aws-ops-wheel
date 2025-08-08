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
import WheelModal from '../../src/components/wheel_table/wheel_modal';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';
import {mount, shallow} from 'enzyme';


describe('WheelModal', function() {
  // sinon.sandbox lets us group these spies together and reset them after every test
  const sandbox = sinon.createSandbox();
  afterEach(() =>{
    sandbox.reset();
  });

  const wheel = shimData.wheels[0];

  const props = {
    isModalOpen: true,
    wheel: wheel,
    onClose: sandbox.spy(),
    onSubmit: sandbox.spy(),
  };

  it('Should mount and render with modal open in edit mode', () => {
    const wrapper = mount(<WheelModal {...props} />);
    expect(wrapper.instance().state.isAdd).to.be.false;
  });

  it('Should mount and render with modal open', () => {
    const wrapper = mount(<WheelModal {...Object.assign({}, props, {wheel: undefined})} />);
    expect(wrapper.instance().state.isAdd).to.be.true;
  });

  it('Should call props.onSubmit() and props.onClose() upon submit', () => {
    const wrapper = shallow(<WheelModal {...props} />);
    // Call modalAfterOpen to update state
    wrapper.instance().modalAfterOpen();
    wrapper.find(Button).at(1).simulate('click', {preventDefault: () => {}});
    expect(props.onSubmit.calledWith(wheel)).to.be.true;
    expect(props.onClose.calledOnce).to.be.true;
  });

  it('Should update participant state correctly when onChange is called', () => {
    const expectedWheel = Object.assign({}, wheel, {name: 'test_updated_name'});
    const wrapper = shallow(<WheelModal {...Object.assign({}, props)} />);
    wrapper.instance().modalAfterOpen();
    expect(wrapper.instance().state.isAdd).to.be.false;
    wrapper.find("[name='name']").simulate('change', {target: {name: 'name', value: 'test_updated_name'}});
    expect(wrapper.instance().state.wheel).to.deep.equal(expectedWheel);
  });
});