from app.extensions import db
from app.models.base import TimestampMixin


class ApprovalRequest(db.Model, TimestampMixin):
    """One outbound "please approve this estimate" request to a customer.

    Each request carries a unique, signed token that resolves to a one-tap
    approve/decline page (see routes/customer.py and services/tokens.py).
    ``sent_at`` and ``responded_at`` are the two timestamps the analytics
    dashboard uses to compute approval turnaround time, and are also kept
    permanently for warranty-dispute recordkeeping - they are never
    overwritten or deleted, only appended to via new ApprovalRequest rows.
    """

    __tablename__ = "approval_requests"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("repair_jobs.id"), nullable=False)
    estimate_id = db.Column(db.Integer, db.ForeignKey("estimates.id"), nullable=False)

    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    channel = db.Column(db.String(10), nullable=False, default="sms")  # "sms"|"email"
    recipient = db.Column(db.String(255), nullable=False)

    estimate_total_at_send = db.Column(db.Numeric(10, 2), nullable=False)
    exceeded_spending_cap = db.Column(db.Boolean, nullable=False, default=False)

    sent_at = db.Column(db.DateTime(), nullable=False)
    expires_at = db.Column(db.DateTime(), nullable=False)
    responded_at = db.Column(db.DateTime(), nullable=True)

    response = db.Column(db.String(10), nullable=True)  # "approved" | "declined"
    response_ip = db.Column(db.String(45), nullable=True)
    response_user_agent = db.Column(db.String(255), nullable=True)

    job = db.relationship("RepairJob", back_populates="approval_requests")
    estimate = db.relationship("Estimate", back_populates="approval_requests")

    @property
    def is_pending(self):
        return self.responded_at is None

    @property
    def turnaround(self):
        """Time between sending the estimate and the customer's response."""
        if self.responded_at is None:
            return None
        return self.responded_at - self.sent_at

    def __repr__(self):
        return f"<ApprovalRequest job={self.job_id} response={self.response}>"
