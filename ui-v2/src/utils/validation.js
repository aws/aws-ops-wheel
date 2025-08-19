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

// Centralized Form Validation Rules and Utilities

// Validation Rule Constants
export const VALIDATION_RULES = {
  USERNAME: {
    MIN_LENGTH: 1,
    MAX_LENGTH: 50,
    PATTERN: /^[a-zA-Z0-9._-]+$/,
    REQUIRED: true
  },
  PASSWORD: {
    MIN_LENGTH: 6,
    MAX_LENGTH: 128,
    PATTERN: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]/,
    REQUIRE_SPECIAL_CHARS: false, // Set to true for stricter validation
    REQUIRED: true
  },
  EMAIL: {
    PATTERN: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    MAX_LENGTH: 254,
    REQUIRED: true
  },
  WHEEL_NAME: {
    MIN_LENGTH: 1,
    MAX_LENGTH: 100,
    PATTERN: /^[a-zA-Z0-9\s._-]+$/,
    REQUIRED: true
  },
  PARTICIPANT_NAME: {
    MIN_LENGTH: 1,
    MAX_LENGTH: 100,
    PATTERN: /^[^\r\n\t]+$/,
    REQUIRED: true
  },
  PARTICIPANT_URL: {
    PATTERN: /^https?:\/\/[^\s]+$/,
    MAX_LENGTH: 500,
    REQUIRED: false
  },
  TENANT_NAME: {
    MIN_LENGTH: 1,
    MAX_LENGTH: 100,
    PATTERN: /^[a-zA-Z0-9\s._-]+$/,
    REQUIRED: true
  },
  DESCRIPTION: {
    MIN_LENGTH: 0,
    MAX_LENGTH: 1000,
    REQUIRED: false
  }
};

// Validation Error Messages
export const VALIDATION_MESSAGES = {
  REQUIRED: 'This field is required',
  MIN_LENGTH: (field, min) => `${field} must be at least ${min} characters long`,
  MAX_LENGTH: (field, max) => `${field} must be no more than ${max} characters long`,
  INVALID_FORMAT: (field) => `${field} has an invalid format`,
  INVALID_EMAIL: 'Please enter a valid email address',
  INVALID_URL: 'Please enter a valid URL (must start with http:// or https://)',
  PASSWORD_TOO_WEAK: 'Password must contain at least one uppercase letter, one lowercase letter, and one number',
  USERNAME_INVALID_CHARS: 'Username can only contain letters, numbers, dots, underscores, and hyphens',
  WHEEL_NAME_INVALID_CHARS: 'Wheel name can only contain letters, numbers, spaces, dots, underscores, and hyphens',
  PARTICIPANT_NAME_INVALID_CHARS: 'Participant name cannot contain line breaks or tabs',
  TENANT_NAME_INVALID_CHARS: 'Tenant name can only contain letters, numbers, spaces, dots, underscores, and hyphens'
};

// Field Display Names
export const FIELD_NAMES = {
  USERNAME: 'Username',
  PASSWORD: 'Password',
  EMAIL: 'Email',
  WHEEL_NAME: 'Wheel Name',
  PARTICIPANT_NAME: 'Participant Name',
  PARTICIPANT_URL: 'Participant URL',
  TENANT_NAME: 'Tenant Name',
  DESCRIPTION: 'Description'
};

// Validation Result Structure
export class ValidationResult {
  constructor(isValid = true, errors = []) {
    this.isValid = isValid;
    this.errors = errors;
  }

  addError(error) {
    this.errors.push(error);
    this.isValid = false;
  }

  hasErrors() {
    return this.errors.length > 0;
  }

  getFirstError() {
    return this.errors.length > 0 ? this.errors[0] : null;
  }
}

// Individual Validation Functions
export const Validators = {
  /**
   * Validate required field
   */
  required: (value, fieldName) => {
    const result = new ValidationResult();
    if (!value || (typeof value === 'string' && value.trim() === '')) {
      result.addError(VALIDATION_MESSAGES.REQUIRED);
    }
    return result;
  },

  /**
   * Validate minimum length
   */
  minLength: (value, minLength, fieldName) => {
    const result = new ValidationResult();
    if (value && value.length < minLength) {
      result.addError(VALIDATION_MESSAGES.MIN_LENGTH(fieldName, minLength));
    }
    return result;
  },

  /**
   * Validate maximum length
   */
  maxLength: (value, maxLength, fieldName) => {
    const result = new ValidationResult();
    if (value && value.length > maxLength) {
      result.addError(VALIDATION_MESSAGES.MAX_LENGTH(fieldName, maxLength));
    }
    return result;
  },

  /**
   * Validate pattern match
   */
  pattern: (value, pattern, fieldName, customMessage = null) => {
    const result = new ValidationResult();
    if (value && !pattern.test(value)) {
      result.addError(customMessage || VALIDATION_MESSAGES.INVALID_FORMAT(fieldName));
    }
    return result;
  },

  /**
   * Validate email format
   */
  email: (value) => {
    const result = new ValidationResult();
    if (value && !VALIDATION_RULES.EMAIL.PATTERN.test(value)) {
      result.addError(VALIDATION_MESSAGES.INVALID_EMAIL);
    }
    return result;
  },

  /**
   * Validate URL format
   */
  url: (value) => {
    const result = new ValidationResult();
    if (value && !VALIDATION_RULES.PARTICIPANT_URL.PATTERN.test(value)) {
      result.addError(VALIDATION_MESSAGES.INVALID_URL);
    }
    return result;
  },

  /**
   * Validate password strength
   */
  passwordStrength: (value) => {
    const result = new ValidationResult();
    if (value && VALIDATION_RULES.PASSWORD.REQUIRE_SPECIAL_CHARS && !VALIDATION_RULES.PASSWORD.PATTERN.test(value)) {
      result.addError(VALIDATION_MESSAGES.PASSWORD_TOO_WEAK);
    }
    return result;
  }
};

// Comprehensive Field Validators
export const FieldValidators = {
  /**
   * Validate username
   */
  validateUsername: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.USERNAME;
    const rules = VALIDATION_RULES.USERNAME;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.minLength(value, rules.MIN_LENGTH, fieldName));
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      results.push(Validators.pattern(value, rules.PATTERN, fieldName, VALIDATION_MESSAGES.USERNAME_INVALID_CHARS));
    }

    return combineValidationResults(results);
  },

  /**
   * Validate password
   */
  validatePassword: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.PASSWORD;
    const rules = VALIDATION_RULES.PASSWORD;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.minLength(value, rules.MIN_LENGTH, fieldName));
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      if (rules.REQUIRE_SPECIAL_CHARS) {
        results.push(Validators.passwordStrength(value));
      }
    }

    return combineValidationResults(results);
  },

  /**
   * Validate email
   */
  validateEmail: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.EMAIL;
    const rules = VALIDATION_RULES.EMAIL;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      results.push(Validators.email(value));
    }

    return combineValidationResults(results);
  },

  /**
   * Validate wheel name
   */
  validateWheelName: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.WHEEL_NAME;
    const rules = VALIDATION_RULES.WHEEL_NAME;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.minLength(value, rules.MIN_LENGTH, fieldName));
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      results.push(Validators.pattern(value, rules.PATTERN, fieldName, VALIDATION_MESSAGES.WHEEL_NAME_INVALID_CHARS));
    }

    return combineValidationResults(results);
  },

  /**
   * Validate participant name
   */
  validateParticipantName: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.PARTICIPANT_NAME;
    const rules = VALIDATION_RULES.PARTICIPANT_NAME;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.minLength(value, rules.MIN_LENGTH, fieldName));
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      results.push(Validators.pattern(value, rules.PATTERN, fieldName, VALIDATION_MESSAGES.PARTICIPANT_NAME_INVALID_CHARS));
    }

    return combineValidationResults(results);
  },

  /**
   * Validate participant URL
   */
  validateParticipantUrl: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.PARTICIPANT_URL;
    const rules = VALIDATION_RULES.PARTICIPANT_URL;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      results.push(Validators.url(value));
    }

    return combineValidationResults(results);
  },

  /**
   * Validate tenant name
   */
  validateTenantName: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.TENANT_NAME;
    const rules = VALIDATION_RULES.TENANT_NAME;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.minLength(value, rules.MIN_LENGTH, fieldName));
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
      results.push(Validators.pattern(value, rules.PATTERN, fieldName, VALIDATION_MESSAGES.TENANT_NAME_INVALID_CHARS));
    }

    return combineValidationResults(results);
  },

  /**
   * Validate description
   */
  validateDescription: (value) => {
    const results = [];
    const fieldName = FIELD_NAMES.DESCRIPTION;
    const rules = VALIDATION_RULES.DESCRIPTION;

    if (rules.REQUIRED) {
      results.push(Validators.required(value, fieldName));
    }
    if (value) {
      results.push(Validators.minLength(value, rules.MIN_LENGTH, fieldName));
      results.push(Validators.maxLength(value, rules.MAX_LENGTH, fieldName));
    }

    return combineValidationResults(results);
  }
};

// Utility Functions
function combineValidationResults(results) {
  const combinedResult = new ValidationResult();
  
  results.forEach(result => {
    if (result.hasErrors()) {
      result.errors.forEach(error => combinedResult.addError(error));
    }
  });

  return combinedResult;
}

/**
 * Validate multiple fields at once
 * @param {Object} fieldValues - Object with field names as keys and values as values
 * @param {Array} validationRules - Array of validation rule objects
 * @returns {Object} - Object with field names as keys and ValidationResult objects as values
 */
export function validateForm(fieldValues, validationRules) {
  const results = {};

  validationRules.forEach(rule => {
    const { fieldName, validator } = rule;
    const value = fieldValues[fieldName];
    
    if (typeof validator === 'function') {
      results[fieldName] = validator(value);
    } else if (typeof validator === 'string' && FieldValidators[validator]) {
      results[fieldName] = FieldValidators[validator](value);
    }
  });

  return results;
}

/**
 * Check if form validation results have any errors
 * @param {Object} validationResults - Results from validateForm
 * @returns {boolean} - true if any field has errors
 */
export function hasValidationErrors(validationResults) {
  return Object.values(validationResults).some(result => result.hasErrors());
}

/**
 * Get the first error message from form validation results
 * @param {Object} validationResults - Results from validateForm
 * @returns {string|null} - First error message or null if no errors
 */
export function getFirstValidationError(validationResults) {
  for (const result of Object.values(validationResults)) {
    if (result.hasErrors()) {
      return result.getFirstError();
    }
  }
  return null;
}

// Example usage patterns:
/*
// Single field validation:
const usernameResult = FieldValidators.validateUsername('john_doe');
if (usernameResult.hasErrors()) {
  console.log(usernameResult.getFirstError());
}

// Form validation:
const formData = {
  username: 'john_doe',
  email: 'john@example.com',
  password: 'password123'
};

const validationRules = [
  { fieldName: 'username', validator: 'validateUsername' },
  { fieldName: 'email', validator: 'validateEmail' },
  { fieldName: 'password', validator: 'validatePassword' }
];

const results = validateForm(formData, validationRules);
if (hasValidationErrors(results)) {
  console.log('Form has errors:', getFirstValidationError(results));
}
*/
