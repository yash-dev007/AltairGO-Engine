"""
routes/trip_editor.py — Full Trip Editing Before Booking
═════════════════════════════════════════════════════════

Gives travellers complete freedom to customise their generated itinerary before
any booking is executed.  "I know this place a little — let me adjust the plan."

ITINERARY EDITING (modify itinerary_json of a saved trip)
──────────────────────────────────────────────────────────
  GET  /api/trip/<id>/hotel-options
       Browse every hotel we have on record for this trip's destination.
       Lets the user choose their own hotel instead of the engine's pick.

  PUT  /api/trip/<id>/hotel
       Replace the hotel in the itinerary.
       Body: {hotel_id} (from our DB) OR {custom_hotel_name, cost_per_night,
              booking_url?, star_rating?, notes?}

  POST /api/trip/<id>/day/<day_num>/activity/add
       Add an activity to a specific day — either from our DB (attraction_id)
       or a completely custom entry the user knows about.
       Re-runs RouteOptimizer after insertion.

  DELETE /api/trip/<id>/day/<day_num>/activity/remove
       Remove an activity from a day by name. Re-schedules the day.

  PUT  /api/trip/<id>/day/<day_num>/activity/edit
       Edit specific fields of an activity without re-optimising.
       Supports: cost_override, user_note, custom_description, scheduled_time.

  PUT  /api/trip/<id>/day/<day_num>/reorder
       Manually reorder activities. Re-optimises timing after reorder.

  PUT  /api/trip/<id>/notes
       Save free-text notes at trip level and per-day.
       {"trip": "...", "days": {"1": "...", "2": "..."}}

BOOKING PLAN EDITING (customise before execution)
──────────────────────────────────────────────────
  PUT  /api/booking/<id>/customize
       Edit a booking item before execution.
       Can: change hotel name/provider/price, add notes, mark as self_arranged
       (so the engine skips it during execute-all — user will handle it themselves).

  POST /api/trip/<id>/booking-plan/add-custom
       Add a booking the user has already arranged themselves or found a
       better deal for.  Immediately marked as booked with the user's ref.
"""

import copy
from datetime import date, datetime, timedelta, timezone

import structlog
from math import ceil
from uuid import uuid4

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.constants import OCCUPANCY_PER_ROOM
from backend.database import db
from backend.engine.route_optimizer import RouteOptimizer
from backend.models import (
    Attraction, Booking, Destination, HotelPrice, Trip, TripPermissionRequest,
)

trip_editor_bp = Blueprint("trip_editor", __name__)
log = structlog.get_logger(__name__)

_ALLOWED_HOTEL_URL_DOMAINS = {
    "booking.com", "hotels.com", "agoda.com", "makemytrip.com",
    "cleartrip.com", "goibibo.com", "airbnb.com", "trivago.com",
    "expedia.com", "oyorooms.com", "treebo.com",
}


def _safe_hotel_url(url: str | None) -> str:
    """Return url only if it belongs to an allowed hotel booking domain, else empty string."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        if any(host == d or host.endswith("." + d) for d in _ALLOWED_HOTEL_URL_DOMAINS):
            return url
    except Exception:
        pass
    return ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_trip_or_404(trip_id: int, user_id: int):
    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != user_id:
        return None
    return trip


def _dest_for_trip(trip: Trip) -> Destination | None:
    """Resolve primary Destination from the itinerary's first day location."""
    itinerary = trip.itinerary_json or {}
    days = itinerary.get("itinerary", [])
    if not days:
        return None
    loc_name = days[0].get("location")
    if not loc_name:
        return None
    return db.session.query(Destination).filter_by(name=loc_name).first()


def _reoptimize_day(trip: Trip, day_num: int, day_data: dict) -> dict:
    """
    Re-run RouteOptimizer on the non-break activities of a day.
    Preserves break entries (breakfast, lunch, dinner, hotel check-in) from
    the original schedule — only activity order and timing are recalculated.
    """
    itinerary = trip.itinerary_json or {}
    num_days = trip.duration or 1

    # Resolve date string for this day
    date_str = date.today().isoformat()
    if trip.start_date:
        try:
            base = datetime.strptime(trip.start_date, "%Y-%m-%d")
            date_str = (base + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
        except Exception:
            pass

    day_type = (
        "arrival" if day_num == 1 and num_days > 1
        else "departure" if day_num == num_days and num_days > 1
        else "normal"
    )

    # Pull non-break activities as proxy objects for RouteOptimizer
    act_entries = [a for a in day_data.get("activities", []) if not a.get("is_break")]
    proxies = [_activity_dict_to_proxy(a) for a in act_entries]

    updated_route = RouteOptimizer().optimize(proxies, date_str, day_type=day_type)
    day_data["activities"] = updated_route["activities"]
    day_data["pacing_level"] = updated_route["pacing_level"]
    return day_data


def _activity_dict_to_proxy(act: dict):
    """
    Wrap a schedule-dict (from itinerary_json) as a minimal proxy object so
    RouteOptimizer can consume it without a live DB row.
    """
    return type("_Proxy", (), {
        "id": act.get("_attraction_id"),
        "name": act.get("name", "Activity"),
        "description": act.get("description", ""),
        "type": act.get("type", "general"),
        "entry_cost_min": act.get("cost", 0),
        "entry_cost_max": act.get("cost", 0),
        "avg_visit_duration_hours": (act.get("duration_minutes", 90)) / 60,
        "best_visit_time_hour": _parse_hour(act.get("time", "10:00")),
        "latitude": act.get("latitude") or act.get("lat"),
        "longitude": act.get("longitude") or act.get("lng"),
        "lat": act.get("lat") or act.get("latitude"),
        "lng": act.get("lng") or act.get("longitude"),
        "gallery_images": act.get("images", []),
        "opening_hours": act.get("opening_hours"),
        "crowd_level_by_hour": {},
        "requires_advance_booking": int(act.get("requires_advance_booking", False)),
        "connects_well_with": [],
        "difficulty_level": act.get("difficulty_level", "easy"),
        "is_photo_spot": int(act.get("is_photo_spot", False)),
        "best_photo_hour": act.get("best_photo_hour"),
        "queue_time_minutes": act.get("queue_wait_minutes", 0),
        "dress_code": act.get("dress_code"),
        "guide_available": int(act.get("guide_available", False)),
        "min_age": act.get("min_age"),
    })()


def _parse_hour(time_str: str) -> int:
    try:
        return int(time_str.split(":")[0])
    except Exception:
        return 10


def _mark_customized(trip: Trip):
    trip.is_customized = 1


# ── Hotel Options ─────────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/hotel-options", methods=["GET"])
@jwt_required()
def hotel_options(trip_id: int):
    """
    List all available hotels for the trip's primary destination.

    Allows the traveller to browse and choose a specific hotel instead of the
    engine's default pick.  Grouped by category (budget / mid / luxury).

    Query params:
      category   — filter: budget / mid / luxury
      max_price  — maximum price per night in INR
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    dest = _dest_for_trip(trip)
    if not dest:
        return jsonify({"error": "Could not resolve destination from itinerary"}), 422

    category_filter = request.args.get("category")
    max_price = request.args.get("max_price", type=int)

    query = db.session.query(HotelPrice).filter_by(destination_id=dest.id)
    if category_filter:
        query = query.filter(HotelPrice.category == category_filter)
    if max_price:
        query = query.filter(HotelPrice.price_per_night_min <= max_price)

    hotels = query.order_by(HotelPrice.category, HotelPrice.price_per_night_min).all()

    # Current hotel in the itinerary (so UI can highlight it)
    itinerary = trip.itinerary_json or {}
    first_day = (itinerary.get("itinerary") or [{}])[0]
    current_accom = first_day.get("accommodation", {})
    current_hotel_name = current_accom.get("hotel_name") if isinstance(current_accom, dict) else None

    grouped: dict[str, list] = {}
    for h in hotels:
        entry = {
            "id": h.id,
            "hotel_name": h.hotel_name,
            "category": h.category,
            "star_rating": h.star_rating,
            "price_per_night_min": h.price_per_night_min,
            "price_per_night_max": h.price_per_night_max,
            "total_stay_estimate_inr": (
                int(h.price_per_night_min * (trip.duration or 1)
                    * ceil((trip.travelers or 1) / OCCUPANCY_PER_ROOM))
                if h.price_per_night_min else None
            ),
            "booking_url": h.booking_url,
            "partner": h.partner,
            "availability_score": h.availability_score,
            "is_current_selection": h.hotel_name == current_hotel_name,
        }
        grouped.setdefault(h.category or "unknown", []).append(entry)

    return jsonify({
        "destination": dest.name,
        "trip_duration_nights": trip.duration or 1,
        "travelers": trip.travelers or 1,
        "current_hotel": current_hotel_name,
        "hotels_by_category": grouped,
        "total_options": len(hotels),
        "tip": "Pick a hotel that works for you — or add your own custom hotel below.",
    }), 200


# ── Change Hotel ──────────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/hotel", methods=["PUT"])
@jwt_required()
def change_hotel(trip_id: int):
    """
    Replace the hotel across all days of the itinerary.

    Body (one of two forms):
      Form A — pick from our DB:
        { "hotel_id": 42 }

      Form B — enter your own hotel (you booked it elsewhere, or know one):
        {
          "custom_hotel_name": "My Haveli",
          "cost_per_night":    2500,
          "booking_url":       "https://...",   (optional)
          "star_rating":       4,               (optional)
          "category":          "mid",           (optional: budget/mid/luxury)
          "notes":             "Family-owned — ask for rooftop room"  (optional)
        }
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}

    # Build the new accommodation object
    if "hotel_id" in body:
        hotel = db.session.get(HotelPrice, body["hotel_id"])
        if not hotel:
            return jsonify({"error": "Hotel not found"}), 404
        new_accom = {
            "hotel_name": hotel.hotel_name,
            "cost_per_night": hotel.price_per_night_min or 0,
            "booking_url": hotel.booking_url or "",
            "star_rating": hotel.star_rating,
            "category": hotel.category,
            "_source": "db",
            "_hotel_id": hotel.id,
        }
    elif body.get("custom_hotel_name"):
        name = body["custom_hotel_name"].strip()
        if not name:
            return jsonify({"error": "custom_hotel_name cannot be empty"}), 400
        new_accom = {
            "hotel_name": name,
            "cost_per_night": body.get("cost_per_night", 0),
            "booking_url": _safe_hotel_url(body.get("booking_url")),
            "star_rating": body.get("star_rating"),
            "category": body.get("category", "mid"),
            "notes": body.get("notes"),
            "_source": "custom",
        }
    else:
        return jsonify({
            "error": "Provide either 'hotel_id' (from /hotel-options) or 'custom_hotel_name'."
        }), 400

    try:
        itinerary = copy.deepcopy(trip.itinerary_json or {})
        updated_days = 0
        for day in itinerary.get("itinerary", []):
            day["accommodation"] = new_accom
            updated_days += 1

        # Also update cost_breakdown if cost changed
        duration = trip.duration or 1
        travelers = trip.travelers or 1
        num_rooms = ceil(travelers / OCCUPANCY_PER_ROOM)
        new_hotel_total = new_accom["cost_per_night"] * duration * num_rooms
        if new_hotel_total > 0:
            itinerary.setdefault("cost_breakdown", {})["accommodation"] = new_hotel_total
            # Recompute total_cost
            breakdown = itinerary.get("cost_breakdown", {})
            itinerary["total_cost"] = sum(int(v) for v in breakdown.values())

        trip.itinerary_json = itinerary
        _mark_customized(trip)
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "hotel_changed_to": new_accom["hotel_name"],
            "cost_per_night": new_accom["cost_per_night"],
            "days_updated": updated_days,
            "message": (
                f"Hotel updated to '{new_accom['hotel_name']}' across all {updated_days} day(s). "
                + (f"Notes: {new_accom['notes']}" if new_accom.get("notes") else "")
            ),
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.change_hotel_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Add Activity ──────────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/day/<int:day_num>/activity/add", methods=["POST"])
@jwt_required()
def add_activity(trip_id: int, day_num: int):
    """
    Add an activity to a specific day.

    Form A — from our DB (you saw it in destination detail):
      { "attraction_id": 123 }

    Form B — completely custom (local dhaba, friend's shop, hidden spot):
      {
        "name":              "Local Pottery Workshop",   (required)
        "description":       "...",
        "type":              "cultural",
        "scheduled_time":    "15:00",   (optional; engine will fit it in if absent)
        "duration_minutes":  90,
        "cost":              500,
        "latitude":          26.92,     (optional; helps routing)
        "longitude":         75.81,
        "notes":             "Book via WhatsApp: +91 98765 43210"
      }

    The day schedule is re-optimised after insertion.
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    itinerary = copy.deepcopy(trip.itinerary_json or {})
    days = itinerary.get("itinerary", [])
    day_data = next((d for d in days if d.get("day") == day_num), None)

    if not day_data:
        return jsonify({"error": f"Day {day_num} not found in itinerary"}), 404

    # Build new activity entry
    if "attraction_id" in body:
        attr = db.session.get(Attraction, body["attraction_id"])
        if not attr:
            return jsonify({"error": "Attraction not found"}), 404

        # Check not already in this day
        existing_names = {a.get("name", "").lower() for a in day_data.get("activities", [])}
        if attr.name.lower() in existing_names:
            return jsonify({"error": f"'{attr.name}' is already in Day {day_num}"}), 409

        cost = int(((attr.entry_cost_min or 0) + (attr.entry_cost_max or 0)) / 2)
        new_act = {
            "_attraction_id": attr.id,
            "name": attr.name,
            "activity": attr.name,
            "description": attr.description or "",
            "type": attr.type or "general",
            "cost": cost,
            "is_break": False,
            "duration_minutes": int((attr.avg_visit_duration_hours or 1.5) * 60),
            "latitude": attr.latitude or attr.lat,
            "longitude": attr.longitude or attr.lng,
            "images": attr.gallery_images or [],
            "opening_hours": attr.opening_hours,
            "requires_advance_booking": bool(attr.requires_advance_booking),
            "difficulty_level": getattr(attr, "difficulty_level", "easy"),
            "is_photo_spot": bool(getattr(attr, "is_photo_spot", 0)),
            "dress_code": getattr(attr, "dress_code", None),
            "guide_available": bool(getattr(attr, "guide_available", 0)),
            "min_age": getattr(attr, "min_age", None),
            "queue_wait_minutes": getattr(attr, "queue_time_minutes", 0),
            "_source": "db",
        }
        source_label = attr.name

    elif body.get("name"):
        name = body["name"].strip()
        if not name:
            return jsonify({"error": "Activity name cannot be empty"}), 400

        new_act = {
            "_attraction_id": None,
            "name": name,
            "activity": name,
            "description": body.get("description", ""),
            "type": body.get("type", "general"),
            "cost": int(body.get("cost", 0)),
            "is_break": False,
            "duration_minutes": int(body.get("duration_minutes", 90)),
            "latitude": body.get("latitude"),
            "longitude": body.get("longitude"),
            "images": [],
            "opening_hours": None,
            "requires_advance_booking": False,
            "difficulty_level": "easy",
            "is_photo_spot": False,
            "dress_code": None,
            "guide_available": False,
            "min_age": None,
            "queue_wait_minutes": 0,
            "user_notes": body.get("notes", ""),
            "_source": "custom",
        }
        # If user gave a specific time, honour it as best_visit_time_hour preference
        if body.get("scheduled_time"):
            new_act["_preferred_time"] = body["scheduled_time"]
        source_label = f"custom: {name}"

    else:
        return jsonify({
            "error": "Provide 'attraction_id' (from our DB) or 'name' for a custom activity."
        }), 400

    try:
        # Insert new activity into day_data so _reoptimize_day includes it
        if new_act.get("_preferred_time"):
            new_act["time"] = new_act.pop("_preferred_time")
        day_data["activities"] = list(day_data.get("activities", [])) + [new_act]

        day_data = _reoptimize_day(trip, day_num, day_data)
        # If new_act was custom, the re-optimizer made a proxy from it — inject user_notes back
        if new_act.get("user_notes"):
            for a in day_data.get("activities", []):
                if a.get("name") == new_act["name"] and not a.get("is_break"):
                    a["user_notes"] = new_act["user_notes"]

        # Patch back into itinerary
        for i, d in enumerate(days):
            if d.get("day") == day_num:
                days[i] = day_data
        itinerary["itinerary"] = days

        trip.itinerary_json = itinerary
        _mark_customized(trip)
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "day": day_num,
            "activity_added": new_act["name"],
            "source": new_act["_source"],
            "updated_day": day_data,
            "message": f"'{new_act['name']}' added to Day {day_num} and schedule re-optimised.",
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.add_activity_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Remove Activity ───────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/day/<int:day_num>/activity/remove", methods=["DELETE"])
@jwt_required()
def remove_activity(trip_id: int, day_num: int):
    """
    Remove an activity from a day by name.  Day schedule is re-optimised.

    Body: { "activity_name": "Jama Masjid" }
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    activity_name = (body.get("activity_name") or "").strip()
    if not activity_name:
        return jsonify({"error": "activity_name is required"}), 400

    itinerary = copy.deepcopy(trip.itinerary_json or {})
    days = itinerary.get("itinerary", [])
    day_data = next((d for d in days if d.get("day") == day_num), None)
    if not day_data:
        return jsonify({"error": f"Day {day_num} not found"}), 404

    original_acts = day_data.get("activities", [])
    matched = next(
        (a for a in original_acts if not a.get("is_break") and a.get("name", "").lower() == activity_name.lower()),
        None,
    )
    if not matched:
        return jsonify({"error": f"Activity '{activity_name}' not found on Day {day_num}"}), 404

    try:
        # Remove from non-break list and re-optimise
        day_data["activities"] = [
            a for a in original_acts
            if not (not a.get("is_break") and a.get("name", "").lower() == activity_name.lower())
        ]
        day_data = _reoptimize_day(trip, day_num, day_data)

        for i, d in enumerate(days):
            if d.get("day") == day_num:
                days[i] = day_data
        itinerary["itinerary"] = days

        trip.itinerary_json = itinerary
        _mark_customized(trip)
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "day": day_num,
            "activity_removed": activity_name,
            "updated_day": day_data,
            "message": f"'{activity_name}' removed from Day {day_num}. Schedule re-optimised.",
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.remove_activity_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Edit Activity Details ─────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/day/<int:day_num>/activity/edit", methods=["PUT"])
@jwt_required()
def edit_activity(trip_id: int, day_num: int):
    """
    Edit specific details of an activity without re-scheduling the whole day.

    Useful for:
      • Overriding the engine's cost with what you actually paid
      • Adding a personal note ("My uncle runs this place — ask for discount")
      • Marking as visited / confirmed
      • Adjusting timing if you know a specific slot is sold out

    Body:
    {
      "activity_name":   "Amber Fort",       (required — identifies the activity)
      "cost_override":   800,                 (replace engine's estimated cost)
      "user_note":       "Book 9am slot online; queues are shortest then",
      "custom_description": "...",            (replace generated description)
      "scheduled_time":  "09:00",             (override time; other activities unchanged)
      "duration_minutes": 120                 (override duration)
    }
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    activity_name = (body.get("activity_name") or "").strip()
    if not activity_name:
        return jsonify({"error": "activity_name is required"}), 400

    itinerary = copy.deepcopy(trip.itinerary_json or {})
    days = itinerary.get("itinerary", [])
    day_data = next((d for d in days if d.get("day") == day_num), None)
    if not day_data:
        return jsonify({"error": f"Day {day_num} not found"}), 404

    target = next(
        (a for a in day_data.get("activities", [])
         if not a.get("is_break") and a.get("name", "").lower() == activity_name.lower()),
        None,
    )
    if not target:
        return jsonify({"error": f"Activity '{activity_name}' not found on Day {day_num}"}), 404

    try:
        # Apply allowed field updates
        changes = []
        if "cost_override" in body:
            target["cost"] = int(body["cost_override"])
            target["_cost_overridden"] = True
            changes.append(f"cost → ₹{body['cost_override']}")
        if "user_note" in body:
            target["user_note"] = body["user_note"]
            changes.append("note added")
        if "custom_description" in body:
            target["description"] = body["custom_description"]
            changes.append("description updated")
        if "scheduled_time" in body:
            target["time"] = body["scheduled_time"]
            target["_time_overridden"] = True
            changes.append(f"time → {body['scheduled_time']}")
        if "duration_minutes" in body:
            target["duration_minutes"] = int(body["duration_minutes"])
            changes.append(f"duration → {body['duration_minutes']}min")

        if not changes:
            return jsonify({"error": "No valid fields to update. Supported: cost_override, user_note, custom_description, scheduled_time, duration_minutes"}), 400

        for i, d in enumerate(days):
            if d.get("day") == day_num:
                days[i] = day_data
        itinerary["itinerary"] = days

        trip.itinerary_json = itinerary
        _mark_customized(trip)
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "day": day_num,
            "activity": activity_name,
            "changes_applied": changes,
            "updated_activity": target,
            "message": f"'{activity_name}' updated: {', '.join(changes)}.",
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.edit_activity_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Reorder Day ───────────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/day/<int:day_num>/reorder", methods=["PUT"])
@jwt_required()
def reorder_day(trip_id: int, day_num: int):
    """
    Manually reorder the activities in a day, then re-optimise timing.

    Body: { "activity_order": ["Amber Fort", "Jaigarh Fort", "Nahargarh Fort"] }

    Activities not listed are appended at the end.
    Re-optimises timing after reorder so start/end times are recalculated.
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    new_order: list[str] = body.get("activity_order", [])
    if not new_order:
        return jsonify({"error": "activity_order (list of activity names) is required"}), 400

    itinerary = copy.deepcopy(trip.itinerary_json or {})
    days = itinerary.get("itinerary", [])
    day_data = next((d for d in days if d.get("day") == day_num), None)
    if not day_data:
        return jsonify({"error": f"Day {day_num} not found"}), 404

    non_breaks = [a for a in day_data.get("activities", []) if not a.get("is_break")]
    name_map = {a.get("name", "").lower(): a for a in non_breaks}

    try:
        # Build ordered list per user's preference
        reordered = []
        for name in new_order:
            act = name_map.get(name.lower())
            if act:
                reordered.append(act)
        # Append any remaining activities the user didn't list
        listed_lower = {n.lower() for n in new_order}
        for act in non_breaks:
            if act.get("name", "").lower() not in listed_lower:
                reordered.append(act)

        # Replace activities in day_data and re-optimise timing
        day_data["activities"] = reordered
        day_data = _reoptimize_day(trip, day_num, day_data)

        for i, d in enumerate(days):
            if d.get("day") == day_num:
                days[i] = day_data
        itinerary["itinerary"] = days

        trip.itinerary_json = itinerary
        _mark_customized(trip)
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "day": day_num,
            "new_order": [a["name"] for a in day_data.get("activities", []) if not a.get("is_break")],
            "updated_day": day_data,
            "message": f"Day {day_num} activities reordered and timing re-optimised.",
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.reorder_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Trip Notes ────────────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/notes", methods=["PUT"])
@jwt_required()
def save_notes(trip_id: int):
    """
    Save personal notes for the trip and individual days.

    Body:
    {
      "trip":  "Pack light — we're doing lots of walking.  Extra rupee coins for temples.",
      "days": {
        "1": "Arrive by 2pm from Delhi. Pre-booked Ola cab (Rahul: +91 98765 43210).",
        "2": "Uncle's house for dinner — skip restaurant booking tonight.",
        "3": "Taj Mahal tickets already with travel agent, no need to book."
      }
    }

    Notes are merged with existing notes (day notes are per-key overwritten).
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    if not body.get("trip") and not body.get("days"):
        return jsonify({"error": "Provide 'trip' (string) and/or 'days' (object) notes"}), 400

    try:
        existing = trip.user_notes or {}
        updated = dict(existing)

        if "trip" in body:
            updated["trip"] = str(body["trip"])
        if "days" in body and isinstance(body["days"], dict):
            day_notes = updated.get("days", {})
            for day_key, note in body["days"].items():
                day_notes[str(day_key)] = str(note)
            updated["days"] = day_notes

        trip.user_notes = updated
        _mark_customized(trip)
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "user_notes": trip.user_notes,
            "message": "Notes saved successfully.",
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.notes_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Booking Customization ─────────────────────────────────────────────────────

@trip_editor_bp.route("/api/booking/<booking_id>/customize", methods=["PUT"])
@jwt_required()
def customize_booking(booking_id: str):
    """
    Edit a booking item before it is executed.

    Use cases:
      • You found a cheaper hotel on Booking.com — update the name, price, URL
      • You don't need the engine to book a restaurant — mark self_arranged
      • You have your own cab arranged — skip the daily_cab booking
      • Add a note for the booking (e.g. "Request non-smoking room")

    Body:
    {
      "item_name":     "Hotel Clarks Amer",    (optional — rename)
      "provider":      "My own booking",       (optional)
      "price_inr":     1800,                   (optional — override price)
      "booking_url":   "https://...",          (optional)
      "notes":         "Room on higher floor if possible",  (optional)
      "self_arranged": true                    (skip engine execution; you'll handle it)
    }
    """
    user_id = int(get_jwt_identity())
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.user_id != user_id:
        return jsonify({"error": "Booking not found"}), 404

    if booking.status in ("booked", "cancelled"):
        return jsonify({
            "error": f"Cannot edit a booking with status '{booking.status}'."
        }), 409

    body = request.get_json() or {}
    if not body:
        return jsonify({"error": "No fields provided to update"}), 400

    try:
        changes = []

        if "item_name" in body:
            booking.item_name = body["item_name"]
            changes.append(f"name → {body['item_name']}")
        if "provider" in body:
            booking.provider = body["provider"]
            changes.append(f"provider → {body['provider']}")
        if "price_inr" in body:
            booking.price_inr = int(body["price_inr"])
            booking.total_price_inr = int(body["price_inr"]) * (booking.num_travelers or 1)
            changes.append(f"price → ₹{body['price_inr']}")
        if "booking_url" in body:
            booking.booking_url = body["booking_url"]
            changes.append("booking_url updated")
        if "notes" in body:
            payload = dict(booking.payload or {})
            payload["user_notes"] = body["notes"]
            booking.payload = payload
            changes.append("notes added")
        if body.get("self_arranged"):
            booking.status = "self_arranged"
            booking.user_approved = 1   # pre-approved; just won't execute via engine
            booking.booking_ref = body.get("booking_ref") or "SELF-ARRANGED"
            changes.append("marked as self-arranged (engine will skip)")

        if not changes:
            return jsonify({"error": "No valid fields to update"}), 400

        db.session.commit()
        log.info(f"Booking {booking_id} customised by user {user_id}: {changes}")

        return jsonify({
            "booking_id": booking_id,
            "item_name": booking.item_name,
            "status": booking.status,
            "changes": changes,
            "message": f"Booking updated: {', '.join(changes)}.",
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.customize_booking_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Add Custom Booking ────────────────────────────────────────────────────────

@trip_editor_bp.route("/api/trip/<int:trip_id>/booking-plan/add-custom", methods=["POST"])
@jwt_required()
def add_custom_booking(trip_id: int):
    """
    Add a booking the user has already arranged themselves.

    Useful when:
      • You found and booked a hotel on your own
      • A travel agent arranged your flights
      • A local guide pre-arranged an activity
      • You want to track a booking from outside our system

    Body:
    {
      "type":          "hotel",                  (hotel/flight/activity/restaurant/cab/other)
      "item_name":     "Rambagh Palace",          (required)
      "provider":      "Direct with hotel",       (optional)
      "booking_ref":   "RPJ-2026-0325",           (optional — your ref number)
      "price_inr":     12000,                     (optional)
      "start_datetime":"2026-03-25T14:00",        (optional)
      "end_datetime":  "2026-03-28T12:00",        (optional)
      "notes":         "Ask for garden-view room" (optional)
    }

    The booking is immediately stored as status='self_arranged' with
    user_approved=1 so it appears in the booking dashboard but is not
    executed by the engine.
    """
    user_id = int(get_jwt_identity())
    trip = _get_trip_or_404(trip_id, user_id)
    if not trip:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    item_name = (body.get("item_name") or "").strip()
    if not item_name:
        return jsonify({"error": "item_name is required"}), 400

    booking_type = (body.get("type") or "other").lower()

    # Resolve or create permission request
    perm_req = (
        db.session.query(TripPermissionRequest)
        .filter_by(trip_id=trip_id, user_id=user_id)
        .order_by(TripPermissionRequest.created_at.desc())
        .first()
    )

    try:
        price_inr = int(body.get("price_inr", 0))
        num_travelers = trip.travelers or 1
        total_price = price_inr * num_travelers

        def _parse_dt(s):
            if not s:
                return None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            return None

        new_booking = Booking(
            id=str(uuid4()),
            trip_id=trip_id,
            user_id=user_id,
            permission_request_id=perm_req.id if perm_req else None,
            booking_type=booking_type,
            item_name=item_name,
            provider=body.get("provider", "Self-arranged"),
            booking_url=body.get("booking_url"),
            start_datetime=_parse_dt(body.get("start_datetime")),
            end_datetime=_parse_dt(body.get("end_datetime")),
            price_inr=price_inr,
            num_travelers=num_travelers,
            total_price_inr=total_price,
            status="self_arranged",
            user_approved=1,
            booking_ref=body.get("booking_ref", "SELF-ARRANGED"),
            payload={"notes": body.get("notes"), "user_added": True},
        )
        db.session.add(new_booking)

        # Update permission request snapshot
        if perm_req:
            snapshot = list(perm_req.items_snapshot or [])
            snapshot.append({
                "type": booking_type,
                "item_name": item_name,
                "provider": new_booking.provider,
                "price_inr": price_inr,
                "total_price_inr": total_price,
                "status": "self_arranged",
            })
            perm_req.items_snapshot = snapshot
            perm_req.total_estimated_cost_inr = (perm_req.total_estimated_cost_inr or 0) + total_price

        db.session.commit()
        log.info(f"Custom booking '{item_name}' added to trip {trip_id} by user {user_id}")

        return jsonify({
            "booking_id": new_booking.id,
            "item_name": item_name,
            "type": booking_type,
            "status": "self_arranged",
            "booking_ref": new_booking.booking_ref,
            "message": (
                f"'{item_name}' added to your booking plan as self-arranged. "
                "The engine will not attempt to book this — it's already taken care of."
            ),
        }), 201

    except Exception:
        db.session.rollback()
        log.exception("trip_editor.add_custom_booking_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500
