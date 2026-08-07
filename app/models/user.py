from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin


class StaffUser(db.Model, UserMixin, TimestampMixin):
    """A shop employee who can log into the internal dashboard.

    Kept separate from Technician (below) because not every staff login is a
    wrench-turning technician (e.g. a service writer), and not every
    technician necessarily has a login. A StaffUser may optionally be linked
    to a Technician profile for attribution on jobs.
    """

    __tablename__ = "staff_users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="service_writer")
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)

    technician_id = db.Column(db.Integer, db.ForeignKey("technicians.id"), nullable=True)
    technician = db.relationship("Technician", back_populates="user_account")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active(self):
        return self.is_active_user

    def __repr__(self):
        return f"<StaffUser {self.email} ({self.role})>"
