#  Bug Condition Exploration Tests - Cross-Tenant Admin Takeover via Email Collision
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests encode the EXPECTED (fixed) behavior for a cross-tenant admin
#  takeover in the public signup flow. They are expected to FAIL on unfixed
#  code, proving the bug exists.
#
#  Bug: The public unauthenticated signup endpoint accepts an attacker-supplied
#  `admin_user.email`, force-sets `email_verified=true` in Cognito, and writes
#  a DynamoDB Users row with that email under a fresh wheel_group. The request
#  middleware then resolves tenant context by querying the `email-index` GSI
#  and returning items[0] without cross-checking the DynamoDB user_id against
#  the JWT `sub`. An unauthenticated attacker who knows a target admin's email
#  can bind their own Cognito session to the victim's tenant.
#
#  Fix layers verified here:
#    1. create_wheel_group_public rejects duplicate emails and does not
#       force email_verified=true
#    2. middleware / authorizer lookup honors JWT sub when resolving the
#       DynamoDB user record

import base64
import json
import os
import sys
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_gateway_authorizer import lambda_handler
from wheel_group_middleware import (
    lookup_user_wheel_group_info,
    wheel_group_middleware,
)


# ── Helpers ──────────────────────────────────────────────────────────────

VICTIM_EMAIL = "victim-admin@corp.example"
ATTACKER_SUB = "attacker-sub-id-999"
VICTIM_SUB = "victim-sub-id-111"
VICTIM_WHEEL_GROUP = "wg-victim"
ATTACKER_WHEEL_GROUP = "wg-attacker"


def _jwt_payload(email=VICTIM_EMAIL, sub=ATTACKER_SUB):
    now = int(time.time())
    return {
        "sub": sub,
        "email": email,
        "name": "Test User",
        "exp": now + 3600,
        "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_TestPool",
        "aud": "test-client-id",
        "token_use": "id",
        "auth_time": now,
        "iat": now,
    }


def _fake_jwt_token(payload):
    header = {"alg": "RS256", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    s = base64.urlsafe_b64encode(b"fake-sig").decode().rstrip("=")
    return f"{h}.{p}.{s}"


def _authorizer_event(token):
    return {
        "type": "TOKEN",
        "authorizationToken": f"Bearer {token}",
        "methodArn": "arn:aws:execute-api:us-west-2:123456789:abc/dev/GET/api/v2/wheels",
    }


def _middleware_event(token):
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


def _users_table_with_two_rows_for_email():
    """
    Build a mocked DynamoDB Users table whose email-index GSI holds two rows
    for VICTIM_EMAIL: the victim's real record first, then the attacker's.
    lookup_user_wheel_group_info previously returned items[0] and would bind
    the caller to the victim's tenant.
    """
    victim_row = {
        "user_id": VICTIM_SUB,
        "wheel_group_id": VICTIM_WHEEL_GROUP,
        "email": VICTIM_EMAIL,
        "role": "ADMIN",
        "name": "Victim Admin",
    }
    attacker_row = {
        "user_id": ATTACKER_SUB,
        "wheel_group_id": ATTACKER_WHEEL_GROUP,
        "email": VICTIM_EMAIL,
        "role": "ADMIN",
        "name": "Attacker",
    }

    users_table = MagicMock()
    users_table.query.return_value = {"Items": [victim_row, attacker_row]}

    wheel_groups_table = MagicMock()
    wheel_groups_table.get_item.side_effect = lambda Key: {
        "Item": {
            "wheel_group_id": Key["wheel_group_id"],
            "wheel_group_name": Key["wheel_group_id"],
        }
    }
    return users_table, wheel_groups_table


# ── Test 1: lookup honors the JWT sub when disambiguating email rows ─────

@patch.dict(os.environ, {"USERS_TABLE": "Users-test", "WHEEL_GROUPS_TABLE": "WG-test"})
@patch("wheel_group_middleware.dynamodb")
def test_lookup_binds_to_row_matching_jwt_sub(mock_dynamodb):
    """
    Bug Condition: two DynamoDB Users rows share the same email; the lookup
    previously returned items[0], which could be the victim's record.

    Expected (fixed): when the caller's JWT sub is passed in, the lookup
    must return the row whose user_id matches the sub — never the other
    tenant's row.
    """
    users_table, wheel_groups_table = _users_table_with_two_rows_for_email()
    mock_dynamodb.Table.side_effect = lambda name: (
        users_table if "Users" in name else wheel_groups_table
    )

    info = lookup_user_wheel_group_info(VICTIM_EMAIL, user_id=ATTACKER_SUB)

    assert info["user_id"] == ATTACKER_SUB, (
        "SECURITY BUG: lookup returned a user_id that does not match the "
        "caller's JWT sub."
    )
    assert info["wheel_group_id"] == ATTACKER_WHEEL_GROUP, (
        f"SECURITY BUG: lookup bound the caller (sub={ATTACKER_SUB}) to "
        f"wheel_group={info['wheel_group_id']} instead of "
        f"{ATTACKER_WHEEL_GROUP}."
    )


# ── Test 2: lookup refuses to return a row with a different sub ──────────

@patch.dict(os.environ, {"USERS_TABLE": "Users-test", "WHEEL_GROUPS_TABLE": "WG-test"})
@patch("wheel_group_middleware.dynamodb")
def test_lookup_rejects_email_row_when_no_sub_matches(mock_dynamodb):
    """
    Bug Condition: attacker's JWT arrives with sub=UNKNOWN, but the
    email-index only contains rows for other Cognito users.

    Expected (fixed): the lookup must raise instead of returning any row.
    """
    users_table, wheel_groups_table = _users_table_with_two_rows_for_email()
    mock_dynamodb.Table.side_effect = lambda name: (
        users_table if "Users" in name else wheel_groups_table
    )

    with pytest.raises(ValueError, match="does not match authenticated identity"):
        lookup_user_wheel_group_info(VICTIM_EMAIL, user_id="unknown-sub")


# ── Test 3: middleware binds to attacker's tenant, never victim's ────────

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "USERS_TABLE": "Users-test",
    "WHEEL_GROUPS_TABLE": "WG-test",
})
@patch("wheel_group_middleware.verify_cognito_token")
@patch("wheel_group_middleware.dynamodb")
def test_middleware_never_binds_attacker_to_victim_tenant(mock_dynamodb, mock_verify):
    """
    Bug Condition: attacker's JWT has sub=ATTACKER_SUB and email=VICTIM_EMAIL.
    Two DynamoDB rows exist for VICTIM_EMAIL (victim first, attacker second).
    Prior middleware returned items[0] → victim's tenant.

    Expected (fixed): the middleware binds the caller to the attacker's own
    wheel_group_id, or rejects the request outright. It must never surface
    the victim's wheel_group_id.
    """
    users_table, wheel_groups_table = _users_table_with_two_rows_for_email()
    mock_dynamodb.Table.side_effect = lambda name: (
        users_table if "Users" in name else wheel_groups_table
    )

    payload = _jwt_payload(email=VICTIM_EMAIL, sub=ATTACKER_SUB)
    mock_verify.return_value = payload
    event = _middleware_event(_fake_jwt_token(payload))

    result = wheel_group_middleware(event, _mock_lambda_context())

    if "wheel_group_context" in result:
        ctx = result["wheel_group_context"]
        assert ctx.get("wheel_group_id") != VICTIM_WHEEL_GROUP, (
            f"SECURITY BUG: middleware bound sub={ATTACKER_SUB} to the "
            f"victim's wheel_group_id={VICTIM_WHEEL_GROUP}."
        )
        assert ctx.get("user_id") == ATTACKER_SUB, (
            "SECURITY BUG: middleware returned a user_id that does not "
            "match the JWT sub."
        )


# ── Test 4: authorizer never binds attacker to victim tenant ─────────────

@patch.dict(os.environ, {
    "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
    "COGNITO_CLIENT_ID": "test-client-id",
    "USERS_TABLE": "Users-test",
    "WHEEL_GROUPS_TABLE": "WG-test",
})
@patch("api_gateway_authorizer.verify_cognito_token")
@patch("boto3.resource")
def test_authorizer_never_binds_attacker_to_victim_tenant(mock_boto3_resource, mock_verify):
    """
    Same class of bug in the API Gateway Lambda Authorizer, which keeps its
    own inline copy of the lookup logic.

    Expected (fixed): the authorizer's context must never carry the victim's
    wheel_group_id when the JWT sub belongs to a different Cognito user.
    """
    users_table, wheel_groups_table = _users_table_with_two_rows_for_email()
    # api_gateway_authorizer.lookup_user_wheel_group_info uses .scan (not .query),
    # so mirror the two-rows response on scan as well.
    users_table.scan.return_value = users_table.query.return_value
    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = lambda name: (
        users_table if "Users" in name else wheel_groups_table
    )
    mock_boto3_resource.return_value = mock_dynamodb

    payload = _jwt_payload(email=VICTIM_EMAIL, sub=ATTACKER_SUB)
    mock_verify.return_value = payload
    event = _authorizer_event(_fake_jwt_token(payload))

    try:
        result = lambda_handler(event, _mock_lambda_context())
    except Exception:
        # Denying the request is an acceptable outcome.
        return

    ctx = result.get("context", {})
    assert ctx.get("wheel_group_id") != VICTIM_WHEEL_GROUP, (
        f"SECURITY BUG: authorizer bound sub={ATTACKER_SUB} to the victim's "
        f"wheel_group_id={VICTIM_WHEEL_GROUP}."
    )
    assert ctx.get("user_id") in ("", ATTACKER_SUB), (
        "SECURITY BUG: authorizer returned a user_id that does not match "
        "the JWT sub."
    )


# ── Test 5: public signup rejects an already-registered email ────────────

@patch.dict(os.environ, {"COGNITO_USER_POOL_ID": "us-west-2_TestPool"})
@patch("wheel_group_management.UserRepository")
@patch("wheel_group_management.WheelGroupRepository")
@patch("wheel_group_management.boto3.client")
def test_public_signup_rejects_duplicate_email(mock_boto_client, mock_wg_repo, mock_user_repo):
    """
    Bug Condition: the public signup endpoint let a second caller register
    with an existing admin's email, planting a Users row that then confused
    the email-index-based tenant lookup.

    Expected (fixed): if a Users row already exists for the email, the
    handler rejects the request BEFORE creating any Cognito or DynamoDB
    resources.
    """
    from wheel_group_management import create_wheel_group_public

    # Existing admin already owns this email.
    mock_user_repo.get_user_by_email.return_value = {
        "user_id": VICTIM_SUB,
        "email": VICTIM_EMAIL,
        "wheel_group_id": VICTIM_WHEEL_GROUP,
        "role": "ADMIN",
    }

    event = {
        "body": {
            "wheel_group_name": "Attacker Corp",
            "admin_user": {
                "username": "mal-x",
                "email": VICTIM_EMAIL,
                "password": "AttackerPass123!",
            },
        }
    }

    response = create_wheel_group_public(event, context=_mock_lambda_context())

    assert response["statusCode"] == 400, (
        "SECURITY BUG: public signup did not reject a duplicate-email "
        f"registration. Response: {response}"
    )
    body = json.loads(response["body"])
    assert VICTIM_EMAIL in body.get("error", ""), (
        f"Error message should identify the duplicate email. Got: {body}"
    )
    # And no new wheel group was created.
    mock_wg_repo.create_wheel_group.assert_not_called()
    # And no Cognito call was issued.
    mock_boto_client.assert_not_called()


# ── Test 6: public signup does not force email_verified=true ─────────────

@patch.dict(os.environ, {"COGNITO_USER_POOL_ID": "us-west-2_TestPool"})
@patch("wheel_group_management.UserRepository")
@patch("wheel_group_management.WheelGroupRepository")
@patch("wheel_group_management.boto3.client")
def test_public_signup_does_not_force_email_verified(mock_boto_client, mock_wg_repo, mock_user_repo):
    """
    Bug Condition: the handler set `email_verified='true'` unconditionally.
    That bypassed Cognito's email-alias uniqueness enforcement, since
    AliasAttributes only rejects duplicates on a verified email.

    Expected (fixed): the handler must NOT pass email_verified='true' when
    creating the Cognito user. Verification happens through the Cognito
    confirmation flow after the caller proves ownership of the address.
    """
    from wheel_group_management import create_wheel_group_public

    mock_user_repo.get_user_by_email.return_value = None
    mock_wg_repo.create_wheel_group.return_value = {
        "wheel_group_id": "wg-new",
        "wheel_group_name": "New Corp",
    }
    mock_cognito = MagicMock()
    mock_cognito.admin_create_user.return_value = {
        "User": {"Attributes": [{"Name": "sub", "Value": "new-sub"}]}
    }
    mock_boto_client.return_value = mock_cognito
    mock_user_repo.create_user.return_value = {
        "user_id": "new-sub",
        "email": "new@example.com",
        "name": "new",
        "role": "ADMIN",
    }

    event = {
        "body": {
            "wheel_group_name": "New Corp",
            "admin_user": {
                "username": "new-admin",
                "email": "new@example.com",
                "password": "GoodPass123!",
            },
        }
    }

    create_wheel_group_public(event, context=_mock_lambda_context())

    _, kwargs = mock_cognito.admin_create_user.call_args
    attrs = {a["Name"]: a["Value"] for a in kwargs["UserAttributes"]}
    assert "email_verified" not in attrs or attrs["email_verified"] != "true", (
        "SECURITY BUG: public signup forced email_verified='true', bypassing "
        "proof-of-ownership. The Cognito verification flow must run instead."
    )


