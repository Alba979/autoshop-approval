from app.extensions import db
from app.models.base import TimestampMixin


class Customer(db.Model, TimestampMixin):
    """A shop customer.

    ``spending_cap`` is the ceiling the customer has told the shop not to
    exceed without a fresh, explicit approval. It defaults to the shop-wide
    default but can be set per customer (e.g. a fleet manager might set a
    much higher cap, or a budget-conscious customer a lower one).
    """

    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)

    spending_cap = db.Column(db.Numeric(10, 2), nullable=False, default=500.00)
    notes = db.Column(db.Text, nullable=True)

    vehicles = db.relationship(
        "Vehicle", back_populates="customer", cascade="all, delete-orphan"
    )
    jobs = db.relationship("RepairJob", back_populates="customer")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<Customer {self.full_name}>"
