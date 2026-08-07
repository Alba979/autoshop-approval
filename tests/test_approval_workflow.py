from decimal import Decimal

from app.services.approval_workflow import (
    send_estimate_for_approval, record_customer_response,
)
from app.services.tokens import generate_approval_token, verify_approval_token
from app.models.job import JobStatus
from tests.conftest import make_estimate


def test_send_estimate_moves_job_to_waiting_on_customer(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)

    assert sample_job.status == JobStatus.WAITING_ON_CUSTOMER
    assert sample_job.waiting_since is not None
    assert approval.token
    assert approval.is_pending


def test_approving_marks_job_approved_and_stops_waiting(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)
        record_customer_response(approval, "approved", ip_address="127.0.0.1")

    assert sample_job.status == JobStatus.APPROVED
    assert sample_job.waiting_since is None
    assert approval.responded_at is not None
    assert approval.response == "approved"


def test_declining_marks_job_declined(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)
        record_customer_response(approval, "declined")

    assert sample_job.status == JobStatus.DECLINED
    assert approval.response == "declined"


def test_double_response_is_idempotent(app, db, sample_job):
    """A customer tapping the link twice (or reloading after responding)
    must not be able to flip their answer or lose the original timestamp."""
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)
        record_customer_response(approval, "approved")
        first_responded_at = approval.responded_at

        # Attempting to decline after already approving should be a no-op.
        record_customer_response(approval, "declined")

    assert approval.response == "approved"
    assert approval.responded_at == first_responded_at


def test_token_round_trips(app):
    with app.test_request_context():
        token = generate_approval_token(approval_request_id=42)
        result = verify_approval_token(token, max_age_seconds=3600)
    assert result == 42


def test_tampered_token_is_rejected(app):
    with app.test_request_context():
        token = generate_approval_token(approval_request_id=42)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        result = verify_approval_token(tampered, max_age_seconds=3600)
    assert result is None


def test_expired_token_is_rejected(app):
    with app.test_request_context():
        token = generate_approval_token(approval_request_id=42)
        result = verify_approval_token(token, max_age_seconds=-1)
    assert result is None
