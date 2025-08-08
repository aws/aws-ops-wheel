#  Base exceptions and utilities for AWS Ops Wheel v2
#  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.

class BadRequestError(Exception):
    """Raised when request parameters are invalid"""
    status_code = 400


class NotFoundError(Exception):
    """Raised when a requested resource is not found"""
    status_code = 404


class ConflictError(Exception):
    """Raised when there's a conflict with the current state"""
    status_code = 409


class InternalServerError(Exception):
    """Raised when there's an internal server error"""
    status_code = 500
