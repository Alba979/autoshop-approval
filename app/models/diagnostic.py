from app.extensions import db
from app.models.base import TimestampMixin


class DiagnosticFinding(db.Model, TimestampMixin):
    """A single issue the technician found during inspection.

    Multiple findings can back one estimate (e.g. "worn front pads" and
    "leaking rear seal" both roll into the same customer-facing estimate).
    """

    __tablename__ = "diagnostic_findings"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("repair_jobs.id"), nullable=False)
    technician_id = db.Column(
        db.Integer, db.ForeignKey("technicians.id"), nullable=True
    )

    system_area = db.Column(db.String(80), nullable=False)  # e.g. "Brakes", "Cooling"
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="recommended")
    # severity: "urgent" | "recommended" | "monitor"

    job = db.relationship("RepairJob", back_populates="findings")
    technician = db.relationship("Technician")
    photos = db.relationship(
        "DiagnosticPhoto", back_populates="finding", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<DiagnosticFinding {self.system_area}: {self.description[:30]}>"


class DiagnosticPhoto(db.Model, TimestampMixin):
    """A permanently retained photo backing a diagnostic finding.

    Files are never deleted through the application - see
    services/photo_storage.py. Retaining the capture timestamp and the
    technician who took it is what makes this useful evidence in a
    warranty dispute months later.
    """

    __tablename__ = "diagnostic_photos"

    id = db.Column(db.Integer, primary_key=True)
    finding_id = db.Column(
        db.Integer, db.ForeignKey("diagnostic_findings.id"), nullable=False
    )
    storage_backend = db.Column(db.String(20), nullable=False, default="local")
    storage_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=True)
    file_size_bytes = db.Column(db.Integer, nullable=True)
    captured_at = db.Column(db.DateTime(), nullable=False)

    finding = db.relationship("DiagnosticFinding", back_populates="photos")

    def __repr__(self):
        return f"<DiagnosticPhoto {self.original_filename}>"
