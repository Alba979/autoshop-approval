from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from app.services.analytics import (
    approval_turnaround_by_technician,
    estimate_vs_final_variance_by_technician,
    shop_summary,
)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@analytics_bp.route("/")
@login_required
def dashboard():
    return render_template(
        "staff/analytics.html",
        summary=shop_summary(),
        turnaround=approval_turnaround_by_technician(),
        variance=estimate_vs_final_variance_by_technician(),
    )


@analytics_bp.route("/data/turnaround.json")
@login_required
def turnaround_json():
    return jsonify(approval_turnaround_by_technician())


@analytics_bp.route("/data/variance.json")
@login_required
def variance_json():
    return jsonify(estimate_vs_final_variance_by_technician())
