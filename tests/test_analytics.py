from datetime import timedelta
from decimal import Decimal

from app.services.approval_workflow import send_estimate_for_approval, record_customer_response
from app.services.analytics import (
    approval_turnaround_by_technician, estimate_vs_final_variance_by_technician,
)
from app.models.job import JobStatus
from app.models.base import utcnow
from tests.conftest import make_estimate


def test_turnaround_only_counts_answered_requests(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "250.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)
        # Simulate a 2-hour turnaround.
        approval.sent_at = utcnow() - timedelta(hours=2)
        db.session.commit()
        record_customer_response(approval, "approved")

    results = approval_turnaround_by_technician()
    row = next(r for r in results if r["technician"] == "Test Tech")
    assert row["sample_size"] == 1
    assert row["avg_turnaround_hours"] is not None
    assert row["avg_turnaround_hours"] >= 1.9  # allow small test-runtime drift


def test_variance_uses_approved_estimate_vs_final_cost(app, db, sample_job):
    estimate = make_estimate(db, sample_job, "200.00")
    with app.test_request_context():
        approval = send_estimate_for_approval(sample_job, estimate)
        record_customer_response(approval, "approved")

    sample_job.status = JobStatus.COMPLETED
    sample_job.final_cost = Decimal("220.00")  # 10% over the approved estimate
    db.session.commit()

    results = estimate_vs_final_variance_by_technician()
    row = next(r for r in results if r["technician"] == "Test Tech")
    assert row["sample_size"] == 1
    assert row["avg_variance_dollars"] == 20.0
    assert abs(row["avg_variance_pct"] - 10.0) < 0.01
