#  Bug Condition Exploration Tests - Participant URL Stored XSS
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  These tests encode the EXPECTED (fixed) behavior for the participant_url
#  stored XSS vulnerability. They are expected to FAIL on unfixed code (where
#  validate_participant_url checks only length), proving the bug exists, and to
#  PASS once the http/https scheme allowlist is enforced.
#
#  Bug: A Wheel Admin can store a participant_url with a dangerous scheme
#  (e.g. "javascript:...") because server-side validation checked only length,
#  not scheme. The stored URL is later passed to window.open()/<a href> in the
#  frontend, so the script executes in a victim admin's session and can read the
#  Cognito idToken from localStorage -> account takeover.
#
#  Sink (frontend): ui-v2/src/components/wheel.jsx window.open(participant_url)
#  Control (server): api-v2/participant_operations.py validate_participant_url

import os
import sys
import pytest

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import BadRequestError
from participant_operations import validate_participant_url, ALLOWED_URL_SCHEMES


# -- Payloads --------------------------------------------------------------

# Representative payload for the stored XSS, plus sibling dangerous schemes.
DANGEROUS_URLS = [
    "javascript:var W=window.opener||window;"
    "W.document.title='TOKEN STOLEN';",
    "javascript:alert(document.domain)",
    "JavaScript:alert(1)",                     # scheme is case-insensitive
    "  javascript:alert(1)",                   # leading whitespace
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "mailto:attacker@example.com",
    "ftp://example.com/x",
    "//evil.example.com",                      # scheme-relative, no scheme
    "/relative/path",                          # relative, no scheme
    "not-a-url",
]

SAFE_URLS = [
    "https://example.com/participant",
    "http://example.com",
    "https://sub.example.com/path?q=1#frag",
    "HTTPS://EXAMPLE.COM",                      # uppercase http(s) still allowed
]


# -- Server-side scheme allowlist ------------------------------------------

@pytest.mark.parametrize("url", DANGEROUS_URLS)
def test_validate_participant_url_rejects_dangerous_scheme(url):
    """SECURITY: validate_participant_url must reject any non-http(s) scheme.

    On unfixed code (length-only check) these all pass validation, which is the
    bug. The fix raises BadRequestError for every dangerous scheme.
    """
    with pytest.raises(BadRequestError):
        validate_participant_url(url)


@pytest.mark.parametrize("url", SAFE_URLS)
def test_validate_participant_url_accepts_http_and_https(url):
    """Legitimate absolute http/https URLs must continue to validate."""
    # Should not raise.
    validate_participant_url(url)


@pytest.mark.parametrize("empty", ["", None])
def test_validate_participant_url_allows_empty(empty):
    """participant_url is optional; empty/None must remain allowed."""
    # Should not raise.
    validate_participant_url(empty)


def test_validate_participant_url_still_enforces_length():
    """The pre-existing length bound must remain enforced for http/https URLs."""
    too_long = "https://example.com/" + ("a" * 600)
    with pytest.raises(BadRequestError):
        validate_participant_url(too_long)


def test_allowed_schemes_are_only_http_https():
    """Guard against accidental widening of the scheme allowlist."""
    assert set(ALLOWED_URL_SCHEMES) == {"http", "https"}
