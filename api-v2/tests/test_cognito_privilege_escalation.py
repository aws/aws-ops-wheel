#  Bug Condition Exploration Tests - Cognito Privilege Escalation
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests encode the EXPECTED (fixed) behavior for the Cognito privilege
#  escalation vulnerability. They are expected to FAIL on unfixed code,
#  proving the bug exists.
#
#  Bug: Any authenticated user can set custom:deployment_admin="true" on their
#  own Cognito profile and gain full deployment admin access because the
#  authorizer, middleware, and deployment admin operations blindly trust
#  the JWT claim without server-side verification.
#
#  Validates: Requirements 1.1, 1.3, 1.4, 1.5

import os
import sys
import pytest
import json
import base64
import time
import yaml
from unittest.mock import patch, Mock

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_gateway_authorizer import lambda_handler, generate_policy
from wheel_group_middleware import wheel_group_middleware, get_role_permissions
from deployment_admin_operations import check_deployment_admin_permission


# ── Helpers ──────────────────────────────────────────────────────────────

ATTACKER_EMAIL = "attacker@example.com"
LEGITIMATE_ADMIN_EMAIL = "admin@example.com"


def _jwt_payload(email=ATTACKER_EMAIL, deployment_admin="true"):
    """Create a JWT payload with custom:deployment_admin claim."""
    now = int(time.time())
    return {
        "sub": "attacker-sub-id-999",
        "email": email,
        "name": "Attacker User",
        "exp": now + 3600,
        "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_TestPool",
        "aud": "test-client-id",
        "token_use": "id",
        "auth_time": now,
        "iat": now,
        "custom:deployment_admin": deployment_admin,
    }


def _fake_jwt_token(payload):
    """Build a structurally valid (but unsigned) JWT string."""
    header = {"alg": "RS256", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    s = base64.urlsafe_b64encode(b"fake-sig").decode().rstrip("=")
    return f"{h}.{p}.{s}"


def _authorizer_event(token):
    """API Gateway TOKEN authorizer event."""
    return {
        "type": "TOKEN",
        "authorizationToken": f"Bearer {token}",
        "methodArn": "arn:aws:execute-api:us-west-2:123456789:abc/dev/GET/api/v2/wheels",
    }


def _middleware_event(token):
    """HTTP event consumed by wheel_group_middleware."""
    return {
        "path": "/api/v2/wheels",
        "httpMethod": "GET",
        "headers": {"Authorization": f"Bearer {token}"},
        "queryStringParameters": None,
        "body": None,
        "isBase64Encoded": False,
    }


def _mock_lambda_context():
    ctx = Mock()
    ctx.aws_request_id = "test-req-id"
    ctx.log_group_name = "/aws/lambda/test"
    return ctx


# ── Test 1: Authorizer must NOT grant DEPLOYMENT_ADMIN to non-admin ─────
# **Validates: Requirements 1.3, 2.3**

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
@patch("api_gateway_authorizer.verify_cognito_token")
def test_authorizer_rejects_deployment_admin_for_non_admin_email(mock_verify):
    """
    Bug Condition: attacker@example.com has custom:deployment_admin='true'
    in their JWT but is NOT a legitimate admin.

    Expected (fixed): The authorizer must NOT return DEPLOYMENT_ADMIN role.
    On unfixed code this WILL FAIL because the authorizer blindly trusts
    the JWT claim.
    """
    payload = _jwt_payload(email=ATTACKER_EMAIL, deployment_admin="true")
    mock_verify.return_value = payload
    token = _fake_jwt_token(payload)
    event = _authorizer_event(token)

    result = lambda_handler(event, _mock_lambda_context())

    # The authorizer should either Deny or Allow with a non-admin role
    context = result.get("context", {})
    assert context.get("role") != "DEPLOYMENT_ADMIN", (
        f"SECURITY BUG: Authorizer granted DEPLOYMENT_ADMIN to {ATTACKER_EMAIL} "
        f"who is NOT a legitimate admin. Context: {context}"
    )
    assert context.get("deployment_admin") != "True", (
        f"SECURITY BUG: deployment_admin flag is True for non-admin {ATTACKER_EMAIL}"
    )


# ── Test 2: Middleware must NOT grant DEPLOYMENT_ADMIN to non-admin ──────
# **Validates: Requirements 1.4, 2.4**

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
@patch("wheel_group_middleware.verify_cognito_token")
def test_middleware_rejects_deployment_admin_for_non_admin_email(mock_verify):
    """
    Bug Condition: attacker@example.com has custom:deployment_admin='true'
    in their JWT but is NOT a legitimate admin.

    Expected (fixed): The middleware must NOT set role=DEPLOYMENT_ADMIN.
    On unfixed code this WILL FAIL because the middleware blindly trusts
    the JWT claim.
    """
    payload = _jwt_payload(email=ATTACKER_EMAIL, deployment_admin="true")
    mock_verify.return_value = payload
    token = _fake_jwt_token(payload)
    event = _middleware_event(token)

    result = wheel_group_middleware(event, _mock_lambda_context())

    # If middleware returned an error response (statusCode), that's acceptable
    # — it means the attacker was denied. But if it returned an enriched event,
    # the role must NOT be DEPLOYMENT_ADMIN.
    if "wheel_group_context" in result:
        ctx = result["wheel_group_context"]
        assert ctx.get("role") != "DEPLOYMENT_ADMIN", (
            f"SECURITY BUG: Middleware granted DEPLOYMENT_ADMIN role to "
            f"{ATTACKER_EMAIL} who is NOT a legitimate admin. Context: {ctx}"
        )
        assert ctx.get("deployment_admin") is not True, (
            f"SECURITY BUG: deployment_admin flag is True for non-admin "
            f"{ATTACKER_EMAIL}"
        )


# ── Test 3: check_deployment_admin_permission must deny non-admin ────────
# **Validates: Requirements 1.5, 2.5**

@patch.dict(os.environ, {
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
def test_deployment_admin_permission_denies_non_admin_with_escalated_claim():
    """
    Bug Condition: An event arrives with deployment_admin=true in the
    authorizer context, but the user's email is NOT in the admin list.

    Expected (fixed): check_deployment_admin_permission returns False.
    On unfixed code this WILL FAIL because the function only checks the
    flag without verifying the email.
    """
    event = {
        "user_info": {
            "deployment_admin": True,
            "email": ATTACKER_EMAIL,
        },
        "wheel_group_context": {
            "deployment_admin": True,
            "email": ATTACKER_EMAIL,
        },
        "requestContext": {
            "authorizer": {
                "deployment_admin": "true",
                "email": ATTACKER_EMAIL,
            }
        },
    }

    result = check_deployment_admin_permission(event)

    assert result is False, (
        f"SECURITY BUG: check_deployment_admin_permission returned True for "
        f"{ATTACKER_EMAIL} who is NOT a legitimate admin. The function blindly "
        f"trusts the deployment_admin flag without verifying the email."
    )


# ── Test 4: CloudFormation template must restrict WriteAttributes ────────
# **Validates: Requirements 2.1, 3.3**

def test_cognito_user_pool_client_excludes_sensitive_write_attributes():
    """
    Bug Condition: The UserPoolClient in cognito-v2.yml has no
    WriteAttributes restriction, allowing any authenticated user to
    set custom:deployment_admin on their own profile.

    Expected (fixed): UserPoolClient has WriteAttributes that includes
    standard attributes (email, name) but EXCLUDES
    custom:deployment_admin and custom:wheel_group_id.

    On unfixed code this WILL FAIL because WriteAttributes is missing.
    """
    # Register CloudFormation intrinsic function constructors so
    # yaml.safe_load can parse !Ref, !Sub, !GetAtt, etc.
    cfn_tags = [
        "!Ref", "!Sub", "!GetAtt", "!Select", "!Split", "!Join",
        "!If", "!Not", "!Equals", "!And", "!Or", "!FindInMap",
        "!Base64", "!Cidr", "!ImportValue", "!GetAZs",
        "!Condition", "!Transform",
    ]
    for tag in cfn_tags:
        yaml.SafeLoader.add_constructor(
            tag,
            lambda loader, node: node.value
            if isinstance(node, yaml.ScalarNode)
            else loader.construct_sequence(node)
            if isinstance(node, yaml.SequenceNode)
            else loader.construct_mapping(node),
        )

    template_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "cloudformation-v2", "cognito-v2.yml"
    )
    with open(template_path, "r") as f:
        template = yaml.safe_load(f)

    user_pool_client = template["Resources"]["UserPoolClient"]["Properties"]

    assert "WriteAttributes" in user_pool_client, (
        "SECURITY BUG: UserPoolClient has no WriteAttributes restriction. "
        "Any authenticated user can call UpdateUserAttributes to set "
        "custom:deployment_admin='true' on their own profile."
    )

    write_attrs = user_pool_client["WriteAttributes"]

    assert "custom:deployment_admin" not in write_attrs, (
        "SECURITY BUG: WriteAttributes includes custom:deployment_admin. "
        "Users can self-assign deployment admin privileges."
    )
    assert "custom:wheel_group_id" not in write_attrs, (
        "SECURITY BUG: WriteAttributes includes custom:wheel_group_id. "
        "Users can switch to another tenant's wheel group."
    )


# ═══════════════════════════════════════════════════════════════════════
#  Preservation Property Tests - Baseline Behavior (BEFORE fix)
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests capture EXISTING correct behavior that must be preserved
#  after the fix is applied. They MUST PASS on both unfixed and fixed code.
#
#  **Validates: Requirements 3.1, 3.2, 3.5**
# ═══════════════════════════════════════════════════════════════════════


# ── Preservation Test 1: Legitimate admin gets DEPLOYMENT_ADMIN role ────
# **Validates: Requirements 3.1**

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
@patch("api_gateway_authorizer.verify_cognito_token")
def test_preservation_authorizer_grants_deployment_admin_to_legitimate_admin(mock_verify):
    """
    Preservation: A legitimate admin (admin@example.com) whose email IS in
    DEPLOYMENT_ADMIN_EMAILS and whose JWT has custom:deployment_admin='true'
    must receive DEPLOYMENT_ADMIN role from the authorizer.

    This must work on BOTH unfixed and fixed code.
    """
    payload = _jwt_payload(email=LEGITIMATE_ADMIN_EMAIL, deployment_admin="true")
    # Override sub/name for the legitimate admin
    payload["sub"] = "admin-sub-id-001"
    payload["name"] = "Admin User"
    mock_verify.return_value = payload
    token = _fake_jwt_token(payload)
    event = _authorizer_event(token)

    result = lambda_handler(event, _mock_lambda_context())

    # The authorizer must return Allow with DEPLOYMENT_ADMIN role
    context = result.get("context", {})
    assert context.get("role") == "DEPLOYMENT_ADMIN", (
        f"Legitimate admin {LEGITIMATE_ADMIN_EMAIL} should get DEPLOYMENT_ADMIN role. "
        f"Got: {context}"
    )
    assert context.get("deployment_admin") == "True", (
        f"Legitimate admin should have deployment_admin=True. Got: {context}"
    )
    # Verify Allow policy
    policy_doc = result.get("policyDocument", {})
    statements = policy_doc.get("Statement", [])
    assert len(statements) > 0, "Policy must have at least one statement"
    assert statements[0].get("Effect") == "Allow", (
        f"Legitimate admin should get Allow policy. Got: {statements}"
    )


# ── Preservation Test 2: Regular user without deployment_admin claim ────
#    goes through DynamoDB lookup in the authorizer
# **Validates: Requirements 3.2**

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
    "USERS_TABLE": "OpsWheelV2-Users-test",
    "WHEEL_GROUPS_TABLE": "OpsWheelV2-WheelGroups-test",
})
@patch("api_gateway_authorizer.verify_cognito_token")
@patch("api_gateway_authorizer.lookup_user_wheel_group_info")
def test_preservation_authorizer_regular_user_dynamo_lookup(mock_lookup, mock_verify):
    """
    Preservation: A regular user whose JWT does NOT have
    custom:deployment_admin='true' must go through DynamoDB lookup
    and get the correct role from the authorizer.

    This must work on BOTH unfixed and fixed code.
    """
    now = int(time.time())
    regular_payload = {
        "sub": "regular-sub-id-002",
        "email": "regular@example.com",
        "name": "Regular User",
        "exp": now + 3600,
        "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_TestPool",
        "aud": "test-client-id",
        "token_use": "id",
        "auth_time": now,
        "iat": now,
        # No custom:deployment_admin claim
    }
    mock_verify.return_value = regular_payload
    mock_lookup.return_value = {
        "user_id": "regular-sub-id-002",
        "wheel_group_id": "wg-test-123",
        "wheel_group_name": "Test Group",
        "role": "USER",
        "email": "regular@example.com",
        "name": "Regular User",
        "permissions": ["spin_wheel", "view_wheels"],
    }

    token = _fake_jwt_token(regular_payload)
    event = _authorizer_event(token)

    result = lambda_handler(event, _mock_lambda_context())

    # DynamoDB lookup must have been called
    mock_lookup.assert_called_once_with("regular@example.com")

    # The authorizer must return Allow with the role from DynamoDB
    context = result.get("context", {})
    assert context.get("role") == "USER", (
        f"Regular user should get USER role from DynamoDB lookup. Got: {context}"
    )
    assert context.get("wheel_group_id") == "wg-test-123", (
        f"Regular user should have wheel_group_id from DynamoDB. Got: {context}"
    )
    # Verify Allow policy
    policy_doc = result.get("policyDocument", {})
    statements = policy_doc.get("Statement", [])
    assert len(statements) > 0
    assert statements[0].get("Effect") == "Allow"


# ── Preservation Test 3: Regular user without deployment_admin claim ────
#    goes through DynamoDB lookup in the middleware
# **Validates: Requirements 3.2**

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
@patch("wheel_group_middleware.verify_cognito_token")
@patch("wheel_group_middleware.lookup_user_wheel_group_info")
def test_preservation_middleware_regular_user_dynamo_lookup(mock_lookup, mock_verify):
    """
    Preservation: A regular user whose JWT does NOT have
    custom:deployment_admin='true' must go through DynamoDB lookup
    in the middleware and get the correct user context.

    This must work on BOTH unfixed and fixed code.
    """
    now = int(time.time())
    regular_payload = {
        "sub": "regular-sub-id-003",
        "email": "user@example.com",
        "name": "Normal User",
        "exp": now + 3600,
        "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_TestPool",
        "aud": "test-client-id",
        "token_use": "id",
        "auth_time": now,
        "iat": now,
        # No custom:deployment_admin claim
    }
    mock_verify.return_value = regular_payload
    mock_lookup.return_value = {
        "user_id": "regular-sub-id-003",
        "wheel_group_id": "wg-test-456",
        "wheel_group_name": "Another Group",
        "role": "WHEEL_ADMIN",
        "email": "user@example.com",
        "name": "Normal User",
    }

    token = _fake_jwt_token(regular_payload)
    event = _middleware_event(token)

    result = wheel_group_middleware(event, _mock_lambda_context())

    # DynamoDB lookup must have been called
    mock_lookup.assert_called_once_with("user@example.com")

    # The middleware must return an enriched event (not an error response)
    assert "wheel_group_context" in result, (
        f"Middleware should return enriched event with wheel_group_context. Got: {result}"
    )
    ctx = result["wheel_group_context"]
    assert ctx["role"] == "WHEEL_ADMIN", (
        f"Regular user should get WHEEL_ADMIN role from DynamoDB. Got: {ctx}"
    )
    assert ctx["wheel_group_id"] == "wg-test-456"
    assert ctx["deployment_admin"] is False


# ── Preservation Test 4: Requests without valid Bearer token rejected ───
# **Validates: Requirements 3.5**

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
def test_preservation_authorizer_rejects_missing_bearer_token():
    """
    Preservation: Requests without a valid Bearer token must be rejected
    with a Deny policy by the authorizer.

    This must work on BOTH unfixed and fixed code.
    """
    # Test with no Bearer prefix
    event_no_bearer = {
        "type": "TOKEN",
        "authorizationToken": "invalid-token-no-bearer",
        "methodArn": "arn:aws:execute-api:us-west-2:123456789:abc/dev/GET/api/v2/wheels",
    }
    result = lambda_handler(event_no_bearer, _mock_lambda_context())

    # Should return Deny policy
    policy_doc = result.get("policyDocument", {})
    statements = policy_doc.get("Statement", [])
    assert len(statements) > 0, "Deny policy must have at least one statement"
    assert statements[0].get("Effect") == "Deny", (
        f"Missing Bearer token should result in Deny policy. Got: {statements}"
    )


@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "DEPLOYMENT_ADMIN_EMAILS": LEGITIMATE_ADMIN_EMAIL,
})
def test_preservation_middleware_rejects_missing_bearer_token():
    """
    Preservation: Requests without a valid Bearer token must be rejected
    with 401 by the middleware.

    This must work on BOTH unfixed and fixed code.
    """
    # Test with no Authorization header
    event_no_auth = {
        "path": "/api/v2/wheels",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": None,
        "body": None,
        "isBase64Encoded": False,
    }
    result = wheel_group_middleware(event_no_auth, _mock_lambda_context())

    assert result.get("statusCode") == 401, (
        f"Missing Authorization header should return 401. Got: {result.get('statusCode')}"
    )


# ── Preservation Test 5: CloudFormation Schema includes email and name ──
#    as mutable attributes (prerequisite for them being writable)
# **Validates: Requirements 3.3**

def test_preservation_cognito_schema_includes_email_and_name_as_mutable():
    """
    Preservation: The CloudFormation template's UserPool Schema must include
    email and name as mutable attributes. This is the prerequisite for them
    being writable by users (via UpdateUserAttributes or WriteAttributes).

    The email attribute is defined in Schema with Mutable: true.
    The name attribute is a standard Cognito attribute that is mutable by default.

    This must work on BOTH unfixed and fixed code.
    """
    # Register CloudFormation intrinsic function constructors
    cfn_tags = [
        "!Ref", "!Sub", "!GetAtt", "!Select", "!Split", "!Join",
        "!If", "!Not", "!Equals", "!And", "!Or", "!FindInMap",
        "!Base64", "!Cidr", "!ImportValue", "!GetAZs",
        "!Condition", "!Transform",
    ]
    for tag in cfn_tags:
        yaml.SafeLoader.add_constructor(
            tag,
            lambda loader, node: node.value
            if isinstance(node, yaml.ScalarNode)
            else loader.construct_sequence(node)
            if isinstance(node, yaml.SequenceNode)
            else loader.construct_mapping(node),
        )

    template_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "cloudformation-v2", "cognito-v2.yml"
    )
    with open(template_path, "r") as f:
        template = yaml.safe_load(f)

    user_pool_props = template["Resources"]["UserPool"]["Properties"]
    schema = user_pool_props.get("Schema", [])

    # Find the email attribute in the schema
    email_attrs = [attr for attr in schema if attr.get("Name") == "email"]
    assert len(email_attrs) > 0, (
        "UserPool Schema must include an 'email' attribute definition"
    )
    email_attr = email_attrs[0]
    assert email_attr.get("Mutable") is True, (
        f"email attribute must be Mutable: true. Got: {email_attr}"
    )

    # Verify that name is a standard Cognito attribute — it's mutable by default
    # and doesn't need to be in the Schema. We just verify the Schema doesn't
    # explicitly set it to non-mutable.
    name_attrs = [attr for attr in schema if attr.get("Name") == "name"]
    if name_attrs:
        # If name IS in the schema, it must be mutable
        assert name_attrs[0].get("Mutable") is not False, (
            f"If name is in Schema, it must not be Mutable: false. Got: {name_attrs[0]}"
        )
    # If name is NOT in the schema, that's fine — standard attributes are mutable by default
