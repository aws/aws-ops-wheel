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
import Login from '../../src/components/login';
import '../globals';
import {mount} from 'enzyme';
import {CognitoUserPool, CognitoUser} from "amazon-cognito-identity-js";
import {Button} from 'react-bootstrap';


describe('Login', function() {

  const sandbox = sinon.createSandbox();

  afterEach(() => {
    sandbox.reset();
  });

  const props = {
    userHasAuthenticated: sandbox.spy(),
    userPool: new CognitoUserPool({
      UserPoolId: 'test_user_pool_id',
      ClientId: 'test_client_id',
    }),
  };

  it('Should mount and render', () => {
    const wrapper = mount(<Login {...props}/>);
    expect(wrapper.html()).to.contain('You can manage Users using the User Pool in AWS Cognito.');
  });

  it('Should set state and call userHasAuthenticated upon onSuccess()', () => {
    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().setState({error: {message: 'test'}, passwordChangeAttributes: {}, isInFlight: true});
    wrapper.instance().onSuccess();
    expect(wrapper.instance().state.error).to.equal(undefined);
    expect(wrapper.instance().state.passwordChangeAttributes).to.equal(undefined);
    expect(wrapper.instance().state.isInFlight).to.be.false;
    expect(props.userHasAuthenticated.calledWith(true)).to.be.true;
  });

  it('Should set state upon onFailure()', () => {
    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().setState({isInFlight: true});
    wrapper.instance().onFailure();
    expect(wrapper.instance().state.isInFlight).to.be.false;
  });

  it('Should set state upon newPasswordRequired()', () => {
    const testUserAttribs = {
      email_verified: true,
      somethingElse: 'test',
    };

    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().setState({error: {}, password: 'test', isInFlight: true });
    wrapper.instance().newPasswordRequired(testUserAttribs);
    let expectedUserAttribs = JSON.parse(JSON.stringify(testUserAttribs));
    delete expectedUserAttribs.email_verified;
    expect(wrapper.instance().state.passwordChangeAttributes).to.deep.equal(expectedUserAttribs);
    expect(wrapper.instance().state.error).to.equal(undefined);
    expect(wrapper.instance().state.password).to.equal('');
    expect(wrapper.instance().state.isInFlight).to.be.false;
  });

  it('Should set state and call completeNewPasswordChallenge upon Login button submit with password not yet set',
    () => {
    const testPWChangeAttribs = {
      somethingElse: 'test',
    };
    const testUser = {
      completeNewPasswordChallenge: sinon.spy(),
    };

    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().setState(
      {
        passwordChangeAttributes: testPWChangeAttribs,
        user: testUser,
      });
    wrapper.find('[type="username"]').at(1).simulate('change', {target: {id: 'username', value: 'test_username'}});
    wrapper.find('[type="password"]').at(1).simulate('change', {target: {id: 'password', value: 'test_password'}});
    wrapper.find(Button).simulate('submit', {preventDefault: () => {}});
    expect(wrapper.instance().state.isInFlight).to.be.true;
    expect(testUser.completeNewPasswordChallenge.calledWith('test_password', testPWChangeAttribs, wrapper.instance()))
      .to.be.true;
  });

  it('Should set state upon handleChange()', () => {
    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().handleChange({target: {id: 'username', value: 'test_username'}});
    expect(wrapper.instance().state.username).to.equal('test_username');
  });

  it('Should set state appropriately on Login button submit with password already set', () => {
    const testUser = {
      completeNewPasswordChallenge: sinon.spy(),
    };
    const expectedUser = new CognitoUser({Username: 'test_username', Pool: props.userPool});

    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().setState({user: testUser});
    wrapper.find('[type="username"]').at(1).simulate('change', {target: {id: 'username', value: 'test_username'}});
    wrapper.find('[type="password"]').at(1).simulate('change', {target: {id: 'password', value: 'test_password'}});
    wrapper.find(Button).simulate('submit', {preventDefault: () => {}});
    expect(wrapper.instance().state.isInFlight).to.be.true;
    expect(wrapper.instance().state.user).to.deep.equal(expectedUser);
  });

  it('Should render error message if set', () => {
    const wrapper = mount(<Login {...props}/>);
    wrapper.instance().setState({error: {message: 'test_error_message'}});
    expect(wrapper.html()).to.contain('test_error_message');
  });
});