"""Helpers for API error responses"""

import logging

from flask import jsonify

from ..exceptions import WireGuardError

logger = logging.getLogger(__name__)

INTERNAL_ERROR_MESSAGE = "Internal server error"


def error_response(exc, status=500):
    """
    Return a JSON error response
    
    Domain exceptions (WireGuardError and subclasses) keep their message.
    Unexpected exceptions are logged with a traceback and replaced by a
    generic message so internals do not leak to the client.
    """
    if isinstance(exc, WireGuardError):
        logger.error("%s", exc)
        return jsonify({"error": str(exc)}), status
    
    logger.exception("Unhandled error")
    return jsonify({"error": INTERNAL_ERROR_MESSAGE}), status
