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

let nock = require('nock');
import {shimData} from './shim_data';
import {createStore, applyMiddleware, combineReducers, compose} from 'redux';
import {middleware as fetchMiddleware, reducer as repository} from 'react-redux-fetch';
import * as H from 'history';
import {Provider} from 'react-redux';
import {Router} from 'react-router';
import {mount, shallow} from 'enzyme';

process.env.NODE_ENV = 'test'

// Setup Enzyme 3 for react16
import { configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
configure({ adapter: new Adapter() });

// Deep copy the shim data
let localShimData = JSON.parse(JSON.stringify(shimData));

// Setup default nocks with shim data
nock('http://localhost')
  .persist().get('/app/api/wheel')
  .reply(200, {
    Count: localShimData.wheels.length,
    Items: shimData.wheels,
    }
  );

for (let wheel of localShimData.wheels) {

  let wheelParticipants = localShimData.participants.filter(e => e.wheel_id === wheel.id);

  nock('http://localhost')
    .persist().get(`/app/api/wheel/${wheel.id}`)
    .reply(200, wheel);
  nock('http://localhost')
    .persist().get(`/app/api/wheel/${wheel.id}/participant`)
    .reply(200, wheelParticipants);
  nock('http://localhost')
    .persist().get(`/app/api/wheel/${wheel.id}/participant/suggest`)
    .reply(200, { participant_id: wheelParticipants[0].id });
}

nock('http://localhost')
  .persist().get('/app/api/config')
  .reply(200, {USER_POOL_ID: 'test_pool_id', APP_CLIENT_ID: 'test_client_id'}
  );

// Mounting wrappers
export const createMockStore = () => {
  return createStore(combineReducers({repository}), undefined, applyMiddleware(fetchMiddleware));
};

export function mountWithRoute(component: any, router: any = {
  history: H.createBrowserHistory(),
    route: {
    location: H.createLocation('/'),
      match: {
      params: {},
      isExact: true,
        path: '/',
        url: 'localhost/'
    }
  }
}) {
  const childContextTypes = Object.assign(Router.childContextTypes, Provider.childContextTypes);
  const store = createMockStore();
  return (
    mount(component, {
      context: {store, router},
      childContextTypes: childContextTypes,
      attachTo: document.getElementById('app')
    })
  );
}

export function shallowWithStore(component: any) {
  const store = createMockStore();
  return shallow(component, {context: {store}});
}