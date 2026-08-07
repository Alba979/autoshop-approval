from app.extensions import db
from app.models.base import TimestampMixin


class Vehicle(db.Model, TimestampMixin):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)

    year = db.Column(db.Integer, nullable=False)
    make = db.Column(db.String(60), nullable=False)
    model = db.Column(db.String(60), nullable=False)
    vin = db.Column(db.String(17), nullable=True, unique=True)
    license_plate = db.Column(db.String(20), nullable=True)
    mileage = db.Column(db.Integer, nullable=True)

    customer = db.relationship("Customer", back_populates="vehicles")
    jobs = db.relationship("RepairJob", back_populates="vehicle")

    @property
    def display_name(self):
        return f"{self.year} {self.make} {self.model}"

    def __repr__(self):
        return f"<Vehicle {self.display_name}>"
