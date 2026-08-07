from app.extensions import db
from app.models.base import TimestampMixin


class Technician(db.Model, TimestampMixin):
    __tablename__ = "technicians"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    specialty = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user_account = db.relationship(
        "StaffUser", back_populates="technician", uselist=False
    )
    jobs = db.relationship("RepairJob", back_populates="technician")

    def __repr__(self):
        return f"<Technician {self.full_name}>"
