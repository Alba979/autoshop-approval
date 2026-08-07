"""Signed, expiring tokens used in one-tap approve/decline links.

We use itsdangerous rather than a plain random string in the URL so that a
token cannot be forged, and so that we can detect tampering (e.g. someone
editing the estimate id in the URL) independently of the database expiry
check on ApprovalRequest.expires_at.
"""
import secrets

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="approval-link"
    )


def generate_approval_token(approval_request_id):
    """Return a URL-safe token that encodes the approval request id.

    A random component is mixed in purely so tokens are not visually
    predictable/sequential, even though the signature already prevents
    tampering.
    """
    nonce = secrets.token_urlsafe(8)
    payload = {"approval_request_id": approval_request_id, "nonce": nonce}
    return _serializer().dumps(payload)


def verify_approval_token(token, max_age_seconds):
    """Return the approval_request_id if the token is valid, else None.

    Raises no exceptions - callers just get None back for any invalid,
    tampered, or expired token, which keeps the customer-facing route
    simple and safe by default.
    """
    try:
        data = _serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("approval_request_id")
