"""
Shared JWT verification module for AWS Ops Wheel v2.

Fetches JWKS from the Cognito User Pool, caches public keys, and verifies
RS256 signatures using PyJWT. This replaces the insecure base64-only decoding
that was previously used in api_gateway_authorizer.py and wheel_group_middleware.py.
"""

import json
import logging
import time
import urllib.request
from typing import Any, Dict, Optional

import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)

# Module-level cache for JWKS keys
_jwks_cache: Dict[str, Any] = {}
_jwks_cache_timestamp: float = 0
_JWKS_CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_jwks_url(user_pool_id: str) -> str:
    """Build the JWKS URL for a Cognito User Pool."""
    region = user_pool_id.split('_')[0]
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"


def _get_issuer(user_pool_id: str) -> str:
    """Build the expected issuer URL for a Cognito User Pool."""
    region = user_pool_id.split('_')[0]
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def _fetch_jwks(user_pool_id: str) -> Dict[str, Any]:
    """
    Fetch and cache JWKS (JSON Web Key Set) from the Cognito User Pool.

    Keys are cached for _JWKS_CACHE_TTL_SECONDS to avoid hitting the
    JWKS endpoint on every request.
    """
    global _jwks_cache, _jwks_cache_timestamp

    now = time.time()
    if _jwks_cache and (now - _jwks_cache_timestamp) < _JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    jwks_url = _get_jwks_url(user_pool_id)
    logger.info(f"Fetching JWKS from {jwks_url}")

    try:
        req = urllib.request.Request(jwks_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            jwks = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from {jwks_url}: {e}")
        # If we have a stale cache, use it rather than failing open
        if _jwks_cache:
            logger.warning("Using stale JWKS cache after fetch failure")
            return _jwks_cache
        raise ValueError(f"Unable to fetch JWKS and no cached keys available: {e}")

    _jwks_cache = jwks
    _jwks_cache_timestamp = now
    return jwks


def _get_signing_key(token: str, user_pool_id: str):
    """
    Extract the signing key from JWKS that matches the token's kid (Key ID).
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as e:
        raise ValueError(f"Invalid JWT header: {e}")

    kid = unverified_header.get('kid')
    if not kid:
        raise ValueError("JWT header missing 'kid' (Key ID)")

    jwks = _fetch_jwks(user_pool_id)
    keys = jwks.get('keys', [])

    for key_data in keys:
        if key_data.get('kid') == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key_data))

    # Key not found — maybe keys rotated. Force refresh and retry once.
    global _jwks_cache_timestamp
    _jwks_cache_timestamp = 0
    jwks = _fetch_jwks(user_pool_id)
    keys = jwks.get('keys', [])

    for key_data in keys:
        if key_data.get('kid') == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key_data))

    raise ValueError(f"Unable to find signing key for kid: {kid}")


def verify_cognito_token(
    token: str,
    user_pool_id: str,
    client_id: str,
    token_use: str = "id",
) -> Dict[str, Any]:
    """
    Verify a Cognito JWT token with full RS256 signature verification.

    Args:
        token: The raw JWT string.
        user_pool_id: The Cognito User Pool ID (e.g. us-west-2_AbCdEfG).
        client_id: The Cognito App Client ID.
        token_use: Expected token_use claim (default: "id").

    Returns:
        The verified and decoded JWT payload as a dict.

    Raises:
        ValueError: If the token is invalid, expired, or signature verification fails.
    """
    signing_key = _get_signing_key(token, user_pool_id)
    expected_issuer = _get_issuer(user_pool_id)

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=expected_issuer,
            audience=client_id,
            options={
                "require": ["sub", "exp", "iss", "aud", "token_use"],
            },
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid token issuer")
    except jwt.InvalidAudienceError:
        raise ValueError("Invalid token audience")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid token signature")
    except jwt.DecodeError as e:
        raise ValueError(f"Token decode failed: {e}")
    except Exception as e:
        raise ValueError(f"Token verification failed: {e}")

    # Verify token_use claim
    if payload.get('token_use') != token_use:
        raise ValueError(
            f"Invalid token_use: expected '{token_use}', got '{payload.get('token_use')}'"
        )

    return payload
