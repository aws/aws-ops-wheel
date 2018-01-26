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

import React, {PropTypes, Component} from 'react';
import WheelTable from './wheel_table/wheel_table';
import Wheel from './wheel';
import ParticipantTable from './participant_table/participant_table';
import Login from './login';
import NotFound from './notFound';
import Navigation from './navigation';
import connect, {container} from 'react-redux-fetch';
import {Route, Switch} from 'react-router-dom';
import '../styles.css';
import {CognitoUserPool} from 'amazon-cognito-identity-js';
import {BrowserRouter, Router} from 'react-router-dom';
import {apiURL} from '../util';

export interface AppProps {
  dispatchConfigGet: PropTypes.func,
  configFetch: PropTypes.object,
}
export interface AppState {
  cognitoUserPool: Object | undefined,
  cognitoSession: Object | undefined,
}

/**
 * Main Application component
 */
class App extends Component<AppProps, AppState> {
  constructor(props) {
    super(props);
    this.state = {
      cognitoUserPool: undefined,
      cognitoSession: undefined
    };
  }

  componentDidMount() {
    this.props.dispatchConfigGet();
  }

  componentDidUpdate() {
    if (this.state.cognitoUserPool === undefined && this.props.configFetch.fulfilled) {
      const cognitoUserPool = new CognitoUserPool({
        UserPoolId: this.props.configFetch.value.USER_POOL_ID,
        ClientId: this.props.configFetch.value.APP_CLIENT_ID,
      })
      this.setState({cognitoUserPool}, this.refreshSession);
    }
  }

  refreshSession = () => {
    const currentUser = this.state.cognitoUserPool.getCurrentUser()
    if (currentUser !== null) {
      const app = this;  // Necessary because of 'this' getting overridden in the callback
      currentUser.getSession(function(err, session) {
        if (err) {
          console.error(err);
          return;
        }
        container.registerRequestHeader('Authorization', session.getIdToken().getJwtToken());
        app.setState({cognitoSession: session});
      })
    }
  }

  userLogout = () => {
    this.state.cognitoUserPool.getCurrentUser().signOut();
    this.setState({cognitoUserPool: undefined, cognitoSession: undefined});
  }

  render() {
    if (!this.props.configFetch.fulfilled) {
      return (<div>Loading ...</div>);
    }

    const childProps = {
      userHasAuthenticated: this.refreshSession,
      userPool: new CognitoUserPool({
        UserPoolId: this.props.configFetch.value.USER_POOL_ID,
        ClientId: this.props.configFetch.value.APP_CLIENT_ID,
      }),
      userLogout: this.userLogout
    };

    if (this.state.cognitoSession !== undefined && this.state.cognitoSession.isValid()) {
      return (
          <BrowserRouter>
            <div>
              <Navigation {...childProps} />
              <Switch>
                <Route path='/' exact={true} component={WheelTable} />
                <Route path='/wheel/:wheel_id' exact={true} component={Wheel} />
                <Route path='/wheel/:wheel_id/participant' exact={true} component={ParticipantTable} />
                <Route component={NotFound} />
              </Switch>
            </div>
          </BrowserRouter>
      )
    } else {
      return <Login {...childProps}/>;
    }
  }
}

export default connect([
  {
    resource: 'config',
    method: 'get',
    request: {url: apiURL('config')},
  },
]) (App);
