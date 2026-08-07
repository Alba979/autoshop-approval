import os
from decimal import Decimal

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    send_from_directory, current_app, abort,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.forms import (
    LoginForm, NewJobForm, DiagnosticFindingForm, EstimateLineItemForm,
    SendEstimateForm, NewCustomerForm, NewVehicleForm, CompleteJobForm,
)
from app.models.user import StaffUser
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.technician import Technician
from app.models.job import RepairJob, JobStatus
from app.models.diagnostic import DiagnosticFinding, DiagnosticPhoto
from app.models.estimate import Estimate, EstimateLineItem
from app.models.base import utcnow
from app.services.approval_workflow import (
    estimate_requires_fresh_approval, send_estimate_for_approval,
)
from app.services.photo_storage import save_diagnostic_photo, photo_url
from app.utils.numbering import next_job_number

staff_bp = Blueprint("staff", __name__, url_prefix="")


@staff_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("staff.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = StaffUser.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.full_name}.", "success")
            next_url = request.args.get("next") or url_for("staff.dashboard")
            return redirect(next_url)
        flash("Invalid email or password.", "danger")
    return render_template("staff/login.html", form=form)


@staff_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("staff.login"))


@staff_bp.route("/")
@login_required
def dashboard():
    active_statuses = [
        JobStatus.NEW, JobStatus.DIAGNOSING, JobStatus.WAITING_ON_CUSTOMER,
        JobStatus.APPROVED, JobStatus.IN_PROGRESS,
    ]
    active_jobs = (
        RepairJob.query.filter(RepairJob.status.in_(active_statuses))
        .order_by(RepairJob.created_at.desc())
        .all()
    )
    waiting_count = sum(1 for j in active_jobs if j.status == JobStatus.WAITING_ON_CUSTOMER)
    return render_template(
        "staff/dashboard.html", jobs=active_jobs, waiting_count=waiting_count
    )


@staff_bp.route("/jobs/history")
@login_required
def job_history():
    closed_statuses = [
        JobStatus.DECLINED, JobStatus.EXPIRED, JobStatus.COMPLETED, JobStatus.CANCELLED,
    ]
    jobs = (
        RepairJob.query.filter(RepairJob.status.in_(closed_statuses))
        .order_by(RepairJob.updated_at.desc())
        .limit(200)
        .all()
    )
    return render_template("staff/job_history.html", jobs=jobs)


@staff_bp.route("/jobs/new", methods=["GET", "POST"])
@login_required
def new_job():
    form = NewJobForm()
    form.customer_id.choices = [
        (c.id, c.full_name) for c in Customer.query.order_by(Customer.last_name).all()
    ]
    form.vehicle_id.choices = [
        (v.id, f"{v.display_name} ({v.customer.full_name})")
        for v in Vehicle.query.all()
    ]
    form.technician_id.choices = [(0, "Unassigned")] + [
        (t.id, t.full_name) for t in Technician.query.filter_by(is_active=True).all()
    ]

    if form.validate_on_submit():
        job = RepairJob(
            job_number=next_job_number(),
            customer_id=form.customer_id.data,
            vehicle_id=form.vehicle_id.data,
            technician_id=form.technician_id.data or None,
            customer_concern=form.customer_concern.data,
            status=JobStatus.DIAGNOSING,
        )
        db.session.add(job)
        db.session.commit()
        flash(f"Job {job.job_number} created.", "success")
        return redirect(url_for("staff.job_detail", job_id=job.id))

    return render_template("staff/new_job.html", form=form)


@staff_bp.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):
    job = RepairJob.query.get_or_404(job_id)
    finding_form = DiagnosticFindingForm()
    line_item_form = EstimateLineItemForm()
    send_form = SendEstimateForm()
    complete_form = CompleteJobForm()
    return render_template(
        "staff/job_detail.html",
        job=job,
        finding_form=finding_form,
        line_item_form=line_item_form,
        send_form=send_form,
        complete_form=complete_form,
    )


@staff_bp.route("/jobs/<int:job_id>/findings", methods=["POST"])
@login_required
def add_finding(job_id):
    job = RepairJob.query.get_or_404(job_id)
    form = DiagnosticFindingForm()
    if form.validate_on_submit():
        finding = DiagnosticFinding(
            job_id=job.id,
            technician_id=job.technician_id,
            system_area=form.system_area.data,
            description=form.description.data,
            severity=form.severity.data,
        )
        db.session.add(finding)
        db.session.flush()

        file_storage = form.photo.data
        if file_storage and file_storage.filename:
            meta = save_diagnostic_photo(file_storage, job.job_number)
            photo = DiagnosticPhoto(finding_id=finding.id, captured_at=utcnow(), **meta)
            db.session.add(photo)

        db.session.commit()
        flash("Diagnostic finding recorded.", "success")
    else:
        flash("Could not save finding - check the form.", "danger")
    return redirect(url_for("staff.job_detail", job_id=job.id))


@staff_bp.route("/jobs/<int:job_id>/estimate/line-items", methods=["POST"])
@login_required
def add_line_item(job_id):
    job = RepairJob.query.get_or_404(job_id)

    editable_statuses = {
        JobStatus.NEW, JobStatus.DIAGNOSING, JobStatus.APPROVED,
        JobStatus.IN_PROGRESS, JobStatus.DECLINED, JobStatus.EXPIRED,
    }
    if job.status not in editable_statuses:
        flash("This job's estimate can no longer be edited.", "danger")
        return redirect(url_for("staff.job_detail", job_id=job.id))

    form = EstimateLineItemForm()

    estimate = job.current_estimate
    if estimate is None or estimate.status not in {"draft"}:
        estimate = Estimate(job_id=job.id, status="draft", tax_rate=Decimal("0.0825"))
        db.session.add(estimate)
        db.session.flush()

    if form.validate_on_submit():
        item = EstimateLineItem(
            estimate_id=estimate.id,
            kind=form.kind.data,
            description=form.description.data,
            quantity=form.quantity.data,
            unit_price=form.unit_price.data,
        )
        db.session.add(item)
        db.session.commit()
        flash("Line item added to draft estimate.", "success")
    else:
        flash("Could not add line item - check the form.", "danger")
    return redirect(url_for("staff.job_detail", job_id=job.id))


@staff_bp.route("/jobs/<int:job_id>/estimate/send", methods=["POST"])
@login_required
def send_estimate(job_id):
    job = RepairJob.query.get_or_404(job_id)
    estimate = job.current_estimate
    if estimate is None or estimate.status != "draft" or not estimate.line_items:
        flash("There's no draft estimate with line items ready to send.", "warning")
        return redirect(url_for("staff.job_detail", job_id=job.id))

    if estimate_requires_fresh_approval(job, estimate):
        flash(
            f"Heads up: ${estimate.total} exceeds {job.customer.first_name}'s "
            f"${job.customer.spending_cap} spending cap. Sending for explicit "
            "approval before any work begins.",
            "warning",
        )

    form = SendEstimateForm()
    channel = form.channel.data if form.validate_on_submit() else "sms"
    send_estimate_for_approval(job, estimate, channel=channel)
    flash(f"Estimate sent to {job.customer.full_name} via {channel}.", "success")
    return redirect(url_for("staff.job_detail", job_id=job.id))


@staff_bp.route("/jobs/<int:job_id>/start-work", methods=["POST"])
@login_required
def start_work(job_id):
    job = RepairJob.query.get_or_404(job_id)
    if job.status != JobStatus.APPROVED:
        flash("Job must be in an approved state to start work.", "danger")
        return redirect(url_for("staff.job_detail", job_id=job.id))
    job.status = JobStatus.IN_PROGRESS
    db.session.commit()
    flash("Job marked in progress.", "success")
    return redirect(url_for("staff.job_detail", job_id=job.id))


@staff_bp.route("/jobs/<int:job_id>/complete", methods=["POST"])
@login_required
def complete_job(job_id):
    job = RepairJob.query.get_or_404(job_id)
    form = CompleteJobForm()
    if job.status != JobStatus.IN_PROGRESS:
        flash("Job must be in progress to complete it.", "danger")
        return redirect(url_for("staff.job_detail", job_id=job.id))

    if form.validate_on_submit():
        job.final_cost = form.final_cost.data
        job.completed_at = utcnow()
        job.status = JobStatus.COMPLETED
        db.session.commit()
        flash(f"Job {job.job_number} marked complete.", "success")
    else:
        flash("Enter a valid final invoice total.", "danger")
    return redirect(url_for("staff.job_detail", job_id=job.id))


@staff_bp.route("/customers/new", methods=["GET", "POST"])
@login_required
def new_customer():
    form = NewCustomerForm()
    if not form.is_submitted():
        form.spending_cap.data = Decimal(
            str(current_app.config["DEFAULT_CUSTOMER_SPENDING_CAP"])
        )
    if form.validate_on_submit():
        customer = Customer(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone_number=form.phone_number.data,
            email=form.email.data or None,
            spending_cap=form.spending_cap.data,
        )
        db.session.add(customer)
        db.session.commit()
        flash(f"Customer {customer.full_name} added.", "success")
        return redirect(url_for("staff.new_vehicle", customer_id=customer.id))
    return render_template("staff/new_customer.html", form=form)


@staff_bp.route("/customers/<int:customer_id>/vehicles/new", methods=["GET", "POST"])
@login_required
def new_vehicle(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = NewVehicleForm()
    if form.validate_on_submit():
        vehicle = Vehicle(
            customer_id=customer.id,
            year=form.year.data,
            make=form.make.data,
            model=form.model.data,
            vin=form.vin.data or None,
            license_plate=form.license_plate.data or None,
            mileage=form.mileage.data,
        )
        db.session.add(vehicle)
        db.session.commit()
        flash(f"Vehicle {vehicle.display_name} added to {customer.full_name}.", "success")
        return redirect(url_for("staff.new_job"))
    return render_template("staff/new_vehicle.html", form=form, customer=customer)


@staff_bp.route("/photos/<path:path>")
@login_required
def diagnostic_photo(path):
    """Serve locally-stored diagnostic photos to logged-in staff only.

    Customer-facing pages never link here directly; warranty review always
    happens through the staff dashboard.
    """
    upload_root = current_app.config["UPLOAD_FOLDER"]
    full_path = os.path.normpath(os.path.join(upload_root, path))
    if not full_path.startswith(os.path.normpath(upload_root)):
        abort(404)
    directory, filename = os.path.split(full_path)
    return send_from_directory(directory, filename)
