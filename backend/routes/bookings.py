"""
routes/bookings.py — Booking Automation API
═══════════════════════════════════════════

Booking automation flow for a saved trip:

  1. POST /api/trip/<trip_id>/booking-plan
       Analyse the trip itinerary and build a list of bookable items
       (hotel, flights, activity tickets, etc.).
       Creates a TripPermissionRequest + individual Booking rows.
       Returns the permission screen payload for the frontend.

  2. GET  /api/trip/<trip_id>/booking-plan
       Fetch the current permission request and all associated bookings.

  3. POST /api/trip/<trip_id>/booking-plan/respond
       User approves or rejects each booking item in one call.
       Body: {"decisions": {"<booking_id>": true|false, ...}}
       Updates Booking.user_approved for each item.
       Returns a summary of approved / rejected counts.

  4. POST /api/booking/<booking_id>/execute
       Execute a single approved booking.
       In production this calls the vendor API; in this implementation it
       marks the booking as 'booked' with a simulated reference.
"""

from datetime import datetime, date, timedelta, timezone
from math import ceil
from uuid import uuid4

import structlog
from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import get_jwt_identity, jwt_required
from backend.extensions import limiter

from backend.constants import (
    AIRPORT_TRANSFER_ESTIMATE_INR,
    DAILY_CAB_ESTIMATE_INR,
    OCCUPANCY_PER_ROOM,
)
from backend.database import db
from backend.models import Booking, FlightRoute, Trip, TripPermissionRequest

bookings_bp = Blueprint("bookings", __name__)
log = structlog.get_logger(__name__)

# Domain allowlist for booking URLs — reject anything not on this list
_ALLOWED_BOOKING_DOMAINS = frozenset({
    "booking.com", "hotels.com", "agoda.com",
    "makemytrip.com", "cleartrip.com", "goibibo.com",
    "klook.com", "insider.in", "dineout.co.in", "zomato.com",
    "ola.com", "uber.com", "rapido.bike",
})


def _validate_booking_url(url: str | None) -> str:
    """Return url only if it belongs to an allowed booking domain, else empty string."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc.lower().lstrip("www.")
        if any(host == d or host.endswith("." + d) for d in _ALLOWED_BOOKING_DOMAINS):
            return url
    except Exception:
        pass
    return ""


def _safe_user_id() -> int | None:
    """Parse JWT identity as int, return None on failure."""
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None

# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_booking_items(trip: Trip) -> list[dict]:
    """
    Parse a saved Trip's itinerary_json and extract all bookable items.

    Returns a list of dicts, each representing one bookable item:
      {type, item_name, provider, booking_url, start_datetime, end_datetime,
       price_inr, num_travelers, total_price_inr, payload}
    """
    items = []
    data = trip.itinerary_json or {}
    num_travelers = trip.travelers or 1
    start_date_str = trip.start_date or date.today().isoformat()

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        start_date = datetime.combine(date.today(), datetime.min.time())

    duration = trip.duration or 1

    # ── Outbound flight (home → destination) ─────────────────────────────────
    # Only added when the itinerary carries from_city_iata (captured at generation time)
    # and a travel_between_cities block is present.
    from_city = data.get("from_city_iata") or data.get("origin_iata")
    dest_city = data.get("destination_iata")
    outbound_price = data.get("outbound_flight_price_inr", 0)
    if from_city and dest_city:
        items.append({
            "type": "flight",
            "item_name": f"Outbound Flight: {from_city} → {dest_city}",
            "provider": "MakeMyTrip",
            "booking_url": "",
            "start_datetime": start_date.isoformat(),
            "end_datetime": start_date.isoformat(),
            "price_inr": int(outbound_price),
            "num_travelers": num_travelers,
            "total_price_inr": int(outbound_price * num_travelers),
            "payload": {"origin": from_city, "destination": dest_city, "flight_type": "outbound"},
        })
        # Return flight — look up actual return route price; fall back to outbound price
        return_date = start_date + timedelta(days=duration)
        return_route = (
            db.session.query(FlightRoute)
            .filter_by(origin_iata=dest_city, destination_iata=from_city)
            .first()
        )
        return_price = (
            return_route.avg_one_way_inr if (return_route and return_route.avg_one_way_inr)
            else outbound_price
        )
        items.append({
            "type": "flight",
            "item_name": f"Return Flight: {dest_city} → {from_city}",
            "provider": "MakeMyTrip",
            "booking_url": "",
            "start_datetime": return_date.isoformat(),
            "end_datetime": return_date.isoformat(),
            "price_inr": int(return_price),
            "num_travelers": num_travelers,
            "total_price_inr": int(return_price * num_travelers),
            "payload": {"origin": dest_city, "destination": from_city, "flight_type": "return"},
        })

    # ── Hotel ────────────────────────────────────────────────────────────────
    first_day = data.get("itinerary", [{}])[0] if data.get("itinerary") else {}
    accom = first_day.get("accommodation")
    if isinstance(accom, dict) and accom.get("hotel_name"):
        cost_per_night = accom.get("cost_per_night") or 0
        end_dt = start_date + timedelta(days=duration)
        special_occasion = data.get("traveler_profile", {}).get("special_occasion")
        num_rooms = ceil(num_travelers / OCCUPANCY_PER_ROOM)
        items.append({
            "type": "hotel",
            "item_name": accom["hotel_name"],
            "provider": "Booking.com",
            "booking_url": accom.get("booking_url") or "",
            "start_datetime": start_date.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "price_inr": int(cost_per_night),
            "num_travelers": num_travelers,
            "total_price_inr": int(cost_per_night * duration * num_rooms),  # per-room × nights × rooms needed
            "payload": {
                "star_rating": accom.get("star_rating"),
                "category": accom.get("category"),
                "special_occasion": special_occasion,
                "special_request": (
                    f"Special occasion: {special_occasion}. Please arrange accordingly."
                    if special_occasion else None
                ),
            },
        })

    # ── Flights / Transport (inter-city within trip) ──────────────────────────
    for segment in data.get("travel_between_cities", []):
        price = segment.get("avg_price_inr") or 0
        transport_type = segment.get("transport_type", "flight")
        items.append({
            "type": "flight" if transport_type == "flight" else "transport",
            "item_name": f"{segment.get('origin', '?')} → {segment.get('destination', '?')} ({transport_type})",
            "provider": "MakeMyTrip",
            "booking_url": "",
            "start_datetime": start_date.isoformat(),
            "end_datetime": start_date.isoformat(),
            "price_inr": int(price),
            "num_travelers": num_travelers,
            "total_price_inr": int(price * num_travelers),
            "payload": segment,
        })

    has_flights = from_city and dest_city

    # ── Airport transfer — arrival (Day 1) ────────────────────────────────────
    # Only add airport transfers when the trip includes flights.
    if has_flights:
        items.append({
            "type": "airport_transfer",
            "item_name": f"Airport → Hotel Transfer (Arrival, Day 1)",
            "provider": "Ola/Uber",
            "booking_url": "",
            "start_datetime": start_date.isoformat(),
            "end_datetime": start_date.isoformat(),
            "price_inr": AIRPORT_TRANSFER_ESTIMATE_INR,
            "num_travelers": num_travelers,
            "total_price_inr": AIRPORT_TRANSFER_ESTIMATE_INR * num_travelers,
            "payload": {"transfer_type": "arrival", "tip": "Pre-book via app to avoid inflated fares."},
        })

    # ── Activity tickets & restaurant reservations ─────────────────────────────
    for day_idx, day in enumerate(data.get("itinerary", [])):
        try:
            day_date = start_date + timedelta(days=day_idx)
        except Exception:
            day_date = start_date

        for act in day.get("activities", []):
            if act.get("is_break"):
                # ── Meal reservation (restaurant-type break) ──────────────────
                meal_type = act.get("meal_type")
                if meal_type in ("lunch", "dinner"):
                    # Only create a restaurant booking for non-hotel meals
                    items.append({
                        "type": "restaurant",
                        "item_name": f"{meal_type.capitalize()} reservation — Day {day.get('day', day_idx + 1)}",
                        "provider": "Dineout/Zomato",
                        "booking_url": "",
                        "start_datetime": f"{day_date.strftime('%Y-%m-%d')}T{act.get('time', '13:00')}:00",
                        "end_datetime": f"{day_date.strftime('%Y-%m-%d')}T{act.get('end_time', '14:00')}:00",
                        "price_inr": 0,   # cost captured in budget; slot reservation is free
                        "num_travelers": num_travelers,
                        "total_price_inr": 0,
                        "payload": {"meal_type": meal_type, "day": day.get("day")},
                    })
                continue

            cost = act.get("cost") or 0
            if cost <= 0:
                continue
            requires_advance = act.get("requires_advance_booking", False)
            items.append({
                "type": "activity",
                "item_name": act.get("name", "Activity"),
                "provider": "Insider" if requires_advance else "Direct",
                "booking_url": "",
                "start_datetime": f"{day_date.strftime('%Y-%m-%d')}T{act.get('time', '10:00')}:00",
                "end_datetime": f"{day_date.strftime('%Y-%m-%d')}T{act.get('end_time', '12:00')}:00",
                "price_inr": int(cost),
                "num_travelers": num_travelers,
                "total_price_inr": int(cost * num_travelers),
                "payload": {
                    "requires_advance_booking": requires_advance,
                    "opening_hours": act.get("opening_hours"),
                    "day": day.get("day"),
                    "dress_code": act.get("dress_code"),
                    "guide_available": act.get("guide_available", False),
                },
            })

        # ── Daily cab estimate (pre-book for each full day) ───────────────────
        activity_count = len([a for a in day.get("activities", []) if not a.get("is_break")])
        if activity_count > 0 and day_idx > 0:  # skip Day 1 (covered by airport transfer)
            items.append({
                "type": "daily_cab",
                "item_name": f"Day {day.get('day', day_idx + 1)} — Cab/Taxi between attractions",
                "provider": "Ola/Uber/Rapido",
                "booking_url": "",
                "start_datetime": day_date.isoformat(),
                "end_datetime": day_date.isoformat(),
                "price_inr": DAILY_CAB_ESTIMATE_INR,
                "num_travelers": num_travelers,
                "total_price_inr": DAILY_CAB_ESTIMATE_INR * num_travelers,
                "payload": {
                    "day": day.get("day"),
                    "activity_count": activity_count,
                    "tip": "Book Ola/Uber in advance for day-use cab at lower rates.",
                },
            })

    # ── Airport transfer — departure (last day) ────────────────────────────────
    if has_flights and duration > 1:
        departure_date = start_date + timedelta(days=duration - 1)
        items.append({
            "type": "airport_transfer",
            "item_name": f"Hotel → Airport Transfer (Departure, Day {duration})",
            "provider": "Ola/Uber",
            "booking_url": "",
            "start_datetime": departure_date.isoformat(),
            "end_datetime": departure_date.isoformat(),
            "price_inr": AIRPORT_TRANSFER_ESTIMATE_INR,
            "num_travelers": num_travelers,
            "total_price_inr": AIRPORT_TRANSFER_ESTIMATE_INR * num_travelers,
            "payload": {
                "transfer_type": "departure",
                "tip": "Allow 2.5–3 hours before flight. Book the night before.",
            },
        })

    return items


# ── Routes ────────────────────────────────────────────────────────────────────


@bookings_bp.route("/api/trip/<int:trip_id>/booking-plan", methods=["POST"])
@jwt_required()
def create_booking_plan(trip_id: int):
    """
    Analyse the trip itinerary and create a permission request with all
    bookable items. If a plan already exists for this trip it is returned
    without creating duplicates.
    """
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        # Return existing plan if already created
        existing = (
            db.session.query(TripPermissionRequest)
            .filter_by(trip_id=trip_id, user_id=user_id)
            .order_by(TripPermissionRequest.created_at.desc())
            .first()
        )
        if existing:
            bookings = (
                db.session.query(Booking)
                .filter_by(permission_request_id=existing.id)
                .all()
            )
            return jsonify({
                "permission_request_id": existing.id,
                "status": existing.status,
                "total_estimated_cost_inr": existing.total_estimated_cost_inr,
                "items": _serialize_bookings(bookings),
            }), 200

        # Build bookable items from itinerary
        raw_items = _build_booking_items(trip)
        total_cost = sum(item["total_price_inr"] for item in raw_items)

        # Create permission request
        perm_id = str(uuid4())
        perm_req = TripPermissionRequest(
            id=perm_id,
            trip_id=trip_id,
            user_id=user_id,
            status="pending",
            total_estimated_cost_inr=total_cost,
            items_snapshot=raw_items,
        )
        db.session.add(perm_req)

        # Create individual Booking rows
        booking_rows = []
        for item in raw_items:
            b = Booking(
                id=str(uuid4()),
                trip_id=trip_id,
                user_id=user_id,
                permission_request_id=perm_id,
                booking_type=item["type"],
                item_name=item["item_name"],
                provider=item.get("provider"),
                booking_url=_validate_booking_url(item.get("booking_url")),
                start_datetime=_parse_dt(item.get("start_datetime")),
                end_datetime=_parse_dt(item.get("end_datetime")),
                price_inr=item["price_inr"],
                num_travelers=item["num_travelers"],
                total_price_inr=item["total_price_inr"],
                status="pending",
                user_approved=0,
                payload=item.get("payload"),
            )
            db.session.add(b)
            booking_rows.append(b)

        db.session.commit()

        log.info("booking_plan.created", trip_id=trip_id, items=len(booking_rows), total_cost=total_cost)

        return jsonify({
            "permission_request_id": perm_id,
            "status": "pending",
            "total_estimated_cost_inr": total_cost,
            "items": _serialize_bookings(booking_rows),
            "message": (
                f"Booking plan ready. {len(booking_rows)} item(s) need your approval "
                f"before we proceed. Total estimated cost: ₹{total_cost:,}."
            ),
        }), 201

    except Exception:
        db.session.rollback()
        log.exception("booking_plan.create_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@bookings_bp.route("/api/trip/<int:trip_id>/booking-plan", methods=["GET"])
@jwt_required()
def get_booking_plan(trip_id: int):
    """Fetch the latest booking plan for a trip."""
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        perm_req = (
            db.session.query(TripPermissionRequest)
            .filter_by(trip_id=trip_id, user_id=user_id)
            .order_by(TripPermissionRequest.created_at.desc())
            .first()
        )
        if not perm_req:
            return jsonify({"error": "No booking plan found. POST to create one."}), 404

        bookings = (
            db.session.query(Booking)
            .filter_by(permission_request_id=perm_req.id)
            .all()
        )

        return jsonify({
            "permission_request_id": perm_req.id,
            "status": perm_req.status,
            "total_estimated_cost_inr": perm_req.total_estimated_cost_inr,
            "responded_at": perm_req.responded_at.isoformat() if perm_req.responded_at else None,
            "items": _serialize_bookings(bookings),
        }), 200

    except Exception:
        log.exception("booking_plan.fetch_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


_MAX_DECISIONS = 500  # Maximum booking IDs accepted in a single respond call


@bookings_bp.route("/api/trip/<int:trip_id>/booking-plan/respond", methods=["POST"])
@jwt_required()
def respond_to_booking_plan(trip_id: int):
    """
    User approves or rejects individual booking items.

    Body: {"decisions": {"<booking_id>": true, "<booking_id2>": false, ...}}

    true  = approved -> Booking.user_approved = 1, status = "approved"
    false = rejected -> Booking.user_approved = -1, status = "rejected"
    """
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json() or {}
    decisions = body.get("decisions", {})

    if not decisions:
        return jsonify({"error": "'decisions' dict is required"}), 400
    if not isinstance(decisions, dict):
        return jsonify({"error": "'decisions' must be an object"}), 400
    if len(decisions) > _MAX_DECISIONS:
        return jsonify({"error": f"Too many decisions; maximum is {_MAX_DECISIONS}"}), 400
    # Validate all values are booleans
    invalid = [k for k, v in decisions.items() if not isinstance(v, bool)]
    if invalid:
        return jsonify({"error": "All decision values must be boolean (true/false)"}), 400

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        perm_req = (
            db.session.query(TripPermissionRequest)
            .filter_by(trip_id=trip_id, user_id=user_id)
            .order_by(TripPermissionRequest.created_at.desc())
            .first()
        )
        if not perm_req:
            return jsonify({"error": "No booking plan found."}), 404

        approved_count = 0
        rejected_count = 0
        not_found = []

        # Load all booking IDs in one query to avoid N+1
        booking_ids = list(decisions.keys())
        bookings_batch = (
            db.session.query(Booking)
            .filter(
                Booking.id.in_(booking_ids),
                Booking.trip_id == trip_id,
                Booking.permission_request_id == perm_req.id,
            )
            .all()
        )
        booking_map = {b.id: b for b in bookings_batch}

        for booking_id, approved in decisions.items():
            booking = booking_map.get(booking_id)
            if not booking:
                not_found.append(booking_id)
                continue
            if approved:
                booking.user_approved = 1
                booking.status = "approved"
                approved_count += 1
            else:
                booking.user_approved = -1
                booking.status = "rejected"
                rejected_count += 1

        # Update permission request status
        all_bookings = (
            db.session.query(Booking)
            .filter_by(permission_request_id=perm_req.id)
            .all()
        )
        total = len(all_bookings)
        n_approved = sum(1 for b in all_bookings if b.user_approved == 1)
        n_rejected = sum(1 for b in all_bookings if b.user_approved == -1)

        if n_rejected == total:
            perm_req.status = "declined"
        elif n_approved == total:
            perm_req.status = "fully_approved"
        elif n_approved + n_rejected == total:
            perm_req.status = "partially_approved"
        else:
            perm_req.status = "presented"

        perm_req.responded_at = datetime.now(timezone.utc)
        db.session.commit()

        log.info(
            "booking_plan.respond",
            perm_id=perm_req.id,
            approved=n_approved,
            rejected=n_rejected,
            total=total,
            status=perm_req.status,
        )

        return jsonify({
            "permission_request_id": perm_req.id,
            "status": perm_req.status,
            "approved": n_approved,
            "rejected": n_rejected,
            "total": total,
            "not_found": not_found,
            "message": (
                f"Got it! {n_approved} booking(s) approved, {n_rejected} skipped. "
                + ("We'll now proceed with the approved bookings." if n_approved > 0 else "No bookings will be made.")
            ),
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("booking_plan.respond_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@bookings_bp.route("/api/booking/<booking_id>/execute", methods=["POST"])
@jwt_required()
def execute_booking(booking_id: str):
    """
    Execute a single approved booking.

    NOTE: Vendor SDK integrations are pending. Currently simulates a confirmed
    reference so the full flow can be tested end-to-end. All responses include
    "simulated": true until real vendor calls are wired in.
    """
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.user_id != user_id:
            return jsonify({"error": "Booking not found"}), 404

        if booking.user_approved != 1:
            return jsonify({"error": "Booking has not been approved by the user."}), 400

        if booking.status == "booked":
            return jsonify({
                "booking_id": booking_id,
                "status": "booked",
                "booking_ref": booking.booking_ref,
                "message": "Already booked.",
            }), 200

        # Delegate to provider registry — hotel uses BookingComProvider (affiliate link),
        # all other types fall back to SimulatedProvider until vendor SDKs are integrated.
        from backend.services.booking_providers import get_provider
        provider = get_provider(booking.booking_type)
        result = provider.execute(booking)

        if not result.success:
            booking.status = "failed"
            booking.failure_reason = result.error or "Provider returned failure"
            db.session.commit()
            return jsonify({
                "booking_id": booking_id,
                "status": "failed",
                "message": result.error or "Booking failed",
            }), 502

        booking.status = "booked"
        booking.booking_ref = result.booking_ref
        if result.booking_url:
            booking.booking_url = _validate_booking_url(result.booking_url)
        db.session.commit()

        log.info("booking.executed", booking_id=booking_id, ref=result.booking_ref, simulated=result.simulated)

        return jsonify({
            "booking_id": booking_id,
            "status": "booked",
            "booking_ref": result.booking_ref,
            "item_name": booking.item_name,
            "booking_url": booking.booking_url,
            "simulated": result.simulated,
            "message": (
                f"{booking.item_name} booking confirmed. Reference: {result.booking_ref}"
                + (" (simulated)" if result.simulated else "")
            ),
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("booking.execute_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@bookings_bp.route("/api/trip/<int:trip_id>/booking-plan/execute-all", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def execute_all_bookings(trip_id: int):
    """
    Execute ALL approved bookings for a trip in one call.

    Only bookings with user_approved=1 and status="approved" are executed.
    Returns a summary of booked / failed counts plus individual results.
    NOTE: responses include "simulated": true until vendor SDKs are integrated.
    """
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        perm_req = (
            db.session.query(TripPermissionRequest)
            .filter_by(trip_id=trip_id, user_id=user_id)
            .order_by(TripPermissionRequest.created_at.desc())
            .first()
        )
        if not perm_req:
            return jsonify({"error": "No booking plan found. POST to /booking-plan first."}), 404

        approved_bookings = (
            db.session.query(Booking)
            .filter_by(permission_request_id=perm_req.id, user_approved=1, status="approved")
            .all()
        )
        if not approved_bookings:
            return jsonify({
                "message": "No approved bookings to execute. Approve items first via /booking-plan/respond.",
                "booked": 0,
                "failed": 0,
            }), 200

        from backend.services.booking_providers import get_provider

        booked, failed = 0, 0
        any_real = False
        results = []
        for booking in approved_bookings:
            try:
                provider = get_provider(booking.booking_type)
                result = provider.execute(booking)
                if result.success:
                    booking.status = "booked"
                    booking.booking_ref = result.booking_ref
                    if result.booking_url:
                        booking.booking_url = _validate_booking_url(result.booking_url)
                    booked += 1
                    if not result.simulated:
                        any_real = True
                    results.append({
                        "booking_id": booking.id,
                        "item_name": booking.item_name,
                        "ref": result.booking_ref,
                        "status": "booked",
                        "simulated": result.simulated,
                    })
                else:
                    booking.status = "failed"
                    booking.failure_reason = result.error
                    failed += 1
                    results.append({"booking_id": booking.id, "item_name": booking.item_name, "status": "failed"})
            except Exception as exc:
                log.warning("booking.execute_single_failed", booking_id=booking.id, error=str(exc))
                booking.status = "failed"
                booking.failure_reason = str(exc)
                failed += 1
                results.append({"booking_id": booking.id, "item_name": booking.item_name, "status": "failed"})

        db.session.commit()
        log.info("booking.execute_all", trip_id=trip_id, booked=booked, failed=failed)

        all_simulated = not any_real
        return jsonify({
            "trip_id": trip_id,
            "booked": booked,
            "failed": failed,
            "simulated": all_simulated,
            "results": results,
            "message": (
                f"{booked} booking(s) confirmed!"
                + (" (simulated)" if all_simulated else "")
                + (f" {failed} failed — check results for details." if failed else "")
            ),
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("booking.execute_all_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@bookings_bp.route("/api/booking/<booking_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_booking(booking_id: str):
    """
    Cancel a booking.  Only bookings that are not yet 'booked' can be cancelled
    without a refund flow; booked items are marked 'cancelled' for vendor follow-up.
    """
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.user_id != user_id:
            return jsonify({"error": "Booking not found"}), 404

        if booking.status == "cancelled":
            return jsonify({"booking_id": booking_id, "status": "cancelled", "message": "Already cancelled."}), 200

        booking.status = "cancelled"
        booking.user_approved = -1
        db.session.commit()

        log.info("booking.cancelled", booking_id=booking_id, user_id=user_id)

        return jsonify({
            "booking_id": booking_id,
            "item_name": booking.item_name,
            "status": "cancelled",
            "message": (
                f"'{booking.item_name}' booking cancelled. "
                "If already confirmed with the vendor, please contact them directly for a refund."
                if booking.booking_ref else
                f"'{booking.item_name}' booking cancelled."
            ),
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("booking.cancel_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@bookings_bp.route("/api/trip/<int:trip_id>/bookings", methods=["GET"])
@jwt_required()
def list_trip_bookings(trip_id: int):
    """
    List all bookings for a trip with their current statuses.
    Grouped by type for easy display in a booking dashboard.
    """
    user_id = _safe_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        bookings = (
            db.session.query(Booking)
            .filter_by(trip_id=trip_id, user_id=user_id)
            .order_by(Booking.start_datetime)
            .all()
        )

        # Group by type
        all_serialized = _serialize_bookings(bookings)
        grouped: dict = {}
        for s in all_serialized:
            grouped.setdefault(s["type"], []).append(s)

        summary = {
            "total": len(bookings),
            "approved": sum(1 for b in bookings if b.user_approved == 1),
            "booked": sum(1 for b in bookings if b.status == "booked"),
            "pending": sum(1 for b in bookings if b.user_approved == 0),
            "rejected": sum(1 for b in bookings if b.user_approved == -1),
            "cancelled": sum(1 for b in bookings if b.status == "cancelled"),
            "total_confirmed_cost_inr": sum(
                (b.total_price_inr or 0) for b in bookings if b.status == "booked"
            ),
        }

        return jsonify({"summary": summary, "by_type": grouped}), 200

    except Exception:
        log.exception("booking.list_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Private helpers ───────────────────────────────────────────────────────────


def _serialize_bookings(bookings: list) -> list[dict]:
    return [
        {
            "id": b.id,
            "type": b.booking_type,
            "item_name": b.item_name,
            "provider": b.provider,
            "booking_url": b.booking_url,
            "start_datetime": b.start_datetime.isoformat() if b.start_datetime else None,
            "end_datetime": b.end_datetime.isoformat() if b.end_datetime else None,
            "price_inr": b.price_inr,
            "num_travelers": b.num_travelers,
            "total_price_inr": b.total_price_inr,
            "status": b.status,
            "user_approved": b.user_approved,
            "booking_ref": b.booking_ref,
        }
        for b in bookings
    ]


def _parse_dt(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
