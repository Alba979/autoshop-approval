from decimal import Decimal

from app.extensions import db
from app.models.base import TimestampMixin


class Estimate(db.Model, TimestampMixin):
    """A parts/labor estimate tied to a job.

    A job can accumulate multiple estimates over time (e.g. the customer
    approves an initial estimate, then the technician finds something else
    mid-repair and issues a revised estimate that must be separately
    approved). ``status`` tracks this specific estimate's own lifecycle,
    while RepairJob.status tracks the job as a whole.
    """

    __tablename__ = "estimates"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("repair_jobs.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="draft")
    # status: "draft" | "sent" | "approved" | "declined" | "expired" | "superseded"

    tax_rate = db.Column(db.Numeric(5, 4), nullable=False, default=Decimal("0.0000"))

    job = db.relationship("RepairJob", back_populates="estimates")
    line_items = db.relationship(
        "EstimateLineItem", back_populates="estimate", cascade="all, delete-orphan"
    )
    approval_requests = db.relationship("ApprovalRequest", back_populates="estimate")

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.line_items), Decimal("0.00"))

    @property
    def tax_amount(self):
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"))

    @property
    def total(self):
        return self.subtotal + self.tax_amount

    def __repr__(self):
        return f"<Estimate #{self.id} for job {self.job_id} (${self.total})>"


class EstimateLineItem(db.Model, TimestampMixin):
    __tablename__ = "estimate_line_items"

    id = db.Column(db.Integer, primary_key=True)
    estimate_id = db.Column(db.Integer, db.ForeignKey("estimates.id"), nullable=False)

    kind = db.Column(db.String(10), nullable=False)  # "part" | "labor"
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("1.00"))
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))

    estimate = db.relationship("Estimate", back_populates="line_items")

    @property
    def line_total(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    def __repr__(self):
        return f"<LineItem {self.kind}: {self.description} x{self.quantity}>"
