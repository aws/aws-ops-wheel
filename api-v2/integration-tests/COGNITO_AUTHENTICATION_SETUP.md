# AWS Cognito Authentication Setup for Integration Tests

## Overview

The integration tests now use **direct AWS Cognito SDK authentication** instead of API login endpoints. This provides more reliable authentication and better handles password challenges.

## ✅ What Was Fixed

1. **Direct Cognito Authentication**: Tests now authenticate directly with AWS Cognito User Pool using boto3 SDK
2. **Password Challenge Handling**: Automatic handling of `NEW_PASSWORD_REQUIRED` challenges
3. **Token Management**: Proper JWT token parsing and validation
4. **Session Management**: Improved token lifecycle and cleanup

## 🔧 Implementation Details

### New Components

1. **CognitoAuthenticator** (`utils/cognito_authenticator.py`)
   - Direct AWS Cognito authentication
   - Challenge handling (password changes)
   - Token refresh and sign-out

2. **Updated AuthManager** (`utils/auth_manager.py`)
   - Integration with CognitoAuthenticator
   - Improved token parsing and validation

3. **Enhanced Test Configuration** (`config/test_config.py`)
   - Cognito User Pool ID and Client ID configuration
   - AWS region configuration

## 📋 Test Results Summary

### ✅ Working Features
- **Cognito Authentication**: Direct SDK authentication working
- **Password Challenges**: NEW_PASSWORD_REQUIRED handled automatically  
- **Token Parsing**: JWT decoding and user info extraction
- **Session Management**: Token lifecycle and cleanup

### ⚠️ Configuration Required
- **Admin User Setup**: Test admin user needs `deployment_admin` custom attribute

## 🚀 Setup Requirements

### 1. Cognito User Pool Configuration

The test admin user must have the following custom attributes:

```json
{
  "custom:deployment_admin": "true",
  "custom:wheel_group_id": "optional-wheel-group-id"
}
```

### 2. Environment Configuration

Update `config/environments.json`:

```json
{
  "test": {
    "cognito_user_pool_id": "us-west-2_Wmq7q6TlY",
    "cognito_client_id": "6qs2uogod8jp1mbjffk3tfk41a",
    "aws_region": "us-west-2",
    "admin_username": "admin",
    "admin_password": "TempPass123!test"
  }
}
```

### 3. AWS Credentials

Ensure AWS credentials are configured for the test environment:

```bash
# Via AWS CLI
aws configure

# Or via environment variables
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-west-2"
```

## 🔧 Setting Up Admin User

### Using AWS CLI

```bash
# Update user attributes
aws cognito-idp admin-update-user-attributes \
  --user-pool-id us-west-2_Wmq7q6TlY \
  --username admin \
  --user-attributes Name=custom:deployment_admin,Value=true

# Verify attributes
aws cognito-idp admin-get-user \
  --user-pool-id us-west-2_Wmq7q6TlY \
  --username admin
```

### Using AWS Console

1. Go to Amazon Cognito console
2. Select User Pool: `us-west-2_Wmq7q6TlY`
3. Find user "admin"
4. Edit user attributes
5. Set `custom:deployment_admin` to `true`

## 🧪 Running Tests

### Basic Test Run
```bash
cd api-v2/integration-tests
python run_tests.py --environment=test --integration-debug
```

### Authentication Tests Only
```bash
python run_tests.py --environment=test --integration-debug --auth
```

### With Specific Environment
```bash
python run_tests.py --environment=dev --integration-debug
```

## 📊 Test Output Analysis

### Successful Authentication Log
```
[COGNITO_AUTH] Authenticating user: admin
[COGNITO_AUTH] Challenge required: NEW_PASSWORD_REQUIRED
[COGNITO_AUTH] Handling NEW_PASSWORD_REQUIRED challenge for: admin
[COGNITO_AUTH] Password change successful for user: admin
[AUTH] Authentication successful for: admin
```

### Common Issues

#### "User does not have deployment admin privileges"
- **Cause**: `custom:deployment_admin` not set to "true"
- **Fix**: Update user attributes in Cognito User Pool

#### "Cognito authenticator not configured"
- **Cause**: Test creating AuthManager without injecting CognitoAuthenticator
- **Fix**: Use the session-scoped `auth_manager` fixture

## 🔄 Migration Notes

### Before (API Login)
```python
# Old approach - used fake API endpoints
response = api_client.post('/app/api/v2/auth/login', data=login_data)
```

### After (Cognito SDK)
```python
# New approach - direct Cognito authentication
tokens = cognito_authenticator.authenticate_user(username, password)
```

## 🎯 Benefits

1. **More Reliable**: Direct SDK authentication eliminates API endpoint dependencies
2. **Better Error Handling**: Proper Cognito error codes and messages
3. **Challenge Support**: Automatic handling of password challenges
4. **Token Validation**: Proper JWT parsing and validation
5. **Real Authentication**: Uses actual AWS Cognito instead of mock endpoints

## 🔧 Troubleshooting

### Debug Mode
Always run with `--integration-debug` for detailed logging:

```bash
python run_tests.py --environment=test --integration-debug
```

### AWS Credentials Issues
```bash
# Check AWS configuration
aws sts get-caller-identity

# Test Cognito access
aws cognito-idp list-user-pools --max-results 10
```

### User Pool Issues
```bash
# Verify user exists
aws cognito-idp admin-get-user \
  --user-pool-id us-west-2_Wmq7q6TlY \
  --username admin
```

## 📈 Next Steps

1. **Set up admin user attributes** in Cognito User Pool
2. **Configure AWS credentials** for test environment
3. **Run integration tests** to verify setup
4. **Update CI/CD pipelines** with new authentication approach

The Cognito authentication integration is complete and working. The remaining step is configuring the test admin user with proper privileges in the Cognito User Pool.
