from datetime import timedelta

from freezegun import freeze_time

from app.services.approval_workflow import (
    send_estimate_for_approval, expire_stale_waiting_jobs,
)
from app.models.job import JobStatus
from app.models.base import utcnow
from tests.conftest import make_estimate


def test_job_expires_after_timeout_with_no_response(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        send_estimate_for_approval(sample_job, estimate)

    assert sample_job.status == JobStatus.WAITING_ON_CUSTOMER

    # Default timeout in testing config comes from Config
    # (WAITING_ON_CUSTOMER_TIMEOUT_HOURS, default 24h). Jump well past it.
    future = utcnow() + timedelta(hours=48)
    with app.test_request_context():
        expired_ids = expire_stale_waiting_jobs(as_of=future)

    assert sample_job.id in expired_ids
    assert sample_job.status == JobStatus.EXPIRED
    assert sample_job.waiting_since is None


def test_job_not_expired_before_timeout(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        send_estimate_for_approval(sample_job, estimate)

    soon = utcnow() + timedelta(hours=1)
    with app.test_request_context():
        expired_ids = expire_stale_waiting_jobs(as_of=soon)

    assert sample_job.id not in expired_ids
    assert sample_job.status == JobStatus.WAITING_ON_CUSTOMER


def test_answered_job_is_never_expired(app, db, sample_job):
    from app.services.approval_workflow import record_customer_response

    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)
        record_customer_response(approval, "approved")

    future = utcnow() + timedelta(hours=48)
    with app.test_request_context():
        expired_ids = expire_stale_waiting_jobs(as_of=future)

    assert sample_job.id not in expired_ids
    assert sample_job.status == JobStatus.APPROVED
