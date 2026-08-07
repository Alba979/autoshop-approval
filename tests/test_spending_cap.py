from decimal import Decimal

from app.services.approval_workflow import estimate_requires_fresh_approval
from app.models.approval import ApprovalRequest
from app.models.base import utcnow
from tests.conftest import make_estimate


def test_estimate_under_cap_does_not_require_fresh_approval(db, sample_job):
    estimate = make_estimate(db, sample_job, "300.00")  # cap is 400.00
    assert estimate_requires_fresh_approval(sample_job, estimate) is False


def test_estimate_over_cap_requires_fresh_approval(db, sample_job):
    estimate = make_estimate(db, sample_job, "500.00")  # cap is 400.00
    assert estimate_requires_fresh_approval(sample_job, estimate) is True


def test_estimate_over_cap_but_already_approved_at_higher_amount(db, sample_job):
    """A technician adding a small item under a previously-approved higher
    estimate should not force a brand-new customer approval."""
    prior_estimate = make_estimate(db, sample_job, "600.00")
    now = utcnow()
    prior_approval = ApprovalRequest(
        job_id=sample_job.id, estimate_id=prior_estimate.id, channel="sms",
        recipient=sample_job.customer.phone_number,
        estimate_total_at_send=Decimal("600.00"), exceeded_spending_cap=True,
        sent_at=now, expires_at=now, token="prior-token-abc",
        response="approved", responded_at=now,
    )
    db.session.add(prior_approval)
    db.session.commit()

    new_estimate = make_estimate(db, sample_job, "550.00")
    assert estimate_requires_fresh_approval(sample_job, new_estimate) is False


def test_estimate_exceeding_prior_approved_amount_requires_new_approval(db, sample_job):
    prior_estimate = make_estimate(db, sample_job, "450.00")
    now = utcnow()
    prior_approval = ApprovalRequest(
        job_id=sample_job.id, estimate_id=prior_estimate.id, channel="sms",
        recipient=sample_job.customer.phone_number,
        estimate_total_at_send=Decimal("450.00"), exceeded_spending_cap=True,
        sent_at=now, expires_at=now, token="prior-token-def",
        response="approved", responded_at=now,
    )
    db.session.add(prior_approval)
    db.session.commit()

    new_estimate = make_estimate(db, sample_job, "700.00")
    assert estimate_requires_fresh_approval(sample_job, new_estimate) is True


def test_declined_prior_approval_does_not_count_as_fresh(db, sample_job):
    prior_estimate = make_estimate(db, sample_job, "600.00")
    now = utcnow()
    prior_approval = ApprovalRequest(
        job_id=sample_job.id, estimate_id=prior_estimate.id, channel="sms",
        recipient=sample_job.customer.phone_number,
        estimate_total_at_send=Decimal("600.00"), exceeded_spending_cap=True,
        sent_at=now, expires_at=now, token="prior-token-ghi",
        response="declined", responded_at=now,
    )
    db.session.add(prior_approval)
    db.session.commit()

    new_estimate = make_estimate(db, sample_job, "550.00")
    assert estimate_requires_fresh_approval(sample_job, new_estimate) is True
