from datetime import datetime, timezone


def register_filters(app):
    @app.template_filter("money")
    def money(value):
        if value is None:
            return "-"
        return f"${value:,.2f}"

    @app.template_filter("friendly_dt")
    def friendly_dt(value):
        if value is None:
            return "-"
        return value.strftime("%b %d, %Y %I:%M %p")

    @app.template_filter("status_badge")
    def status_badge(status):
        value = status.value if hasattr(status, "value") else status
        colors = {
            "new": "secondary",
            "diagnosing": "info",
            "waiting_on_customer": "warning",
            "approved": "primary",
            "in_progress": "primary",
            "declined": "danger",
            "expired": "dark",
            "completed": "success",
            "cancelled": "dark",
        }
        return colors.get(value, "secondary")

    @app.context_processor
    def inject_now():
        from app.models.base import utcnow

        return {"now": utcnow()}
