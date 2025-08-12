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
import UserTable from './user_table/user_table';
import Login from './login';
import NotFound from './notFound';
import Navigation from './navigation';
import connect, {container} from 'react-redux-fetch';
import {Route, Switch} from 'react-router-dom';
import '../styles.css';
import {CognitoUserPool} from 'amazon-cognito-identity-js';
import {BrowserRouter, Router} from 'react-router-dom';
import {apiURL, setAPIConfig} from '../util';
import { PermissionProvider } from './PermissionContext';

// Constants
const INITIAL_STATE = {
  cognitoUserPool: undefined,
  cognitoSession: undefined
};

const TOKEN_KEYS = {
  ID_TOKEN: 'idToken',
  ACCESS_TOKEN: 'accessToken',
  REFRESH_TOKEN: 'refreshToken'
};

const ROUTES = {
  APP_ROOT: '/app',
  USERS: '/app/users',
  WHEEL: '/app/wheel/:wheel_id',
  PARTICIPANTS: '/app/wheel/:wheel_id/participant'
};

const LOADING_MESSAGES = {
  INITIAL: 'Loading ...',
  CONFIG: 'Loading configuration...'
};

/**
 * Main Application component
 */
class App extends Component {
  constructor(props) {
    super(props);
    this.state = INITIAL_STATE;
  }

  componentDidMount() {
    this.props.dispatchConfigGet();
  }

  componentDidUpdate() {
    if (this.state.cognitoUserPool === undefined && this.props.configFetch.fulfilled) {
      // Set the API config for subsequent API calls
      setAPIConfig(this.props.configFetch.value);
      
      const cognitoUserPool = new CognitoUserPool({
        UserPoolId: this.props.configFetch.value.UserPoolId,
        ClientId: this.props.configFetch.value.ClientId,
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
        const idToken = session.getIdToken().getJwtToken();
        // Store token for both react-redux-fetch and direct API calls
        container.registerRequestHeader('Authorization', idToken);
        localStorage.setItem(TOKEN_KEYS.ID_TOKEN, idToken);
        localStorage.setItem(TOKEN_KEYS.ACCESS_TOKEN, session.getAccessToken().getJwtToken());
        localStorage.setItem(TOKEN_KEYS.REFRESH_TOKEN, session.getRefreshToken().getToken());
        app.setState({cognitoSession: session});
      })
    }
  }

  userLogout = () => {
    this.state.cognitoUserPool.getCurrentUser().signOut();
    // Clear stored tokens
    localStorage.removeItem(TOKEN_KEYS.ID_TOKEN);
    localStorage.removeItem(TOKEN_KEYS.ACCESS_TOKEN);
    localStorage.removeItem(TOKEN_KEYS.REFRESH_TOKEN);
    this.setState(INITIAL_STATE);
  }

  createUserPool = (config) => {
    return new CognitoUserPool({
      UserPoolId: config.UserPoolId,
      ClientId: config.ClientId,
    });
  }

  getChildProps = () => {
    const config = this.props.configFetch.value;
    return {
      userHasAuthenticated: this.refreshSession,
      userPool: this.createUserPool(config),
      userLogout: this.userLogout
    };
  }

  renderRoutes = () => {
    return (
      <Switch>
        <Route path={ROUTES.APP_ROOT} exact={true} component={WheelTable} />
        <Route path={ROUTES.USERS} exact={true} component={UserTable} />
        <Route path={ROUTES.WHEEL} exact={true} component={Wheel} />
        <Route path={ROUTES.PARTICIPANTS} exact={true} component={ParticipantTable} />
        <Route component={NotFound} />
      </Switch>
    );
  }

  handleClickCapture = () => {
    if(this.state.cognitoUserPool!== undefined){
      this.refreshSession()
    }else{
      this.componentDidUpdate()
    }
  }

  render() {
    if (!this.props.configFetch.fulfilled) {
      return <div>{LOADING_MESSAGES.INITIAL}</div>;
    }

    const childProps = this.getChildProps();

    if (this.state.cognitoSession !== undefined && this.state.cognitoSession.isValid()) {
      return (
        <BrowserRouter>
          <PermissionProvider>
            <div id="grandparent" onClickCapture={this.handleClickCapture}>
              <Navigation {...childProps} />
              {this.renderRoutes()}
            </div>
          </PermissionProvider>
        </BrowserRouter>
      );
    } else {
      return <Login {...childProps}/>;
    }
  }
}

export default connect([
  {
    resource: 'config',
    method: 'get',
    request: {url: '/app/config.json'},
  },
]) (App);
