"""
routes/webhooks.py — Webhook Receiver for Booking Status Updates
═════════════════════════════════════════════════════════════════

Receives POST callbacks from booking vendors when a booking status changes
(confirmed, cancelled, modified).  Each vendor has its own signature
verification scheme; unverified payloads are rejected with 401.

Endpoints:
  POST /api/webhooks/<provider>   Receive a webhook from a vendor

Supported providers (signature schemes):
  - bookingcom  — HMAC-SHA256 of body using BOOKINGCOM_WEBHOOK_SECRET
  - makemytrip  — X-MMT-Signature header (HMAC-SHA256)
  - generic     — No signature (dev/test only; rejects in production)

Vendor-sent status → AltairGO Booking.status mapping:
  confirmed  → booked
  cancelled  → cancelled
  modified   → booked (with updated ref)
  failed     → failed
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import structlog
from flask import Blueprint, g, jsonify, request

from backend.database import db
from backend.models import Booking
from backend.utils.responses import normalize_api_response

webhooks_bp = Blueprint("webhooks", __name__)
log = structlog.get_logger(__name__)


@webhooks_bp.after_request
def _normalize_webhooks_response(response):
    return normalize_api_response(response)

_BOOKINGCOM_SECRET = os.getenv("BOOKINGCOM_WEBHOOK_SECRET", "")
_MMT_SECRET = os.getenv("MMT_WEBHOOK_SECRET", "")
_IS_PRODUCTION = os.getenv("FLASK_ENV", "production") == "production"

# Vendor status → internal status
_STATUS_MAP = {
    "confirmed": "booked",
    "cancelled": "cancelled",
    "modified": "booked",
    "failed": "failed",
    "pending": "pending",
}

_ALLOWED_PROVIDERS = frozenset({"bookingcom", "makemytrip", "generic"})


def _verify_bookingcom(body: bytes, signature: str) -> bool:
    if not _BOOKINGCOM_SECRET:
        return False
    expected = hmac.new(_BOOKINGCOM_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower().removeprefix("sha256="))


def _verify_makemytrip(body: bytes, signature: str) -> bool:
    if not _MMT_SECRET:
        return False
    expected = hmac.new(_MMT_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


@webhooks_bp.route("/api/webhooks/<provider>", methods=["POST"])
def receive_webhook(provider: str):
    """
    Receive a booking status webhook from a vendor.
    Verifies the signature, logs to WebhookLog, and updates the Booking row.
    """
    if provider not in _ALLOWED_PROVIDERS:
        return jsonify({"error": "Unknown provider"}), 404

    raw_body = request.get_data()
    content_type = request.content_type or ""

    # ── Signature verification ────────────────────────────────────────────────
    verified = False
    if provider == "bookingcom":
        sig = request.headers.get("X-Booking-Hmac-Sha256", "")
        verified = _verify_bookingcom(raw_body, sig)
    elif provider == "makemytrip":
        sig = request.headers.get("X-MMT-Signature", "")
        verified = _verify_makemytrip(raw_body, sig)
    elif provider == "generic":
        # Generic webhooks allowed only in non-production environments
        verified = not _IS_PRODUCTION

    if not verified:
        log.warning("webhook.signature_invalid", provider=provider)
        _log_webhook(provider, "signature_rejected", {}, status="rejected")
        return jsonify({"error": "Invalid signature"}), 401

    # ── Parse payload ─────────────────────────────────────────────────────────
    try:
        if "json" in content_type:
            payload = request.get_json(force=True) or {}
        else:
            payload = json.loads(raw_body) if raw_body else {}
    except Exception:
        log.warning("webhook.parse_failed", provider=provider)
        return jsonify({"error": "Invalid JSON payload"}), 400

    # ── Log the raw webhook ───────────────────────────────────────────────────
    webhook_log_id = _log_webhook(provider, payload.get("event_type", "unknown"), payload, status="received")

    # ── Process booking update ────────────────────────────────────────────────
    booking_ref = payload.get("booking_ref") or payload.get("reference") or payload.get("reservation_id")
    vendor_status = (payload.get("status") or "").lower()
    internal_status = _STATUS_MAP.get(vendor_status)

    if booking_ref and internal_status:
        try:
            booking = (
                db.session.query(Booking)
                .filter_by(booking_ref=booking_ref)
                .first()
            )
            if booking:
                booking.status = internal_status
                if internal_status == "booked":
                    new_ref = payload.get("confirmation_number") or booking_ref
                    booking.booking_ref = new_ref
                db.session.commit()
                _update_webhook_log(webhook_log_id, "processed", booking.id)
                log.info(
                    "webhook.booking_updated",
                    provider=provider,
                    booking_id=booking.id,
                    new_status=internal_status,
                )
            else:
                log.warning("webhook.booking_not_found", provider=provider, ref=booking_ref)
                _update_webhook_log(webhook_log_id, "booking_not_found")

        except Exception:
            db.session.rollback()
            log.exception("webhook.update_failed", provider=provider)
            _update_webhook_log(webhook_log_id, "update_failed")
            return jsonify({"error": "Processing failed"}), 500
    else:
        _update_webhook_log(webhook_log_id, "no_booking_ref")

    return jsonify({"received": True}), 200


# ── WebhookLog helpers ────────────────────────────────────────────────────────


def _log_webhook(provider: str, event_type: str, payload: dict, status: str = "received") -> str | None:
    """Write a WebhookLog entry and return its ID."""
    try:
        from backend.models import WebhookLog
        entry = WebhookLog(
            id=str(uuid4()),
            provider=provider,
            event_type=event_type,
            payload=payload,
            processing_status=status,
        )
        db.session.add(entry)
        db.session.commit()
        return entry.id
    except Exception:
        db.session.rollback()
        return None


def _update_webhook_log(log_id: str | None, processing_status: str, booking_id: str | None = None):
    if not log_id:
        return
    try:
        from backend.models import WebhookLog
        entry = db.session.get(WebhookLog, log_id)
        if entry:
            entry.processing_status = processing_status
            if booking_id:
                entry.booking_id = booking_id
            db.session.commit()
    except Exception:
        db.session.rollback()
