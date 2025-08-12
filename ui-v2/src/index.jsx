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

// Global window object type declaration removed - handled as JavaScript
import React from 'react';
import {render} from 'react-dom';
import {Provider} from 'react-redux';
import {createLogger} from 'redux-logger';
import {createStore, applyMiddleware, combineReducers, compose} from 'redux';
import {middleware as fetchMiddleware, reducer as repository} from 'react-redux-fetch';
import 'bootstrap/dist/css/bootstrap.css';
import 'font-awesome/css/font-awesome.css';

import App from './components/app';


/*
 Integration of Redux Store Chrome debugger:
 https://github.com/zalmoxisus/redux-devtools-extension
 */
const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;

const middleWare = composeEnhancers(applyMiddleware(
  fetchMiddleware, // lets us dispatch() functions
  createLogger({}) // neat middleware that logs actions and the state before and after (super useful for debugging)
));

const store = createStore(combineReducers({repository}), undefined, middleWare);

render(
  <Provider store={store}>
    <App />
  </Provider>,
  document.getElementById('app')
);
