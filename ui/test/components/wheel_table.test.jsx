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
import ConnectedWheelTable, {WheelTable} from '../../src/components/wheel_table/wheel_table';
import '../globals';
import {shimData} from '../shim_data';
import {Button} from 'react-bootstrap';


describe('WheelTable', function() {
  const shallowProps = {
    wheelsFetch: {
      fulfilled: true,
      rejected: false,
      pending: false,
      value: {Items: shimData.wheels},
    },
  };

  const sandbox = sinon.sandbox.create();
  const dispatchProps = {
    dispatchWheelsGet: sandbox.spy(),
    dispatchCreateWheelPost: sandbox.spy(),
    dispatchUpdateWheelPut: sandbox.spy(),
    dispatchDeleteWheelDelete: sandbox.spy(),
  };
  afterEach(() => {
    sandbox.reset();
  });

  it('Should render before and after loading completely', (done) => {
    const wrapper = mountWithRoute(<ConnectedWheelTable />);
    // The wheel table should be be loading when initially mounted
    expect(wrapper.find('div').html()).to.contain('Loading...');

    // After 50ms we should have retrieved wheels data from the nocks
    setTimeout(() => {
      expect(wrapper.find('div').html()).to.contain('wheel_name_0');
      expect(wrapper.find('div').html()).to.contain('wheel_name_1');
      done();
    }, 50);
  });

  it('Should set isWheelModalOpen to true when Add New Wheel button is clicked', () => {

    const wrapper = shallowWithStore(<WheelTable {...Object.assign({}, shallowProps, dispatchProps)} />);
    expect(wrapper.find('.pageRoot').html()).to.contain('wheel_name_1');
    wrapper.find(Button).simulate('click');
    expect(wrapper.instance().state.isWheelModalOpen).to.be.true;
  });

  it('Should dispatch a post upon handleWheelAdd, then update state properly on componentDidUpdate',
    () => {
      const testCreateWheel = {
        name: 'test_create_wheel',
      }
      const postProps = {
        createWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const wrapper = shallowWithStore(
        <WheelTable {...Object.assign({}, postProps, shallowProps, dispatchProps)} />);
      expect(wrapper.html()).to.contain('wheel_name_0');
      wrapper.instance().handleWheelAdd(testCreateWheel);
      expect(dispatchProps.dispatchCreateWheelPost.calledWith(testCreateWheel)).to.be.true;
      expect(wrapper.instance().state.create).to.be.true;
      wrapper.instance().componentDidUpdate();
      expect(dispatchProps.dispatchWheelsGet.calledTwice).to.be.true;
      expect(wrapper.instance().state.create).to.be.false;
    });

  it('Should dispatch a post upon handleWheelAdd, then update state properly on componentDidUpdate',
    () => {
      const testWheel = {
        name: 'test_create_wheel',
      }
      const postProps = {
        createWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const wrapper = shallowWithStore(
        <WheelTable {...Object.assign({}, postProps, shallowProps, dispatchProps)} />);
      expect(wrapper.html()).to.contain('wheel_name_0');
      wrapper.instance().handleWheelAdd(testWheel);
      expect(dispatchProps.dispatchCreateWheelPost.calledWith(testWheel)).to.be.true;
      expect(wrapper.instance().state.create).to.be.true;
      wrapper.instance().componentDidUpdate();
      expect(dispatchProps.dispatchWheelsGet.calledTwice).to.be.true;
      expect(wrapper.instance().state.create).to.be.false;
    });

  it('Should dispatch a put upon handleWheelEdit, then update state properly on componentDidUpdate',
    () => {
      const testWheel = {
        name: 'test_edit_wheel',
        id: shallowProps.wheelsFetch.value.Items[0].id,
      }
      const postProps = {
        updateWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const wrapper = shallowWithStore(
        <WheelTable {...Object.assign({}, postProps, shallowProps, dispatchProps)} />);
      expect(wrapper.html()).to.contain('wheel_name_0');
      wrapper.instance().handleWheelEdit(testWheel);
      expect(dispatchProps.dispatchUpdateWheelPut.calledWith(testWheel)).to.be.true;
      expect(wrapper.instance().state.edit).to.be.true;
      wrapper.instance().componentDidUpdate();
      expect(dispatchProps.dispatchWheelsGet.calledTwice).to.be.true;
      expect(wrapper.instance().state.edit).to.be.false;
    });

  it('Should dispatch a delete upon handleWheelDelete, then update state properly on componentDidUpdate',
    () => {
      const testWheel = {
        name: 'test_delete_wheel',
        id: shallowProps.wheelsFetch.value.Items[0].id,
      }
      const postProps = {
        deleteWheelFetch: {
          fulfilled: true,
          pending: false,
          rejected: false,
        }
      };

      const wrapper = shallowWithStore(
        <WheelTable {...Object.assign({}, postProps, shallowProps, dispatchProps)} />);
      expect(wrapper.html()).to.contain('wheel_name_0');
      wrapper.instance().handleWheelDelete(testWheel);
      expect(dispatchProps.dispatchDeleteWheelDelete.calledWith(testWheel.id)).to.be.true;
      expect(wrapper.instance().state.delete).to.be.true;
      wrapper.instance().componentDidUpdate();
      expect(dispatchProps.dispatchWheelsGet.calledTwice).to.be.true;
      expect(wrapper.instance().state.delete).to.be.false;
    });

  it('Should render an error message if wheels get fails', () => {
      const postProps = {
        wheelsFetch: {
          fulfilled: false,
          pending: false,
          rejected: true,
        }
      };

      const wrapper = shallowWithStore(
        <WheelTable {...Object.assign({}, shallowProps, dispatchProps, postProps)} />);
      expect(wrapper.html()).to.contain('Oops... Could not fetch the wheels data!');
    });
});