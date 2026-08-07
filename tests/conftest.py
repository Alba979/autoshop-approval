import pytest

from app import create_app
from app.extensions import db as _db
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.technician import Technician
from app.models.job import RepairJob, JobStatus
from app.models.estimate import Estimate, EstimateLineItem
from decimal import Decimal


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_job(db):
    customer = Customer(
        first_name="Test", last_name="Customer", phone_number="+15555550199",
        email="test@example.com", spending_cap=Decimal("400.00"),
    )
    db.session.add(customer)
    db.session.flush()

    vehicle = Vehicle(customer_id=customer.id, year=2020, make="Toyota", model="Corolla")
    db.session.add(vehicle)

    technician = Technician(full_name="Test Tech")
    db.session.add(technician)
    db.session.flush()

    job = RepairJob(
        job_number="RO-TEST-0001", customer_id=customer.id, vehicle_id=vehicle.id,
        technician_id=technician.id, status=JobStatus.DIAGNOSING,
    )
    db.session.add(job)
    db.session.commit()
    return job


def make_estimate(db, job, total_before_tax, tax_rate=Decimal("0.00")):
    estimate = Estimate(job_id=job.id, status="draft", tax_rate=tax_rate)
    db.session.add(estimate)
    db.session.flush()
    db.session.add(EstimateLineItem(
        estimate_id=estimate.id, kind="part", description="Test part",
        quantity=Decimal("1"), unit_price=Decimal(str(total_before_tax)),
    ))
    db.session.commit()
    return estimate
