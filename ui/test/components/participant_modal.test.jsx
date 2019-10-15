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
import ParticipantModal from '../../src/components/participant_table/participant_modal';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';
import {mount, shallow} from 'enzyme';


describe('ParticipantModal', function() {
  // sinon.sandbox lets us group these spies together and reset them after every test
  const sandbox = sinon.createSandbox();
  afterEach(() =>{
    sandbox.reset();
  });

  const participants = shimData.participants.filter((e) => e.wheel_id === shimData.wheels[0].id);

  const props = {
    isOpen: true,
    onSubmit: sandbox.spy(),
    onClose: sandbox.spy(),
    participant: participants[0],
    participantList: participants,
  };

  const defaultParticipant = {
    id: '',
    name: '',
    url: '',
    weight: 1
  };

  it('Should mount and render with modal open in edit mode', () => {
    const wrapper = mount(<ParticipantModal {...props} />);
    expect(wrapper.instance().state.isAdd).to.be.false;
    expect(wrapper.instance().state.participant).to.deep.equal(participants[0]);
  });

  it('Should mount and render with modal open in add mode', () => {
    const wrapper = mount(<ParticipantModal {...Object.assign({}, props, {participant: undefined})} />);
    expect(wrapper.instance().state.isAdd).to.be.true;
    expect(wrapper.instance().state.participant).to.deep.equal(defaultParticipant);
  });

  it('Should call props.onSubmit() and props.onClose() upon submit', () => {
    const wrapper = shallow(<ParticipantModal {...props} />);
    // Call modalAfterOpen to update state
    wrapper.instance().modalAfterOpen();
    wrapper.find(Button).at(1).simulate('click', {preventDefault: () => {}});
    expect(props.onSubmit.calledWith(participants[0])).to.be.true;
    expect(props.onClose.calledOnce).to.be.true;
  });

  it('Should generate errors for name and url on call to getErrors', () => {
    const wrapper = shallow(<ParticipantModal {...Object.assign({}, props, {participant: undefined})} />);
    wrapper.instance().modalAfterOpen();
    expect(wrapper.instance().state.isAdd).to.be.true;
    let errors = wrapper.instance().getErrors().map((e) => e.props.children);
    expect(errors[0]).to.equal('Name can\'t be blank');
    expect(errors[1]).to.equal('Url can\'t be blank');
    expect(errors[2]).to.equal('Url is not a valid url');
  });

  it('Should call generate error for duplicate name on call to getErrors', () => {
    const testParticipant = Object.assign({}, participants[0], {id: 'test_id'});
    const wrapper = shallow(<ParticipantModal {...Object.assign({}, props, {participant: undefined})} />);
    wrapper.instance().modalAfterOpen();
    expect(wrapper.instance().state.isAdd).to.be.true;
    wrapper.instance().state.participant = testParticipant;
    let errors = wrapper.instance().getErrors().map((e) => e.props.children);
    expect(errors[0]).to.equal('Name is already taken');
  });

  it('Should update participant state correctly when onChange is called', () => {
    const expectedParticipant = Object.assign({}, participants[0], {name: 'test_updated_name', url: 'http://testupdatedurl.com'});
    const wrapper = shallow(<ParticipantModal {...Object.assign({}, props)} />);
    wrapper.instance().modalAfterOpen();
    expect(wrapper.instance().state.isAdd).to.be.false;
    wrapper.find("[name='name']").simulate('change', {target: {name: 'name', value: 'test_updated_name'}});
    wrapper.find("[name='url']").simulate('change', {target: {name: 'url', value: 'http://testupdatedurl.com'}});
    expect(wrapper.instance().state.participant).to.deep.equal(expectedParticipant);
  });
});