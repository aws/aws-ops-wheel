#  Unit Tests for Base Exception Classes - AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest

# Add the parent directory to the Python path so we can import api-v2 modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base import BadRequestError, NotFoundError, ConflictError, InternalServerError


def test_bad_request_error_status_code():
    """Test BadRequestError has correct status code"""
    error = BadRequestError("Invalid request")
    assert error.status_code == 400
    assert str(error) == "Invalid request"


def test_not_found_error_status_code():
    """Test NotFoundError has correct status code"""
    error = NotFoundError("Resource not found")
    assert error.status_code == 404
    assert str(error) == "Resource not found"


def test_conflict_error_status_code():
    """Test ConflictError has correct status code"""
    error = ConflictError("Resource conflict")
    assert error.status_code == 409
    assert str(error) == "Resource conflict"


def test_internal_server_error_status_code():
    """Test InternalServerError has correct status code"""
    error = InternalServerError("Internal error")
    assert error.status_code == 500
    assert str(error) == "Internal error"
