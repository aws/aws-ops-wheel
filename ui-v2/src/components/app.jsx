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

import React, {Component, Suspense, lazy} from 'react';
import PropTypes from 'prop-types';
import Login from './login';
import ForgotPassword from './forgot_password';
import ResetPassword from './reset_password';
import WheelGroupCreation from './wheel_group_creation';
import NotFound from './notFound';
import Navigation from './navigation';
import DeploymentAdminNavigation from './deployment_admin_navigation';
import connect, {container} from 'react-redux-fetch';
import {Route, Switch, Redirect} from 'react-router-dom';
import '../styles.css';
import {CognitoUserPool} from 'amazon-cognito-identity-js';
import {BrowserRouter} from 'react-router-dom';
import {setAPIConfig} from '../util';
import { PermissionProvider, usePermissions } from './PermissionContext';

// Lazy load heavy components for better performance
const WheelTable = lazy(() => import('./wheel_table/wheel_table'));
const Wheel = lazy(() => import('./wheel'));
const ParticipantTable = lazy(() => import('./participant_table/participant_table'));
const UserTable = lazy(() => import('./user_table/user_table'));
const WheelGroupsTable = lazy(() => import('./wheel_groups_table/wheel_groups_table'));

// Constants
const INITIAL_STATE = {
  cognitoUserPool: undefined,
  cognitoSession: undefined,
  showTenantCreation: false
};

const TOKEN_KEYS = {
  ID_TOKEN: 'idToken',
  ACCESS_TOKEN: 'accessToken',
  REFRESH_TOKEN: 'refreshToken'
};

const ROUTES = {
  APP_ROOT: '/app',
  WHEELS: '/app/wheels',
  WHEEL_GROUPS: '/app/wheelgroups',
  USERS: '/app/users',
  WHEEL: '/app/wheel/:wheel_id',
  PARTICIPANTS: '/app/wheel/:wheel_id/participant',
  CREATE_WHEEL_GROUP: '/app/createtenant'
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
          return;
        }
        const idToken = session.getIdToken().getJwtToken();
        
        // Only update state if the session actually changed to prevent unnecessary re-renders
        const currentIdToken = app.state.cognitoSession?.getIdToken()?.getJwtToken();
        const currentStoredToken = localStorage.getItem(TOKEN_KEYS.ID_TOKEN);
        
        if (currentIdToken !== idToken) {
          // Store token for both react-redux-fetch and direct API calls
          container.registerRequestHeader('Authorization', idToken);
          
          // Only update localStorage if the token is actually different to prevent storage events
          if (currentStoredToken !== idToken) {
            localStorage.setItem(TOKEN_KEYS.ID_TOKEN, idToken);
            localStorage.setItem(TOKEN_KEYS.ACCESS_TOKEN, session.getAccessToken().getJwtToken());
            localStorage.setItem(TOKEN_KEYS.REFRESH_TOKEN, session.getRefreshToken().getToken());
          }
          
          app.setState({cognitoSession: session});
        }
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
      userLogout: this.userLogout,
      onCreateTenant: this.handleShowTenantCreation
    };
  }

  handleShowTenantCreation = () => {
    this.setState({ showTenantCreation: true });
  }

  handleBackToLogin = () => {
    this.setState({ showTenantCreation: false });
  }

  handleWheelGroupCreated = (wheelGroupData, credentials) => {
    // After wheel group creation, go back to login page
    this.setState({ showTenantCreation: false });
    
  }

  renderRoutes = () => {
    return (
      <Suspense fallback={<div style={{padding: '20px', textAlign: 'center'}}>Loading...</div>}>
        <Switch>
          <Route path="/" exact={true} render={() => <Redirect to={ROUTES.WHEELS} />} />
          <Route path={ROUTES.APP_ROOT} exact={true} render={() => <Redirect to={ROUTES.WHEELS} />} />
          <Route path={ROUTES.WHEELS} exact={true} component={WheelTable} />
          <Route path={ROUTES.USERS} exact={true} component={UserTable} />
          <Route path={ROUTES.WHEEL} exact={true} component={Wheel} />
          <Route path={ROUTES.PARTICIPANTS} exact={true} component={ParticipantTable} />
          <Route component={NotFound} />
        </Switch>
      </Suspense>
    );
  }

  renderUnauthenticatedRoutes = () => {
    return (
      <Switch>
        <Route path={ROUTES.CREATE_WHEEL_GROUP} exact={true} render={() => (
          <WheelGroupCreation 
            onWheelGroupCreated={this.handleWheelGroupCreated}
            onBackToLogin={this.handleBackToLogin}
          />
        )} />
        <Route path="/forgot-password" exact={true} render={() => (
          <ForgotPassword {...this.getChildProps()} />
        )} />
        <Route path="/reset-password" exact={true} render={() => (
          <ResetPassword {...this.getChildProps()} />
        )} />
        <Route path="/" render={() => <Login {...this.getChildProps()} />} />
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
            <AuthenticatedApp
              childProps={childProps}
              handleClickCapture={this.handleClickCapture}
            />
          </PermissionProvider>
        </BrowserRouter>
      );
    } else {
      return (
        <BrowserRouter>
          {this.renderUnauthenticatedRoutes()}
        </BrowserRouter>
      );
    }
  }
}

// Functional component that uses hooks to access permissions
const AuthenticatedApp = React.memo(({ childProps, handleClickCapture }) => {
  const { isRole, loading } = usePermissions();

  // Track when permissions have been loaded to prevent redirect loops
  const [permissionsStable, setPermissionsStable] = React.useState(false);
  const [initialLoad, setInitialLoad] = React.useState(true);

  React.useEffect(() => {
    if (!loading && initialLoad) {
      // Add a small delay to ensure permissions are fully stable
      const timer = setTimeout(() => {
        setPermissionsStable(true);
        setInitialLoad(false);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [loading, initialLoad]);

  // Show loading until permissions are stable
  if (!permissionsStable) {
    return <div style={{padding: '20px', textAlign: 'center'}}>Loading permissions...</div>;
  }

  const isDeploymentAdmin = isRole('DEPLOYMENT_ADMIN');

  return (
    <div id="grandparent" onClickCapture={handleClickCapture}>
      {isDeploymentAdmin ? (
        <DeploymentAdminNavigation {...childProps} />
      ) : (
        <Navigation {...childProps} />
      )}
      <Suspense fallback={<div style={{padding: '20px', textAlign: 'center'}}>Loading...</div>}>
        <Switch>
          {/* Root redirects - only after permissions are stable */}
          <Route path="/" exact={true} render={() => 
            <Redirect to={isDeploymentAdmin ? ROUTES.WHEEL_GROUPS : ROUTES.WHEELS} />
          } />
          <Route path={ROUTES.APP_ROOT} exact={true} render={() => 
            <Redirect to={isDeploymentAdmin ? ROUTES.WHEEL_GROUPS : ROUTES.WHEELS} />
          } />
          
          {/* Deployment Admin Routes - no cross-redirects */}
          <Route path={ROUTES.WHEEL_GROUPS} exact={true} render={() => 
            isDeploymentAdmin ? <WheelGroupsTable /> : <div>Access denied</div>
          } />
          
          {/* Regular User Routes - no cross-redirects */}
          <Route path={ROUTES.WHEELS} exact={true} render={(props) => 
            !isDeploymentAdmin ? <WheelTable {...props} /> : <div>Access denied</div>
          } />
          <Route path={ROUTES.USERS} exact={true} render={(props) => 
            !isDeploymentAdmin ? <UserTable {...props} /> : <div>Access denied</div>
          } />
          <Route path={ROUTES.WHEEL} exact={true} render={(props) => 
            !isDeploymentAdmin ? <Wheel {...props} /> : <div>Access denied</div>
          } />
          <Route path={ROUTES.PARTICIPANTS} exact={true} render={(props) => 
            !isDeploymentAdmin ? <ParticipantTable {...props} /> : <div>Access denied</div>
          } />
          
          <Route component={NotFound} />
        </Switch>
      </Suspense>
    </div>
  );
});

export default connect([
  {
    resource: 'config',
    method: 'get',
    request: {url: '/app/config.json'},
  },
]) (App);
