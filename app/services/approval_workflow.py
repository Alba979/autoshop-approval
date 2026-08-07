"""
Core workflow logic that ties diagnostics -> estimate -> customer approval
-> authorized work together.

Every function here is intentionally framework-light (no request/response
handling) so it can be unit tested directly and reused from both the staff
UI routes and, eventually, an API/webhook integration.
"""
from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models.job import RepairJob, JobStatus, JobStatusEvent
from app.models.approval import ApprovalRequest
from app.models.base import utcnow
from app.services import sms
from app.services.tokens import generate_approval_token


class SpendingCapExceeded(Exception):
    """Raised when an estimate exceeds the customer's cap and no fresh
    approval covers it. Callers should catch this and route the estimate
    through send_estimate_for_approval() instead of auto-authorizing it."""


def _transition(job, to_status, note=None, actor="system"):
    from_status = job.status.value if job.status else None
    job.status = to_status
    db.session.add(
        JobStatusEvent(
            job_id=job.id, from_status=from_status, to_status=to_status.value,
            note=note, actor=actor,
        )
    )


def estimate_requires_fresh_approval(job, estimate):
    """True if this estimate's total exceeds the customer's spending cap
    and there is no still-valid approval already covering an amount this
    high for this job.

    A "fresh" approval is one that was both (a) approved, and (b) for an
    amount >= the current estimate total. This means a technician can add
    a small additional item under a previously-approved higher estimate
    without re-prompting the customer, but any estimate that pushes the
    total past the cap - or past what was last explicitly approved -
    always requires a new customer sign-off.
    """
    cap = job.customer.spending_cap
    if estimate.total <= cap:
        return False

    for prior in job.approval_requests:
        if (
            prior.response == "approved"
            and prior.estimate_total_at_send >= estimate.total
        ):
            return False
    return True


def send_estimate_for_approval(job, estimate, channel="sms"):
    """Text (or email) the customer the itemized estimate with a one-tap
    approve/decline link, and move the job into WAITING_ON_CUSTOMER.

    Returns the created ApprovalRequest.
    """
    if estimate.status not in {"draft", "sent"}:
        raise ValueError(f"Cannot send an estimate with status {estimate.status!r}")

    now = utcnow()
    ttl_hours = current_app.config["APPROVAL_LINK_TTL_HOURS"]

    approval = ApprovalRequest(
        job_id=job.id,
        estimate_id=estimate.id,
        channel=channel,
        recipient=job.customer.phone_number if channel == "sms" else job.customer.email,
        estimate_total_at_send=estimate.total,
        exceeded_spending_cap=estimate.total > job.customer.spending_cap,
        sent_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
        # Placeholder to satisfy the NOT NULL constraint until we have an id
        # to sign - overwritten below before anything is committed.
        token=f"pending-{now.timestamp()}",
    )
    db.session.add(approval)
    db.session.flush()  # populate approval.id for the token payload

    approval.token = generate_approval_token(approval.id)

    estimate.status = "sent"
    job.waiting_since = now
    _transition(
        job, JobStatus.WAITING_ON_CUSTOMER,
        note=f"Estimate #{estimate.id} (${estimate.total}) sent via {channel}",
        actor="system",
    )

    approval_url = (
        f"{current_app.config['PUBLIC_BASE_URL']}/estimate/{approval.token}"
    )
    if channel == "sms":
        body = sms.build_estimate_sms_body(
            current_app.config["SHOP_NAME"], job, estimate, approval_url
        )
        sms.send_sms(job.customer.phone_number, body)

    db.session.commit()
    return approval


def record_customer_response(approval, decision, ip_address=None, user_agent=None):
    """Apply a customer's tap on the approve/decline link.

    ``decision`` is "approved" or "declined". Idempotent: if this approval
    request has already been answered, the original response is returned
    unchanged rather than overwritten, so a customer double-tapping (or
    reloading) the link can't flip their own answer or corrupt the
    timestamp used for warranty recordkeeping.
    """
    if decision not in {"approved", "declined"}:
        raise ValueError("decision must be 'approved' or 'declined'")

    if not approval.is_pending:
        return approval  # already answered - do not overwrite the record

    now = utcnow()
    approval.responded_at = now
    approval.response = decision
    approval.response_ip = ip_address
    approval.response_user_agent = user_agent

    job = approval.job
    estimate = approval.estimate
    job.waiting_since = None

    if decision == "approved":
        estimate.status = "approved"
        _transition(job, JobStatus.APPROVED, note="Customer approved via link",
                    actor="customer")
    else:
        estimate.status = "declined"
        _transition(job, JobStatus.DECLINED, note="Customer declined via link",
                    actor="customer")

    db.session.commit()
    return approval


def expire_stale_waiting_jobs(as_of=None):
    """Move any job that has sat in WAITING_ON_CUSTOMER past the shop's
    timeout window into EXPIRED, and expire its outstanding approval
    request. Intended to be called by the background scheduler.

    Returns the list of job ids that were expired.
    """
    as_of = as_of or utcnow()
    timeout_hours = current_app.config["WAITING_ON_CUSTOMER_TIMEOUT_HOURS"]
    cutoff = as_of - timedelta(hours=timeout_hours)

    stale_jobs = RepairJob.query.filter(
        RepairJob.status == JobStatus.WAITING_ON_CUSTOMER,
        RepairJob.waiting_since.isnot(None),
        RepairJob.waiting_since <= cutoff,
    ).all()

    expired_ids = []
    for job in stale_jobs:
        job.waiting_since = None
        _transition(
            job, JobStatus.EXPIRED,
            note=f"No customer response within {timeout_hours}h window",
            actor="system",
        )
        pending = [ar for ar in job.approval_requests if ar.is_pending]
        for approval in pending:
            approval.response = None  # left null: "no response", not a decision
            approval.responded_at = None
        if job.current_estimate and job.current_estimate.status == "sent":
            job.current_estimate.status = "expired"
        expired_ids.append(job.id)

    if expired_ids:
        db.session.commit()
    return expired_ids
