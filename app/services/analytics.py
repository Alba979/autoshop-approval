"""
Reporting queries backing the analytics dashboard:
  1. Average approval turnaround time (sent -> customer response), per
     technician who performed the diagnosis on the job.
  2. Estimate-to-final-cost variance: how far the final invoice drifted
     from the approved estimate, per technician.

Kept as plain Python aggregation over ORM objects rather than raw SQL
aggregates - shop data volumes are small (hundreds to low thousands of
jobs/year) so this stays simple and easy to reason about, and easy to port
to a proper SQL aggregate later if a shop's data outgrows it.
"""
from collections import defaultdict
from decimal import Decimal

from app.models.job import RepairJob, JobStatus


def _technician_label(technician):
    return technician.full_name if technician else "Unassigned"


def approval_turnaround_by_technician():
    """Return a list of dicts: technician, avg_turnaround_hours, sample_size.

    Only approval requests that actually received a response are counted -
    an expired (unanswered) request has no turnaround to measure.
    """
    buckets = defaultdict(list)

    for job in RepairJob.query.all():
        label = _technician_label(job.technician)
        for approval in job.approval_requests:
            if approval.turnaround is not None:
                buckets[label].append(approval.turnaround.total_seconds() / 3600.0)

    results = []
    for label, samples in buckets.items():
        avg_hours = sum(samples) / len(samples)  # samples is never empty here
        results.append(
            {
                "technician": label,
                "avg_turnaround_hours": round(avg_hours, 2),
                "sample_size": len(samples),
            }
        )
    results.sort(key=lambda r: r["technician"])
    return results


def estimate_vs_final_variance_by_technician():
    """Return a list of dicts: technician, avg_variance_pct, avg_variance_dollars,
    sample_size - comparing each completed job's final_cost against the
    total of the estimate the customer actually approved.

    Positive variance means the shop ended up billing more than what was
    approved (a red flag worth investigating - approved change orders
    should show up as a new estimate, not silently inflate the final
    invoice); negative means the job came in under the approved estimate.
    """
    buckets = defaultdict(list)

    completed_jobs = RepairJob.query.filter(
        RepairJob.status == JobStatus.COMPLETED, RepairJob.final_cost.isnot(None)
    ).all()

    for job in completed_jobs:
        approved_estimate = job.latest_approved_estimate
        if approved_estimate is None:
            continue
        approved_total = approved_estimate.total
        if approved_total == 0:
            continue

        variance_dollars = job.final_cost - approved_total
        variance_pct = (variance_dollars / approved_total) * Decimal("100")

        label = _technician_label(job.technician)
        buckets[label].append(
            {"dollars": float(variance_dollars), "pct": float(variance_pct)}
        )

    results = []
    for label, samples in buckets.items():
        avg_dollars = sum(s["dollars"] for s in samples) / len(samples)
        avg_pct = sum(s["pct"] for s in samples) / len(samples)
        results.append(
            {
                "technician": label,
                "avg_variance_dollars": round(avg_dollars, 2),
                "avg_variance_pct": round(avg_pct, 2),
                "sample_size": len(samples),
            }
        )
    results.sort(key=lambda r: r["technician"])
    return results


def shop_summary():
    """A handful of headline numbers for the top of the analytics page."""
    all_jobs = RepairJob.query.all()
    total_jobs = len(all_jobs)
    by_status = defaultdict(int)
    for job in all_jobs:
        by_status[job.status.value] += 1

    answered = [
        ar
        for job in all_jobs
        for ar in job.approval_requests
        if ar.turnaround is not None
    ]
    overall_avg_turnaround = (
        round(
            sum(a.turnaround.total_seconds() / 3600.0 for a in answered)
            / len(answered),
            2,
        )
        if answered
        else None
    )

    return {
        "total_jobs": total_jobs,
        "by_status": dict(by_status),
        "overall_avg_turnaround_hours": overall_avg_turnaround,
        "answered_approval_count": len(answered),
    }
