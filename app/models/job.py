import enum

from app.extensions import db
from app.models.base import TimestampMixin


class JobStatus(str, enum.Enum):
    """Lifecycle of a repair order.

    NEW                 -> intake created, no diagnosis yet
    DIAGNOSING          -> technician is actively inspecting the vehicle
    WAITING_ON_CUSTOMER -> an estimate has been sent, awaiting approve/decline
    APPROVED            -> customer approved; work is authorized to start
    IN_PROGRESS         -> technician is performing the approved repair
    DECLINED            -> customer declined the estimate; job closed out
    EXPIRED             -> customer never responded within the timeout window
    COMPLETED           -> repair finished, final invoice recorded
    CANCELLED           -> shop or customer cancelled the job outright
    """

    NEW = "new"
    DIAGNOSING = "diagnosing"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    DECLINED = "declined"
    EXPIRED = "expired"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# States from which work is authorized to proceed.
ACTIVE_WORK_STATES = {JobStatus.APPROVED, JobStatus.IN_PROGRESS}

# Terminal states - nothing else should change once a job reaches these.
TERMINAL_STATES = {
    JobStatus.DECLINED,
    JobStatus.EXPIRED,
    JobStatus.COMPLETED,
    JobStatus.CANCELLED,
}


class RepairJob(db.Model, TimestampMixin):
    __tablename__ = "repair_jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_number = db.Column(db.String(20), unique=True, nullable=False, index=True)

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    technician_id = db.Column(
        db.Integer, db.ForeignKey("technicians.id"), nullable=True
    )

    status = db.Column(
        db.Enum(JobStatus), nullable=False, default=JobStatus.NEW, index=True
    )
    customer_concern = db.Column(db.Text, nullable=True)

    # Set the moment an estimate is texted out; cleared once the customer
    # responds or the job leaves WAITING_ON_CUSTOMER for any reason. The
    # scheduled job in services/scheduler_jobs.py uses this to find jobs
    # that have gone quiet longer than WAITING_ON_CUSTOMER_TIMEOUT_HOURS.
    waiting_since = db.Column(db.DateTime(), nullable=True)

    # Final invoice total once work is completed - compared against the
    # approved estimate total to compute cost variance per technician.
    final_cost = db.Column(db.Numeric(10, 2), nullable=True)
    completed_at = db.Column(db.DateTime(), nullable=True)

    customer = db.relationship("Customer", back_populates="jobs")
    vehicle = db.relationship("Vehicle", back_populates="jobs")
    technician = db.relationship("Technician", back_populates="jobs")

    findings = db.relationship(
        "DiagnosticFinding", back_populates="job", cascade="all, delete-orphan"
    )
    estimates = db.relationship(
        "Estimate",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Estimate.created_at.desc()",
    )
    approval_requests = db.relationship(
        "ApprovalRequest",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ApprovalRequest.created_at.desc()",
    )
    status_events = db.relationship(
        "JobStatusEvent",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobStatusEvent.created_at",
    )

    @property
    def current_estimate(self):
        """Most recent estimate, regardless of its approval state."""
        return self.estimates[0] if self.estimates else None

    @property
    def latest_approved_estimate(self):
        for estimate in self.estimates:
            if estimate.status == "approved":
                return estimate
        return None

    def __repr__(self):
        return f"<RepairJob {self.job_number} [{self.status.value}]>"


class JobStatusEvent(db.Model, TimestampMixin):
    """Immutable audit trail of every status transition on a job.

    This, together with DiagnosticPhoto and ApprovalRequest timestamps, is
    what the shop pulls up if a customer disputes a warranty claim - it
    proves exactly what was found, what was quoted, when it was approved,
    and by what channel.
    """

    __tablename__ = "job_status_events"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("repair_jobs.id"), nullable=False)
    from_status = db.Column(db.String(30), nullable=True)
    to_status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    actor = db.Column(db.String(120), nullable=True)  # "system", staff name, "customer"

    job = db.relationship("RepairJob", back_populates="status_events")
