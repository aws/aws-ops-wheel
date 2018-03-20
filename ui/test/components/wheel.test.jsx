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
import {expect, assert} from 'chai';
import * as sinon from 'sinon';
import {mountWithRoute, shallowWithStore} from '../globals';
import ConnectedWheel, {Wheel} from '../../src/components/wheel';
import * as H from 'history';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';

describe('Wheel', function() {
  const wheelId = 'wheel_id_0';
  const participants = shimData.participants.filter((e) => e.wheel_id === shimData.wheels[0].id);

  // Wheel uses localStorage which doesn't exist in tests. Mock it
  // Open Question: do we want to test localStorage logic? If so, need to create a basic 
  // implementation and add tests
  if (!global.window.localStorage) {
    global.window.localStorage = {
      getItem() { return ''; },
      setItem() {}
    };
  }

  console.log('participants: ', participants);

  const props = {
    location: H.createLocation('/'),
    match: {
      params: {wheel_id: wheelId},
      isExact: true,
      path: `/wheel/${wheelId}`,
      url: 'localhost/'
    },
    history: H.createHashHistory(),
  };

  const shallowProps = {
    wheelFetch: {
      fulfilled: true,
      rejected: false,
      pending: false,
      value: shimData.wheels[0],
    },
    allParticipantsFetch: {
      fulfilled: true,
      rejected: false,
      pending: false,
      value: participants,
    },
    participantSuggestFetch: {
      fulfilled: true,
      rejected: false,
      pending: false,
      value: {participant_id: participants[1].id},
    },
    participantSelectFetch: {
      fulfilled: false,
      rejected: false,
      pending: false,
    },
    match: {
      params: {wheel_id: wheelId},
    },
  };

  const sandbox = sinon.sandbox.create();
  const dispatchProps = {
    dispatchWheelGet: sandbox.spy(),
    dispatchAllParticipantsGet: sandbox.spy(),
    dispatchParticipantSelectPost: sandbox.spy(),
    dispatchParticipantSuggestGet: sandbox.spy(),
  };
  afterEach(() => {
    sandbox.reset();
  });

  it('Should render before and after loading completely', (done) => {
    const wrapper = mountWithRoute(<ConnectedWheel {...props} />);
    // The wheel should be be loading when initially mounted
    expect(wrapper.html()).to.contain('Loading the Wheel and its Participants...');

    // After 50ms we should have retrieved wheel and participant data from the nocks
    setTimeout(() => {
      expect(wrapper.find('div').first().html()).to.contain('wheel_name_0');
      done();
    }, 50);
  });

  it('Should update state appropriately upon initial update with suggested participant', () => {
    const testSelectedParticipant = Object.assign({}, shallowProps.participantSuggestFetch.value, participants[1]);
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps)} />);
    // Let's strip out the drawing and animation stuff
    wrapper.instance().drawInitialWheel = sinon.spy();
    wrapper.instance().componentDidUpdate();
    wrapper.instance().spinTicker = {add: sinon.spy(), remove: sinon.spy(), stop: sinon.spy()};
    wrapper.instance().setState({isSpinning: true});
    wrapper.instance().componentDidUpdate();
    expect(wrapper.instance().state.wheel).to.equal(shallowProps.wheelFetch.value);
    expect(wrapper.instance().state.participants).to.equal(shallowProps.allParticipantsFetch.value);
    expect(wrapper.instance().state.fetching).to.be.false;
    expect(wrapper.instance().state.fetching).to.be.false;
    expect(wrapper.instance().drawInitialWheel.calledOnce).to.be.true;
    expect(wrapper.instance().state.selectedParticipant).to.deep.equal(testSelectedParticipant);
  });

  it('Should update state appropriately upon initial update with rigged suggested participant', () => {
    const testProps = {
      participantSuggestFetch: {
        fulfilled: true,
        rejected: false,
        pending: false,
        value: {
          participant_id: participants[1].id,
          rigged: true,
        },
      },
    }
    const testSelectedParticipant = Object.assign({}, testProps.participantSuggestFetch.value, participants[1]);
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    // Let's strip out the drawing and animation stuff
    wrapper.instance().drawInitialWheel = sinon.spy();
    wrapper.instance().componentDidUpdate();
    wrapper.instance().spinTicker = {add: sinon.spy(), remove: sinon.spy(), stop: sinon.spy()};
    wrapper.instance().setState({isSpinning: true});
    wrapper.instance().componentDidUpdate();
    expect(wrapper.instance().state.wheel).to.equal(shallowProps.wheelFetch.value);
    expect(wrapper.instance().state.participants).to.equal(shallowProps.allParticipantsFetch.value);
    expect(wrapper.instance().state.fetching).to.be.false;
    expect(wrapper.instance().state.fetching).to.be.false;
    expect(wrapper.instance().drawInitialWheel.calledOnce).to.be.true;
    expect(wrapper.instance().state.selectedParticipant).to.deep.equal(testSelectedParticipant);
  });

  it('Should update state appropriately and call dispatchParticipantSuggestGet when Spin is clicked', () => {
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps)} />);
    // Let's strip out the drawing and animation stuff
    wrapper.instance().drawInitialWheel = sinon.spy();
    wrapper.instance().componentDidUpdate();
    wrapper.find('#btnSpin').first().simulate('click');
    expect(wrapper.instance().state.isSpinning).to.be.true;
    expect(wrapper.instance().state.selectedParticipant).to.be.undefined;
    expect(dispatchProps.dispatchParticipantSuggestGet.calledWith(wheelId)).to.be.true;
    // Try to spin again; state should remain unchanged
    wrapper.instance().startSpinningWheel();
    expect(wrapper.instance().state.selectedParticipant).to.be.undefined;
    expect(dispatchProps.dispatchParticipantSuggestGet.calledWith(wheelId)).to.be.true;
  });

  it('Should set time fields and call drawWheel upon calls to spin()', () => {
    const testTime = 4;
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps)} />);
    // Let's strip out the drawing and animation stuff
    wrapper.instance().drawInitialWheel = sinon.spy();
    wrapper.instance().drawWheel = sinon.spy();
    wrapper.instance().componentDidUpdate();
    wrapper.instance().spinTicker = {add: sinon.spy(), remove: sinon.spy(), stop: sinon.spy()};
    wrapper.instance().setState({isSpinning: true});
    wrapper.instance().componentDidUpdate();
    wrapper.instance().spin(testTime);
    expect(wrapper.instance().currentAnimationTime).to.equal(testTime);
    expect(wrapper.instance().drawWheel.calledOnce).to.be.true;
    // 2nd spin with time increased by 16 results in a call to drawWheel and requestAnimationFrame
    wrapper.instance().spin(1);
    expect(wrapper.instance().drawWheel.calledTwice).to.be.true;
    expect(wrapper.instance().currentAnimationTime).to.equal(testTime + 1);
  });

  it('Should call appropriate methods and eventually spinTicker.remove upon calls to riggedSpin()', () => {
    const testTime = 16;
    const testProps = {
      participantSuggestFetch: {
        fulfilled: true,
        rejected: false,
        pending: false,
        value: {
          participant_id: participants[1].id,
          rigged: true,
        },
      },
    }
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    // Let's strip out the drawing and animation stuff
    wrapper.instance().drawInitialWheel = sinon.spy();
    wrapper.instance().drawWheel = sinon.spy();
    wrapper.instance().componentDidUpdate();
    wrapper.instance().spinTicker = {add: sinon.spy(), remove: sinon.spy(), stop: sinon.spy()};
    wrapper.instance().setState({isSpinning: true});
    wrapper.instance().componentDidUpdate();
    wrapper.instance().currentAnimationTime = 0;
    // First riggedSpin call should result in immediate exit due to not enough time elapsed
    wrapper.instance().riggedSpin(0);
    expect(wrapper.instance().lastClickTime).to.equal(0);
    // Second riggedSpin call should result in a call to drawWheel
    wrapper.instance().riggedSpin(50);
    expect(wrapper.instance().drawWheel.calledOnce).to.be.true;
    // Third riggedSpin call we add a ton of time so we can hit the base case
    // This will call spinTicker.remove, drawWheel, and stop spinning
    wrapper.instance().riggedSpin(1000);
    expect(wrapper.instance().spinTicker.remove.calledOnce).to.be.true;
    expect(wrapper.instance().drawWheel.calledTwice).to.be.true;
    expect(wrapper.instance().state.isSpinning).to.be.false;
    expect(wrapper.instance().state.targetAngle).to.equal(undefined);
    expect(wrapper.instance().currentAnimationTime).to.equal(undefined);
  });

  it('Should render loading message if wheel and participant fetches arent fulfilled', () => {
    const testProps = {
      wheelFetch: {
        fulfilled: true,
        rejected: false,
        pending: true,
        value: shimData.wheels[0],
      },
      allParticipantsFetch: {
        fulfilled: false,
        rejected: false,
        pending: true,
        value: participants,
      },
    };
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    expect(wrapper.html()).to.contain('Loading the Wheel and its Participants...');
  });

  it('Should render an error message if wheel fetch is rejected', () => {
    const testProps = {
      wheelFetch: {
        fulfilled: false,
        rejected: true,
        pending: false,
        value: shimData.wheels[0],
      },
    };
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    expect(wrapper.html()).to.contain('Error: Wheel or wheel participants could not be loaded!');
  });

  it('Should render an error message if wheel fetch is rejected', () => {
    const testProps = {
      participantSuggestFetch: {
        fulfilled: false,
        rejected: true,
        pending: false,
        value: participants,
      },
    };
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    expect(wrapper.html()).to.contain('Error: Participant Selection could not be loaded!');
  });

  it('Should call the appropriate functions and set state appropriately on call to openParticipantPage', () => {
    const testProps = {
      participantSuggestFetch: {
        fulfilled: false,
        rejected: true,
        pending: false,
        value: participants,
      },
    };
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    window.open = sinon.spy();
    wrapper.instance().setState({selectedParticipant: {wheel_id: 'test_wheel_id', id: 'test_id', url: 'test_url'}});
    wrapper.instance().openParticipantPage();
    expect(dispatchProps.dispatchParticipantSelectPost.calledWith('test_wheel_id', 'test_id')).to.be.true;
    expect(window.open.calledWith('test_url')).to.be.true;
  });

  it('Should not do anything on openParticipantPage if the wheel is still spinning', () => {
    const testProps = {
      participantSuggestFetch: {
        fulfilled: false,
        rejected: true,
        pending: false,
        value: participants,
      },
    };
    const wrapper = shallowWithStore(<Wheel {...Object.assign({}, props, shallowProps, dispatchProps, testProps)} />);
    window.open = sinon.spy();
    wrapper.instance().setState({isSpinning: true});
    wrapper.instance().openParticipantPage();
    expect(dispatchProps.dispatchParticipantSelectPost.called).to.be.false;
    expect(window.open.called).to.be.false;
  });
});
