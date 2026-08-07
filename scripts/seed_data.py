"""
Seeds the database with realistic sample data for local development, demos,
and manual QA: a shop with a few staff accounts, technicians, customers,
vehicles, and repair jobs spanning every stage of the diagnostic-to-repair
workflow (including one job past its "waiting on customer" timeout and a
couple of completed jobs with estimate-vs-final variance to look at on the
Analytics page).

Usage:
    flask --app wsgi.py seed-db          # via the CLI command registered below
    python scripts/seed_data.py          # or run directly

Safe to re-run: it wipes and recreates all tables first.
"""
import base64
import os
import sys
from datetime import timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import StaffUser
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.technician import Technician
from app.models.job import RepairJob, JobStatus, JobStatusEvent
from app.models.diagnostic import DiagnosticFinding, DiagnosticPhoto
from app.models.estimate import Estimate, EstimateLineItem
from app.models.approval import ApprovalRequest
from app.models.base import utcnow
from app.services.tokens import generate_approval_token

# A tiny (1x1 px) valid JPEG, used as placeholder bytes for seeded diagnostic
# photos so the app has real files on disk to serve without shipping large
# binary assets in the repo.
_PLACEHOLDER_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI"
    "CQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAAAv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
)


def _placeholder_photo_bytes():
    return base64.b64decode(_PLACEHOLDER_JPEG_B64)


def run_seed():
    app = create_app("development")
    with app.app_context():
        print("Dropping and recreating all tables...")
        db.drop_all()
        db.create_all()

        now = utcnow()

        # ---------------------------------------------------------------
        # Technicians + staff logins
        # ---------------------------------------------------------------
        tech_marcus = Technician(full_name="Marcus Alvarado", specialty="Brakes & Suspension")
        tech_priya = Technician(full_name="Priya Nair", specialty="Engine Diagnostics")
        tech_dan = Technician(full_name="Dan Okafor", specialty="Electrical")
        db.session.add_all([tech_marcus, tech_priya, tech_dan])
        db.session.flush()

        owner = StaffUser(full_name="Sam Whitfield", email="owner@ridgelineauto.example", role="owner")
        owner.set_password("ShopOwner!2026")

        writer = StaffUser(
            full_name="Jordan Reyes", email="frontdesk@ridgelineauto.example", role="service_writer"
        )
        writer.set_password("FrontDesk!2026")

        tech_login_marcus = StaffUser(
            full_name="Marcus Alvarado", email="marcus@ridgelineauto.example",
            role="technician", technician_id=tech_marcus.id,
        )
        tech_login_marcus.set_password("Technician!2026")

        db.session.add_all([owner, writer, tech_login_marcus])

        # ---------------------------------------------------------------
        # Customers + vehicles
        # ---------------------------------------------------------------
        customers_data = [
            dict(first_name="Elena", last_name="Ramos", phone_number="+15555550101",
                 email="elena.ramos@example.com", spending_cap=Decimal("400.00"),
                 vehicle=dict(year=2016, make="Honda", model="Civic", vin="2HGFC2F59GH512345",
                              license_plate="7KLM901", mileage=98200)),
            dict(first_name="Trevor", last_name="Bishop", phone_number="+15555550102",
                 email="trevor.bishop@example.com", spending_cap=Decimal("750.00"),
                 vehicle=dict(year=2019, make="Ford", model="F-150", vin="1FTEW1EP5KFA10234",
                              license_plate="9PTB214", mileage=54300)),
            dict(first_name="Grace", last_name="Kim", phone_number="+15555550103",
                 email="grace.kim@example.com", spending_cap=Decimal("500.00"),
                 vehicle=dict(year=2021, make="Toyota", model="RAV4", vin="2T3H1RFV0MW123456",
                              license_plate="4GKX773", mileage=21100)),
            dict(first_name="Omar", last_name="Farouk", phone_number="+15555550104",
                 email="omar.farouk@example.com", spending_cap=Decimal("300.00"),
                 vehicle=dict(year=2014, make="Subaru", model="Outback", vin="4S4BRBAC7E3123456",
                              license_plate="2QWE556", mileage=142000)),
            dict(first_name="Lindsay", last_name="Park", phone_number="+15555550105",
                 email="lindsay.park@example.com", spending_cap=Decimal("600.00"),
                 vehicle=dict(year=2018, make="Chevrolet", model="Malibu", vin="1G1ZD5ST9JF123456",
                              license_plate="6RTY882", mileage=67500)),
            dict(first_name="Marcus", last_name="Diallo", phone_number="+15555550106",
                 email="marcus.diallo@example.com", spending_cap=Decimal("450.00"),
                 vehicle=dict(year=2020, make="Nissan", model="Altima", vin="1N4BL4BV3LC123456",
                              license_plate="3ASD990", mileage=32800)),
        ]

        customers = {}
        vehicles = {}
        for data in customers_data:
            v = data.pop("vehicle")
            customer = Customer(**data)
            db.session.add(customer)
            db.session.flush()
            vehicle = Vehicle(customer_id=customer.id, **v)
            db.session.add(vehicle)
            db.session.flush()
            customers[customer.first_name] = customer
            vehicles[customer.first_name] = vehicle

        db.session.commit()

        # ---------------------------------------------------------------
        # Helper to build a job + findings + estimate consistently
        # ---------------------------------------------------------------
        def make_job(customer_name, technician, concern, findings, line_items,
                     job_number_suffix, tax_rate=Decimal("0.0825")):
            customer = customers[customer_name]
            vehicle = vehicles[customer_name]
            job = RepairJob(
                job_number=f"RO-2026-{job_number_suffix:04d}",
                customer_id=customer.id,
                vehicle_id=vehicle.id,
                technician_id=technician.id if technician else None,
                customer_concern=concern,
                status=JobStatus.DIAGNOSING,
            )
            db.session.add(job)
            db.session.flush()
            db.session.add(JobStatusEvent(job_id=job.id, from_status=None,
                                           to_status="new", note="Vehicle checked in",
                                           actor=writer.full_name))
            db.session.add(JobStatusEvent(job_id=job.id, from_status="new",
                                           to_status="diagnosing",
                                           note="Technician began inspection",
                                           actor=technician.full_name if technician else "system"))

            for f in findings:
                finding = DiagnosticFinding(
                    job_id=job.id, technician_id=technician.id if technician else None,
                    system_area=f["area"], description=f["description"],
                    severity=f["severity"],
                )
                db.session.add(finding)
                db.session.flush()
                if f.get("photo"):
                    photo_dir = os.path.join(app.config["UPLOAD_FOLDER"], job.job_number)
                    os.makedirs(photo_dir, exist_ok=True)
                    filename = f"{finding.id}_{f['area'].lower().replace(' ', '_')}.jpg"
                    full_path = os.path.join(photo_dir, filename)
                    with open(full_path, "wb") as fh:
                        fh.write(_placeholder_photo_bytes())
                    db.session.add(DiagnosticPhoto(
                        finding_id=finding.id, storage_backend="local",
                        storage_path=os.path.join(job.job_number, filename),
                        original_filename=filename, content_type="image/jpeg",
                        file_size_bytes=os.path.getsize(full_path),
                        captured_at=now - timedelta(days=job_number_suffix % 10, hours=2),
                    ))

            estimate = Estimate(job_id=job.id, status="draft", tax_rate=tax_rate)
            db.session.add(estimate)
            db.session.flush()
            for li in line_items:
                db.session.add(EstimateLineItem(
                    estimate_id=estimate.id, kind=li["kind"],
                    description=li["description"], quantity=Decimal(str(li["quantity"])),
                    unit_price=Decimal(str(li["unit_price"])),
                ))
            db.session.flush()
            return job, estimate

        # ---------------------------------------------------------------
        # Job 1: NEW / freshly diagnosing, no estimate sent yet
        # ---------------------------------------------------------------
        job1, est1 = make_job(
            "Omar", tech_dan, "Dashboard battery light stays on",
            findings=[dict(area="Charging System", severity="urgent",
                           description="Alternator output tests at 11.2V under load, below spec. "
                                        "Serpentine belt also glazed and due for replacement.",
                           photo=True)],
            line_items=[
                dict(kind="part", description="Alternator, remanufactured", quantity=1, unit_price=210.00),
                dict(kind="part", description="Serpentine belt", quantity=1, unit_price=38.00),
                dict(kind="labor", description="Alternator + belt replacement", quantity=1.5, unit_price=120.00),
            ],
            job_number_suffix=1,
        )
        job1.status = JobStatus.DIAGNOSING

        # ---------------------------------------------------------------
        # Job 2: WAITING_ON_CUSTOMER, within the timeout window, UNDER cap
        # ---------------------------------------------------------------
        job2, est2 = make_job(
            "Grace", tech_marcus, "30,000 mile service + odd noise from front end",
            findings=[
                dict(area="Suspension", severity="recommended",
                     description="Front sway bar end links have play; clunking noise over bumps confirmed on test drive.",
                     photo=True),
                dict(area="Maintenance", severity="monitor",
                     description="Cabin air filter heavily soiled.", photo=False),
            ],
            line_items=[
                dict(kind="part", description="Sway bar end links (pair)", quantity=1, unit_price=64.00),
                dict(kind="part", description="Cabin air filter", quantity=1, unit_price=22.00),
                dict(kind="labor", description="End link replacement + filter swap", quantity=1.0, unit_price=110.00),
            ],
            job_number_suffix=2,
        )
        sent_at = now - timedelta(hours=5)
        est2.status = "sent"
        job2.status = JobStatus.WAITING_ON_CUSTOMER
        job2.waiting_since = sent_at
        approval2 = ApprovalRequest(
            job_id=job2.id, estimate_id=est2.id, channel="sms",
            recipient=job2.customer.phone_number, estimate_total_at_send=est2.total,
            exceeded_spending_cap=est2.total > job2.customer.spending_cap,
            sent_at=sent_at, expires_at=sent_at + timedelta(hours=72),
            token="",
        )
        db.session.add(approval2)
        db.session.flush()
        approval2.token = generate_approval_token(approval2.id)

        # ---------------------------------------------------------------
        # Job 3: WAITING_ON_CUSTOMER, OVER cap, still within window
        # ---------------------------------------------------------------
        job3, est3 = make_job(
            "Elena", tech_priya, "Grinding noise when braking",
            findings=[dict(area="Brakes", severity="urgent",
                           description="Front pads worn to 2mm, rotors scored beyond machining tolerance. "
                                        "Rear pads at 5mm, within spec.",
                           photo=True)],
            line_items=[
                dict(kind="part", description="Front brake pads (ceramic)", quantity=1, unit_price=68.00),
                dict(kind="part", description="Front rotors (pair)", quantity=1, unit_price=145.00),
                dict(kind="labor", description="Front brake job", quantity=1.5, unit_price=130.00),
            ],
            job_number_suffix=3,
        )
        sent_at3 = now - timedelta(hours=8)
        est3.status = "sent"
        job3.status = JobStatus.WAITING_ON_CUSTOMER
        job3.waiting_since = sent_at3
        approval3 = ApprovalRequest(
            job_id=job3.id, estimate_id=est3.id, channel="sms",
            recipient=job3.customer.phone_number, estimate_total_at_send=est3.total,
            exceeded_spending_cap=est3.total > job3.customer.spending_cap,
            sent_at=sent_at3, expires_at=sent_at3 + timedelta(hours=72), token="",
        )
        db.session.add(approval3)
        db.session.flush()
        approval3.token = generate_approval_token(approval3.id)

        # ---------------------------------------------------------------
        # Job 4: EXPIRED - sent, customer never responded, past timeout
        # ---------------------------------------------------------------
        job4, est4 = make_job(
            "Marcus", tech_dan, "Check engine light, rough idle",
            findings=[dict(area="Ignition", severity="recommended",
                           description="Cylinder 3 misfire (P0303). Spark plugs original at 32k miles.",
                           photo=False)],
            line_items=[
                dict(kind="part", description="Spark plug set (4)", quantity=1, unit_price=48.00),
                dict(kind="labor", description="Diagnostic + spark plug replacement", quantity=1.0, unit_price=95.00),
            ],
            job_number_suffix=4,
        )
        sent_at4 = now - timedelta(days=4)
        est4.status = "expired"
        job4.status = JobStatus.EXPIRED
        job4.waiting_since = None
        approval4 = ApprovalRequest(
            job_id=job4.id, estimate_id=est4.id, channel="sms",
            recipient=job4.customer.phone_number, estimate_total_at_send=est4.total,
            exceeded_spending_cap=False,
            sent_at=sent_at4, expires_at=sent_at4 + timedelta(hours=72), token="",
            response=None, responded_at=None,
        )
        db.session.add(approval4)
        db.session.flush()
        approval4.token = generate_approval_token(approval4.id)
        db.session.add(JobStatusEvent(
            job_id=job4.id, from_status="waiting_on_customer", to_status="expired",
            note="No customer response within 24h window", actor="system",
        ))

        # ---------------------------------------------------------------
        # Job 5: DECLINED
        # ---------------------------------------------------------------
        job5, est5 = make_job(
            "Lindsay", tech_priya, "Rattling under the car",
            findings=[dict(area="Exhaust", severity="monitor",
                           description="Heat shield loose, rattling at idle. Cosmetic/noise only, no leak detected.",
                           photo=True)],
            line_items=[
                dict(kind="labor", description="Heat shield re-secure / replace clips", quantity=0.5, unit_price=90.00)],
            job_number_suffix=5,
        )
        sent_at5 = now - timedelta(days=2)
        responded_at5 = sent_at5 + timedelta(hours=3)
        est5.status = "declined"
        job5.status = JobStatus.DECLINED
        job5.waiting_since = None
        approval5 = ApprovalRequest(
            job_id=job5.id, estimate_id=est5.id, channel="sms",
            recipient=job5.customer.phone_number, estimate_total_at_send=est5.total,
            exceeded_spending_cap=False, sent_at=sent_at5,
            expires_at=sent_at5 + timedelta(hours=72), token="",
            response="declined", responded_at=responded_at5,
            response_ip="203.0.113.44",
        )
        db.session.add(approval5)
        db.session.flush()
        approval5.token = generate_approval_token(approval5.id)

        # ---------------------------------------------------------------
        # Jobs 6-9: COMPLETED, with a spread of estimate-vs-final variance
        # so the analytics charts have something to show.
        # ---------------------------------------------------------------
        def make_completed_job(customer_name, technician, concern, findings, line_items,
                                job_number_suffix, final_cost, days_ago):
            job, est = make_job(customer_name, technician, concern, findings, line_items,
                                 job_number_suffix)
            sent_at = now - timedelta(days=days_ago, hours=6)
            responded_at = sent_at + timedelta(hours=[1.5, 4, 0.5, 6][job_number_suffix % 4])
            est.status = "approved"
            approval = ApprovalRequest(
                job_id=job.id, estimate_id=est.id, channel="sms",
                recipient=job.customer.phone_number, estimate_total_at_send=est.total,
                exceeded_spending_cap=est.total > job.customer.spending_cap,
                sent_at=sent_at, expires_at=sent_at + timedelta(hours=72), token="",
                response="approved", responded_at=responded_at,
                response_ip="198.51.100.23",
            )
            db.session.add(approval)
            db.session.flush()
            approval.token = generate_approval_token(approval.id)

            job.status = JobStatus.COMPLETED
            job.waiting_since = None
            job.final_cost = Decimal(str(final_cost))
            job.completed_at = responded_at + timedelta(days=1)
            for evt_status in ["approved", "in_progress", "completed"]:
                db.session.add(JobStatusEvent(
                    job_id=job.id, from_status=None, to_status=evt_status,
                    note="Seeded historical event", actor=technician.full_name if technician else "system",
                ))
            return job, est

        make_completed_job(
            "Trevor", tech_marcus, "Front end shakes at highway speed",
            findings=[dict(area="Suspension", severity="urgent",
                           description="Two front tires cupped; struts leaking oil.", photo=True)],
            line_items=[
                dict(kind="part", description="Front struts (pair)", quantity=1, unit_price=240.00),
                dict(kind="part", description="Alignment", quantity=1, unit_price=0.00),
                dict(kind="labor", description="Strut replacement + 4-wheel alignment", quantity=2.5, unit_price=130.00),
            ],
            job_number_suffix=6, final_cost=612.40, days_ago=18,
        )

        make_completed_job(
            "Grace", tech_priya, "AC not cold",
            findings=[dict(area="Climate Control", severity="recommended",
                           description="Low refrigerant charge, small leak at condenser fitting.", photo=False)],
            line_items=[
                dict(kind="part", description="O-ring kit", quantity=1, unit_price=14.00),
                dict(kind="part", description="Refrigerant (R1234yf)", quantity=2, unit_price=45.00),
                dict(kind="labor", description="AC leak repair + recharge", quantity=1.5, unit_price=115.00),
            ],
            job_number_suffix=7, final_cost=299.50, days_ago=25,
        )

        make_completed_job(
            "Omar", tech_dan, "Won't start intermittently",
            findings=[dict(area="Electrical", severity="urgent",
                           description="Battery terminal corrosion causing intermittent connection; battery itself tests weak.",
                           photo=True)],
            line_items=[
                dict(kind="part", description="Battery, 12V AGM", quantity=1, unit_price=175.00),
                dict(kind="labor", description="Battery replacement + terminal cleaning", quantity=0.5, unit_price=80.00),
            ],
            job_number_suffix=8, final_cost=298.60, days_ago=32,
        )

        # This one ran over the approved estimate - useful to show a
        # positive-variance outlier on the technician chart.
        make_completed_job(
            "Lindsay", tech_marcus, "Transmission slipping under load",
            findings=[dict(area="Transmission", severity="urgent",
                           description="Fluid burnt and low; slippage confirmed 2nd-3rd gear on road test.",
                           photo=True)],
            line_items=[
                dict(kind="part", description="Transmission fluid + filter kit", quantity=1, unit_price=95.00),
                dict(kind="labor", description="Fluid/filter service", quantity=1.5, unit_price=120.00),
            ],
            job_number_suffix=9, final_cost=430.00, days_ago=10,
        )

        db.session.commit()

        print("Seed complete.")
        print(f"  Staff users:     {StaffUser.query.count()}")
        print(f"  Technicians:     {Technician.query.count()}")
        print(f"  Customers:       {Customer.query.count()}")
        print(f"  Vehicles:        {Vehicle.query.count()}")
        print(f"  Repair jobs:     {RepairJob.query.count()}")
        print(f"  Diagnostic photos: {DiagnosticPhoto.query.count()}")
        print()
        print("Demo staff logins:")
        print("  owner@ridgelineauto.example      / ShopOwner!2026")
        print("  frontdesk@ridgelineauto.example  / FrontDesk!2026")
        print("  marcus@ridgelineauto.example      / Technician!2026")
        print()
        print("Sample customer approval links (also visible on each job's detail page):")
        for label, approval in [("Grace - within cap", approval2), ("Elena - OVER cap", approval3)]:
            print(f"  {label}: /estimate/{approval.token}")


if __name__ == "__main__":
    run_seed()
