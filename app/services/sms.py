"""Outbound SMS for estimate notifications and reminders.

Two providers are supported:
  - "console": logs the message instead of sending it. Used in local dev
    and in tests so nobody accidentally texts a real phone number.
  - "twilio": sends a real SMS via the Twilio REST API.

Swap providers with the SMS_PROVIDER environment variable - nothing else
in the app needs to change.
"""
import logging

from flask import current_app

logger = logging.getLogger("autoshop.sms")


class SmsSendError(Exception):
    pass


def send_sms(to_number, body):
    provider = current_app.config.get("SMS_PROVIDER", "console")
    if provider == "console":
        logger.info("[console-sms] to=%s body=%s", to_number, body)
        return {"provider": "console", "sid": None}

    if provider == "twilio":
        return _send_via_twilio(to_number, body)

    raise SmsSendError(f"Unknown SMS_PROVIDER: {provider!r}")


def _send_via_twilio(to_number, body):
    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException
    except ImportError as exc:  # pragma: no cover
        raise SmsSendError("twilio package is not installed") from exc

    sid = current_app.config["TWILIO_ACCOUNT_SID"]
    token = current_app.config["TWILIO_AUTH_TOKEN"]
    from_number = current_app.config["TWILIO_FROM_NUMBER"]

    if not (sid and token and from_number):
        raise SmsSendError(
            "Twilio credentials are not configured. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER, or switch "
            "SMS_PROVIDER back to 'console' for local use."
        )

    client = Client(sid, token)
    try:
        message = client.messages.create(to=to_number, from_=from_number, body=body)
    except TwilioRestException as exc:
        logger.error("Twilio send failed: %s", exc)
        raise SmsSendError(str(exc)) from exc

    return {"provider": "twilio", "sid": message.sid}


def build_estimate_sms_body(shop_name, job, estimate, approval_url):
    lines = [
        f"{shop_name}: Estimate ready for your {job.vehicle.display_name}.",
    ]
    for item in estimate.line_items:
        lines.append(f"- {item.description}: ${item.line_total}")
    lines.append(f"Total: ${estimate.total}")
    lines.append(f"Review & approve/decline: {approval_url}")
    return "\n".join(lines)
