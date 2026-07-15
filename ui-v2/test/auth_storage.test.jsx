/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

/*
 * Tests for the in-memory Cognito token store (stored-XSS hardening follow-up).
 *
 * The security goal: auth tokens must live only in this in-memory store, never
 * in localStorage, so a stored-XSS payload cannot exfiltrate them. These tests
 * assert the store behaves like the Web Storage subset amazon-cognito-identity-js
 * needs, that getStoredIdToken resolves both key styles, and -- critically --
 * that writing tokens through it never touches window.localStorage.
 */

import {expect} from 'chai';
import {authStorage, getStoredIdToken, clearStoredTokens} from '../src/auth_storage';

describe('auth_storage (in-memory token store)', function() {

  afterEach(() => {
    clearStoredTokens();
  });

  it('implements the Web Storage subset used by amazon-cognito-identity-js', () => {
    expect(authStorage.getItem('missing')).to.equal(null);
    authStorage.setItem('a', 'x');
    authStorage.setItem('b', 'y');
    expect(authStorage.getItem('a')).to.equal('x');
    expect(authStorage.length).to.equal(2);
    expect(authStorage.key(0)).to.equal('a');
    authStorage.removeItem('a');
    expect(authStorage.getItem('a')).to.equal(null);
    expect(authStorage.length).to.equal(1);
    authStorage.clear();
    expect(authStorage.length).to.equal(0);
    expect(authStorage.key(0)).to.equal(null);
  });

  it('coerces stored values to strings, like real Storage', () => {
    authStorage.setItem('n', 123);
    expect(authStorage.getItem('n')).to.equal('123');
  });

  it('getStoredIdToken returns the plain idToken key when present', () => {
    authStorage.setItem('idToken', 'JWT_PLAIN');
    expect(getStoredIdToken()).to.equal('JWT_PLAIN');
  });

  it('getStoredIdToken falls back to the CognitoIdentityServiceProvider key', () => {
    authStorage.setItem(
      'CognitoIdentityServiceProvider.abc123.alice.idToken', 'JWT_COGNITO');
    expect(getStoredIdToken()).to.equal('JWT_COGNITO');
  });

  it('getStoredIdToken returns null when no token is stored', () => {
    expect(getStoredIdToken()).to.equal(null);
  });

  it('clearStoredTokens empties the store', () => {
    authStorage.setItem('idToken', 'JWT');
    authStorage.setItem('CognitoIdentityServiceProvider.abc.bob.accessToken', 'A');
    clearStoredTokens();
    expect(getStoredIdToken()).to.equal(null);
    expect(authStorage.length).to.equal(0);
  });

  it('SECURITY: storing tokens must never write to window.localStorage', () => {
    // The whole point of the migration: an XSS payload reading localStorage must
    // find nothing. Simulate the pool/user writing session tokens through the
    // store and assert localStorage stays empty.
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.clear();
    }
    authStorage.setItem('idToken', 'JWT');
    authStorage.setItem('CognitoIdentityServiceProvider.abc.carol.idToken', 'JWT2');
    authStorage.setItem('CognitoIdentityServiceProvider.abc.carol.refreshToken', 'RT');

    if (typeof window !== 'undefined' && window.localStorage) {
      expect(window.localStorage.getItem('idToken')).to.equal(null);
      const leaked = Object.keys(window.localStorage).filter(k =>
        k.includes('CognitoIdentityServiceProvider') || k === 'idToken');
      expect(leaked).to.have.lengthOf(0);
    }
    // The token is still retrievable from the in-memory store for the app's use.
    expect(getStoredIdToken()).to.equal('JWT');
  });
});
