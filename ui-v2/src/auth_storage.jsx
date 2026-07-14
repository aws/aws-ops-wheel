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
 * In-memory token store for Cognito auth (stored-XSS hardening follow-up).
 *
 * WHY: Cognito id/access/refresh tokens previously lived in localStorage, which
 * is readable by any script in the origin. Combined with an XSS sink that was a
 * credential-theft -> account-takeover chain. Keeping the tokens in a JS closure
 * (this module's `store`) instead of localStorage removes the exfiltration
 * surface: there is nothing for `localStorage.getItem('idToken')` (or a scan of
 * `CognitoIdentityServiceProvider.*` keys) to read.
 *
 * TRADE-OFF: in-memory storage does not survive a full page reload or a new tab,
 * so the user re-authenticates after a hard refresh. This is intentional. The
 * only way to keep cross-reload persistence while remaining unreadable by JS is
 * HttpOnly cookies, which requires backend/API-Gateway-authorizer changes and is
 * out of scope for this frontend change.
 *
 * This class implements the subset of the Web Storage API that
 * amazon-cognito-identity-js requires, so it can be passed as the `Storage`
 * option to CognitoUserPool / CognitoUser.
 */
class InMemoryStorage {
  constructor() {
    this.store = {};
  }

  setItem(key, value) {
    this.store[key] = String(value);
  }

  getItem(key) {
    return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null;
  }

  removeItem(key) {
    delete this.store[key];
  }

  clear() {
    this.store = {};
  }

  get length() {
    return Object.keys(this.store).length;
  }

  key(index) {
    const keys = Object.keys(this.store);
    return index >= 0 && index < keys.length ? keys[index] : null;
  }

  /** Return the first stored key matching the predicate, or null. */
  findKey(predicate) {
    return Object.keys(this.store).find(predicate) || null;
  }
}

// Single shared instance: the pool, every CognitoUser, and all token readers
// must see the same store.
export const authStorage = new InMemoryStorage();

/**
 * Read the current Cognito ID token (JWT) from the in-memory store.
 * amazon-cognito-identity-js persists it under a
 * `CognitoIdentityServiceProvider.<clientId>.<user>.idToken` key; older code
 * also wrote a plain `idToken` key, which we still honour for compatibility.
 *
 * @returns {string|null} the raw JWT, or null if not authenticated.
 */
export const getStoredIdToken = () => {
  const direct = authStorage.getItem('idToken');
  if (direct) {
    return direct;
  }
  const key = authStorage.findKey(k =>
    k.includes('CognitoIdentityServiceProvider') && k.endsWith('.idToken'));
  return key ? authStorage.getItem(key) : null;
};

/** Clear all auth tokens (used on logout / auth failure). */
export const clearStoredTokens = () => {
  authStorage.clear();
};
