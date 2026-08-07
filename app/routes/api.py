from flask import Blueprint, jsonify
from flask_login import login_required

from app.models.job import RepairJob

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/jobs/<int:job_id>/status")
@login_required
def job_status(job_id):
    job = RepairJob.query.get_or_404(job_id)
    return jsonify(
        {
            "job_number": job.job_number,
            "status": job.status.value,
            "waiting_since": job.waiting_since.isoformat() if job.waiting_since else None,
            "final_cost": str(job.final_cost) if job.final_cost is not None else None,
        }
    )
