"""Human-friendly, sequential job numbers (e.g. RO-2026-0001).

Sequential per calendar year so shop staff can eyeball roughly how many
jobs have come through this year, mirroring how most shop management
systems label repair orders (RO = "Repair Order").
"""
from app.extensions import db
from app.models.job import RepairJob
from app.models.base import utcnow


def next_job_number():
    year = utcnow().year
    prefix = f"RO-{year}-"

    count = (
        db.session.query(RepairJob)
        .filter(RepairJob.job_number.like(f"{prefix}%"))
        .count()
    )
    return f"{prefix}{count + 1:04d}"
