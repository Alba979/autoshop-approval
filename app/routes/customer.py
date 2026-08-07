from flask import Blueprint, render_template, request, current_app

from app.models.approval import ApprovalRequest
from app.services.tokens import verify_approval_token
from app.services.approval_workflow import record_customer_response
from app.forms import CustomerResponseForm
from app.models.base import utcnow

customer_bp = Blueprint("customer", __name__, url_prefix="/estimate")


def _resolve_approval(token):
    max_age = current_app.config["APPROVAL_LINK_TTL_HOURS"] * 3600
    approval_id = verify_approval_token(token, max_age_seconds=max_age)
    if approval_id is None:
        return None
    return ApprovalRequest.query.get(approval_id)


@customer_bp.route("/<token>", methods=["GET"])
def view_estimate(token):
    approval = _resolve_approval(token)
    if approval is None:
        return render_template("customer/link_invalid.html"), 404

    expired = (not approval.is_pending) or approval.expires_at <= utcnow()
    form = CustomerResponseForm()
    return render_template(
        "customer/estimate.html",
        approval=approval,
        job=approval.job,
        estimate=approval.estimate,
        expired=expired,
        form=form,
    )


@customer_bp.route("/<token>/respond", methods=["POST"])
def respond(token):
    approval = _resolve_approval(token)
    if approval is None:
        return render_template("customer/link_invalid.html"), 404

    if not approval.is_pending or approval.expires_at <= utcnow():
        return render_template(
            "customer/estimate.html", approval=approval, job=approval.job,
            estimate=approval.estimate, expired=True, form=CustomerResponseForm(),
        )

    form = CustomerResponseForm()
    decision = request.form.get("decision")
    if form.validate_on_submit() and decision in {"approved", "declined"}:
        record_customer_response(
            approval,
            decision,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:255],
        )

    return render_template("customer/response_recorded.html", approval=approval)
