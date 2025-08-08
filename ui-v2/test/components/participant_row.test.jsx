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
import ParticipantRow from '../../src/components/participant_table/participant_row';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';
import {mount} from 'enzyme';


describe('ParticipantRow', function() {
  const sandbox = sinon.createSandbox();
  afterEach(() => {
    sandbox.reset();
  });

  const participants = shimData.participants.filter((e) => e.wheel_id === shimData.wheels[0].id);
  const participant = participants[0];

  const props = {
    participant: participant,
    rig: false,
    hidden: false,
    onEdit: sandbox.spy(),
    onDelete: sandbox.spy(),
    onRig: sandbox.spy(),
    onHidden: sandbox.spy(),
    participantList: participants,
  };

  it('Should render and display wheel name', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    expect(wrapper.html()).to.contain(participant.name);
  });

  it('Should toggle participationModalOpen state on click of Edit button', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    expect(wrapper.instance().state.participationModalOpen).to.be.false;
    wrapper.find(Button).at(0).simulate('click');
    expect(wrapper.instance().state.participationModalOpen).to.be.true;
  });

  it('Should toggle confirmationModalOpen state on click of delete button', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    expect(wrapper.instance().state.confirmationModalOpen).to.be.false;
    wrapper.find(Button).at(1).simulate('click');
    expect(wrapper.instance().state.confirmationModalOpen).to.be.true;
  });

  it('Should call handleRigParticipant() on click of rig radio button', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    wrapper.find("[type='radio']").simulate('change', {target: {checked: true}});
    expect(props.onRig.calledWith(participant)).to.be.true;
  });

  it('Should call handleHiddenRigParticipant() on click of hidden checkbox', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    wrapper.find("[type='checkbox']").simulate('change', {target: {checked: true}});
    expect(props.onHidden.calledWith(participant)).to.be.true;
  });

  it('Should call props.onEdit upon call to handleUpdateParticipant()', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    wrapper.instance().handleUpdateParticipant(participant);
    expect(props.onEdit.calledWith(participant)).to.be.true;
  });

  it('Should call props.onDelete upon call to handleDeleteParticipant()', () => {
    const wrapper = mount(<ParticipantRow {...props} />);
    wrapper.instance().handleDeleteParticipant();
    expect(props.onDelete.calledWith(participant)).to.be.true;
  });
});
