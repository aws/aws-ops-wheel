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
import {mountWithRoute, shallowWithStore} from '../globals';
import ConnectedParticipantTable, {ParticipantTable} from '../../src/components/participant_table/participant_table';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';
import * as H from 'history';


describe('ParticipantTable', function() {
  const testWheelId = 'wheel_id_0';

  // Props containing route data for mountWithRoute
  const props = {
    location: H.createLocation('/'),
    match: {
      params: {wheel_id: testWheelId},
      isExact: true,
      path: `/app/wheel/${testWheelId}`,
      url: 'localhost/'
    },
    history: H.createHashHistory(),
  };

  // Props for shallow mounting (normally set by react-redux-fetch)
  const shallowProps = {
    wheelFetch: {
      fulfilled: true,
      rejected: false,
      pending: false,
      value: shimData.wheels[0],
    },
    listParticipantsFetch: {
      fulfilled: true,
      rejected: false,
      pending: false,
      value: shimData.participants.filter((e) => e.wheel_id === shimData.wheels[0].id),
    },
    match: {
      params: {wheel_id: testWheelId},
    },
  };

  // sinon.sandbox lets us group these spies together and reset them after every test
  const sandbox = sinon.createSandbox();
  const dispatchProps = {
    dispatchWheelGet: sandbox.spy(),
    dispatchListParticipantsGet: sandbox.spy(),
    dispatchCreateParticipantPost: sandbox.spy(),
    dispatchUpdateParticipantPut: sandbox.spy(),
    dispatchDeleteParticipantDelete: sandbox.spy(),
    dispatchRigParticipantPost: sandbox.spy(),
    dispatchUnrigParticipantPost: sandbox.spy(),
    dispatchResetWheelPost: sandbox.spy(),
  };
  afterEach(() =>{
    sandbox.reset();
  });

  it('Should render before and after loading completely', (done) => {
    const wrapper = mountWithRoute(<ConnectedParticipantTable {...props} />);
    // The wheel table should be be loading when initially mounted
    expect(wrapper.html()).to.contain('Loading...');

    // After 50ms we should have retrieved wheels data from the nocks
    setTimeout(() => {
      expect(wrapper.html()).to.contain('participant_name_0');
      expect(wrapper.html()).to.contain('participant_name_3');
      done();
    }, 50);
  });

  it('Should set participantModalOpen to true when Add New Participant button is clicked', () => {

    const wrapper = shallowWithStore(<ParticipantTable {...Object.assign({}, props, shallowProps, dispatchProps)} />);
    // Force pending state so wheel state is updated
    wrapper.instance().setState({fetchPending: true});
    wrapper.instance().componentDidUpdate();
    wrapper.update();
    wrapper.find(Button).at(2).simulate('click');
    expect(wrapper.instance().state.participantModalOpen).to.be.true;
  });

  it('Should set resetModalOpen to true when Reset button is clicked', () => {

    const wrapper = shallowWithStore(<ParticipantTable {...Object.assign({}, props, shallowProps, dispatchProps)} />);
    // Force pending state so wheel state is updated
    wrapper.instance().setState({fetchPending: true});
    wrapper.instance().componentDidUpdate();
    wrapper.update();
    wrapper.find(Button).at(3).simulate('click');
    expect(wrapper.instance().state.resetModalOpen).to.be.true;
  });

  it('Should dispatch a post upon handleCreateParticipant, then update state properly on componentDidUpdate',
    () => {
    const postProps = {
      createParticipantFetch: {
        fulfilled: false,
        pending: false,
        rejected: false,
      }
    };
    const testParticipant = {
      id: 'test_id',
    };

    const wrapper = shallowWithStore(
      <ParticipantTable {...Object.assign({}, props, postProps, shallowProps, dispatchProps)} />);
    wrapper.instance().handleCreateParticipant(testParticipant);
    expect(dispatchProps.dispatchCreateParticipantPost.calledWith(testWheelId, testParticipant)).to.be.true;
    expect(wrapper.instance().state.createPending).to.be.true;

    wrapper.setProps({createParticipantFetch: {fulfilled: true}})
    wrapper.instance().componentDidUpdate();
    expect(wrapper.instance().state.createPending).to.be.false;
    expect(wrapper.instance().state.fetchPending).to.be.false;
  });

  it('Should dispatch a put upon handleUpdateParticipant, then update state properly on componentDidUpdate',
    () => {
      const postProps = {
        updateParticipantFetch: {
          fulfilled: false,
          pending: false,
          rejected: false,
        }
      };
      const testParticipant = {
        id: 'test_id',
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, postProps, shallowProps, dispatchProps)} />);
      wrapper.instance().handleUpdateParticipant(testParticipant);
      expect(dispatchProps.dispatchUpdateParticipantPut.calledWith(testWheelId, testParticipant)).to.be.true;
      expect(wrapper.instance().state.updatePending).to.be.true;

      wrapper.setProps({updateParticipantFetch: {fulfilled: true}})
      wrapper.instance().componentDidUpdate();
      expect(wrapper.instance().state.updatePending).to.be.false;
      expect(wrapper.instance().state.fetchPending).to.be.false;
    });

  it('Should dispatch a delete upon handleDeleteParticipant, then update state properly on componentDidUpdate',
    () => {
      const postProps = {
        deleteParticipantFetch: {
          fulfilled: false,
          pending: false,
          rejected: false,
        }
      };
      const testParticipant = {
        id: 'test_id',
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, postProps, shallowProps, dispatchProps)} />);
      wrapper.instance().handleDeleteParticipant(testParticipant);
      expect(dispatchProps.dispatchDeleteParticipantDelete.calledWith(testWheelId, testParticipant.id)).to.be.true;
      expect(wrapper.instance().state.deletePending).to.be.true;

      wrapper.setProps({deleteParticipantFetch: {fulfilled: true}})
      wrapper.instance().componentDidUpdate();
      expect(wrapper.instance().state.deletePending).to.be.false;
      expect(wrapper.instance().state.fetchPending).to.be.false;
    });

  it('Should dispatch a reset post on handleResetWheel, then update state properly on componentDidUpdate',
    () => {
      const postProps = {
        resetWheelFetch: {
          fulfilled: false,
          pending: false,
          rejected: false,
        }
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, postProps, shallowProps, dispatchProps)} />);
      wrapper.instance().handleResetWheel();
      expect(dispatchProps.dispatchResetWheelPost.calledWith(testWheelId)).to.be.true;
      expect(wrapper.instance().state.resetPending).to.be.true;

      wrapper.setProps({resetWheelFetch: {fulfilled: true}})
      wrapper.instance().componentDidUpdate();
      expect(wrapper.instance().state.resetPending).to.be.false;
      expect(wrapper.instance().state.fetchPending).to.be.false;
    });

  it('Should dispatch a rig post on handleRigParticipant, then update state properly on componentDidUpdate',
    () => {
      const testId = shallowProps.listParticipantsFetch.value[0].id;
      const testHidden = false;
      const postProps = {
        wheelFetch: {
          fulfilled: true,
          rejected: false,
          pending: false,
          value: Object.assign({}, shimData.wheels[0],
            {rigging: {participant_id: testId, hidden: testHidden}}),
        },
        resetWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const testParticipant = {
        id: testId,
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, shallowProps, postProps, dispatchProps)} />);
      wrapper.instance().handleRigParticipant(testParticipant);
      expect(dispatchProps.dispatchRigParticipantPost
        .calledWith(testWheelId, testParticipant.id, testHidden)).to.be.true;
      // We reset the wheel here to set fetchPending which causes rigId and hidden states to be set
      wrapper.instance().handleResetWheel();
      wrapper.instance().componentDidUpdate();
      expect(wrapper.instance().state.rigging.participant_id).to.equal(testId);
      // Re-rigging the same participant should result in no change
      wrapper.instance().handleRigParticipant(testParticipant);
      expect(dispatchProps.dispatchRigParticipantPost.calledOnce).to.be.true;
      expect(wrapper.instance().state.rigging.participant_id).to.equal(testId);
    });

  it('Should dispatch a rig post upon handleHiddenParticipant, then update state properly on componentDidUpdate',
    () => {
      const testId = shallowProps.listParticipantsFetch.value[0].id;
      const testHidden = false;
      const postProps = {
        wheelFetch: {
          fulfilled: true,
          rejected: false,
          pending: false,
          value: Object.assign({}, shimData.wheels[0],
            {rigging: {participant_id: testId, hidden: testHidden}}),
        },
        resetWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const testParticipant = {
        id: testId,
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, shallowProps, postProps, dispatchProps)} />);
      // We reset the wheel here to set fetchPending which causes rigId and hidden states to be set
      wrapper.instance().handleResetWheel();
      wrapper.instance().componentDidUpdate();
      wrapper.instance().handleHiddenRigParticipant(testParticipant);
      expect(dispatchProps.dispatchRigParticipantPost
        .calledWith(testWheelId, testParticipant.id, !testHidden)).to.be.true;
      expect(wrapper.instance().state.rigging.hidden).to.equal(!testHidden);
    });

  it('Should dispatch an unrig post upon unrigWheel and update rig and hidden states', () => {
      const testId = shallowProps.listParticipantsFetch.value[0].id;
      const testHidden = false;
      const postProps = {
        wheelFetch: {
          fulfilled: true,
          rejected: false,
          pending: false,
          value: Object.assign({}, shimData.wheels[0],
            {rigging: {participant_id: testId, hidden: testHidden}}),
        },
        resetWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const testParticipant = {
        id: testId,
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, shallowProps, postProps, dispatchProps)} />);
      // We reset the wheel here to set fetchPending which causes rigId and hidden states to be set
      wrapper.instance().handleResetWheel();
      wrapper.instance().componentDidUpdate();
      expect(wrapper.instance().state.rigging.participant_id).to.equal(testId);
      wrapper.instance().unrigWheel();
      expect(dispatchProps.dispatchUnrigParticipantPost .calledWith(testWheelId)).to.be.true;
      expect('participant_id' in wrapper.instance().state.rigging).to.be.false;
      expect('hidden' in wrapper.instance().state.rigging).to.be.false;
    });

  it('Should render an error message if the wheel could not be fetched', () => {
      const testProps = {
        wheelFetch: {
          fulfilled: false,
          rejected: true,
          pending: false,
        },
      };

      const wrapper = shallowWithStore(
        <ParticipantTable {...Object.assign({}, props, shallowProps, testProps, dispatchProps)} />);
      expect(wrapper.text()).to.contain('Wheel information could not be loaded');
    });

  it('Should render an error message if participants could not be fetched and the wheel is rigged', () => {
    const testProps = {
      listParticipantsFetch: {
        fulfilled: false,
        rejected: true,
        pending: false,
      },
    };

    const wrapper = shallowWithStore(
      <ParticipantTable {...Object.assign({}, props, shallowProps, testProps, dispatchProps)} />);
    wrapper.instance().setState({wheel: {}});
    wrapper.instance().setState({rigging: {participant_id: 'test_id', hidden: false}});
    wrapper.update();
    expect(wrapper.text()).to.contain('Participant information could not be loaded.');
  });

  it('Should render loading if participants are still fetching and wheel is rigged', () => {
    const testProps = {
      listParticipantsFetch: {
        fulfilled: false,
        rejected: false,
        pending: true,
      },
    };

    const wrapper = shallowWithStore(
      <ParticipantTable {...Object.assign({}, props, shallowProps, testProps, dispatchProps)} />);
    wrapper.instance().setState({wheel: {}});
    wrapper.instance().setState({rigging: {participant_id: 'test_id', hidden: false}});
    wrapper.update();
    expect(wrapper.text()).to.contain('Loading participant information...');
  });
});
