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
import Navigation from '../../src/components/navigation';
import {mountWithRoute} from '../globals';
import '../globals';

describe('Navigation', function() {

  const sandbox = sinon.createSandbox();

  afterEach(() => {
    sandbox.reset();
  });

  const userPoolStub = sandbox.stub();
  const currentUserStub = sandbox.stub();
  userPoolStub.returns({getUsername: currentUserStub});
  currentUserStub.returns('test_user');

  const props = {
    userPool: {
      getCurrentUser: userPoolStub,
    },
    userLogout: sandbox.spy(),
  };

  it('Should mount and render', () => {
    const wrapper = mountWithRoute(<Navigation {...props}/>);
    expect(wrapper.html()).to.contain('test_user');
  });
});