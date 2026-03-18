"""
routes/trip_tools.py — Trip Readiness, Daily Briefing & Activity Swap
═══════════════════════════════════════════════════════════════════════

Answers the questions travellers ask AFTER they have a plan but BEFORE they travel:

  GET  /api/trip/<id>/readiness
       "Am I ready to go?" — Checks visa, bookings, advance-booking activities,
       hotel confirmation, flights, insurance, and more.  Returns a readiness score.

  GET  /api/trip/<id>/daily-briefing/<day_num>
       "What do I need to know for Day 3?" — Weather alerts, activities, what to
       wear, what to carry, confirmed bookings, transport mode, emergency contacts.

  POST /api/trip/<id>/activity/swap
       "I don't want this temple — show me alternatives." — Replaces one activity
       in the itinerary with a different one from the same destination, then
       re-schedules the day and saves the updated itinerary.

  GET  /api/trip/<id>/next-trip-ideas
       "Where should I go next based on what I liked?" — Post-trip recommendations
       seeded from the completed trip's activity types and destination vibes.
"""

import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.database import db
from backend.engine.route_optimizer import RouteOptimizer
from backend.models import (
    Attraction, Booking, Destination, DestinationInfo, LocalEvent,
    Trip, TripPermissionRequest, WeatherAlert,
)

trip_tools_bp = Blueprint("trip_tools", __name__)
log = logging.getLogger(__name__)

# Items that should be advance-booked (checked in readiness)
_ADVANCE_BOOKING_TYPES = frozenset({"hotel", "flight", "airport_transfer"})

# Effort → carry items mapping for daily briefing
_CARRY_BY_TYPE = {
    "fort":      ["good walking shoes", "sunscreen", "water bottle", "hat"],
    "palace":    ["comfortable shoes", "camera", "ID proof"],
    "museum":    ["comfortable shoes", "notepad (optional)"],
    "beach":     ["sunscreen", "swimwear", "water shoes", "towel", "sunglasses"],
    "temple":    ["modest clothing (cover shoulders & knees)", "socks (for removing footwear)"],
    "mosque":    ["modest clothing (cover head)", "socks"],
    "church":    ["modest clothing"],
    "waterfall": ["waterproof bag", "change of clothes", "water shoes"],
    "trek":      ["sturdy shoes", "water bottle", "energy snacks", "rain jacket"],
    "natural":   ["sunscreen", "insect repellent", "water bottle"],
    "viewpoint": ["camera", "warm layer (breezy at top)"],
    "shopping":  ["carry bags", "cash for bargaining"],
    "restaurant":["nothing extra needed"],
    "cafe":      ["nothing extra needed"],
    "default":   ["water bottle", "comfortable shoes", "ID proof", "phone charger"],
}


def _get_carry_items(activity_types: list) -> list[str]:
    items: set[str] = set()
    for t in activity_types:
        carry = _CARRY_BY_TYPE.get(t.lower(), _CARRY_BY_TYPE["default"])
        items.update(carry)
    return sorted(items)


def _weather_wear_tip(alerts: list) -> str | None:
    if not alerts:
        return None
    types = {a.get("type", "") for a in alerts}
    if "rain" in types or "storm" in types:
        return "Carry a rain jacket or umbrella. Wear quick-dry clothing."
    if "extreme_heat" in types:
        return "Wear light, breathable clothing. Stay hydrated. Avoid midday sun."
    if "fog" in types:
        return "Visibility may be poor early morning. Allow extra travel time."
    return None


# ── Readiness Check ───────────────────────────────────────────────────────────

@trip_tools_bp.route("/api/trip/<int:trip_id>/readiness", methods=["GET"])
@jwt_required()
def trip_readiness(trip_id: int):
    """
    Comprehensive pre-departure readiness check.

    Returns a readiness_score (0-100) and a detailed checklist so the traveller
    knows exactly what is still pending before they leave.
    """
    user_id = int(get_jwt_identity())

    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != user_id:
        return jsonify({"error": "Trip not found"}), 404

    itinerary = trip.itinerary_json or {}
    checklist = []
    total_points = 0
    earned_points = 0

    def _check(item: str, category: str, status: bool, details: str = "", critical: bool = True, points: int = 10):
        nonlocal total_points, earned_points
        total_points += points
        if status:
            earned_points += points
        checklist.append({
            "item": item,
            "category": category,
            "status": "done" if status else "pending",
            "critical": critical,
            "details": details,
        })

    # ── Trip basics ────────────────────────────────────────────────────────────
    _check(
        "Travel dates confirmed",
        "basics",
        bool(trip.start_date),
        trip.start_date or "Start date not set — update the trip.",
    )
    _check(
        "Trip duration set",
        "basics",
        bool(trip.duration and trip.duration > 0),
        f"{trip.duration} days" if trip.duration else "Duration missing.",
    )

    # ── Bookings ───────────────────────────────────────────────────────────────
    try:
        bookings = db.session.query(Booking).filter_by(
            trip_id=trip_id, user_id=user_id
        ).all()
        booked_types = {b.booking_type for b in bookings if b.status == "booked"}

        _check(
            "Hotel confirmed",
            "bookings",
            "hotel" in booked_types,
            "Hotel booking confirmed." if "hotel" in booked_types else "Hotel not yet booked.",
        )
        _check(
            "Outbound flight confirmed",
            "bookings",
            "flight" in booked_types,
            "Flight confirmed." if "flight" in booked_types else "Book your outbound flight.",
        )
        _check(
            "Airport transfer on arrival day",
            "bookings",
            "airport_transfer" in booked_types,
            "Transfer booked." if "airport_transfer" in booked_types else "Book airport pickup to avoid inflated walk-in fares.",
            critical=False, points=5,
        )
        _check(
            "Daily transport arranged",
            "bookings",
            "daily_cab" in booked_types,
            "Daily cabs pre-booked." if "daily_cab" in booked_types else "Consider pre-booking day-use cabs.",
            critical=False, points=5,
        )

        # Advance-booking activities not yet booked
        advance_acts = []
        for day in itinerary.get("itinerary", []):
            for act in day.get("activities", []):
                if act.get("requires_advance_booking") and not act.get("is_break"):
                    act_name = act.get("name", "")
                    already_booked = any(
                        b.item_name == act_name and b.status == "booked"
                        for b in bookings
                    )
                    if not already_booked:
                        advance_acts.append(act_name)

        _check(
            "Advance-booking attractions ticketed",
            "bookings",
            len(advance_acts) == 0,
            "All advance-booking attractions are ticketed." if not advance_acts
            else f"Book tickets in advance: {', '.join(advance_acts[:5])}.",
        )

    except Exception as e:
        log.warning(f"Readiness booking check failed: {e}")

    # ── Visa & Entry ───────────────────────────────────────────────────────────
    try:
        dest_name = (itinerary.get("itinerary") or [{}])[0].get("location") if itinerary.get("itinerary") else None
        dest = None
        if dest_name:
            dest = db.session.query(Destination).filter_by(name=dest_name).first()
        if dest:
            dest_info = db.session.query(DestinationInfo).filter_by(
                destination_id=dest.id
            ).first()
            if dest_info and dest_info.visa_notes:
                _check(
                    "Visa / entry requirements reviewed",
                    "documents",
                    False,  # cannot auto-verify — requires user confirmation
                    dest_info.visa_notes,
                    points=8,
                )
            else:
                _check(
                    "Entry requirements checked",
                    "documents",
                    True,
                    "No specific visa requirements flagged for this destination.",
                    points=8,
                )
    except Exception as e:
        log.warning(f"Readiness visa check failed: {e}")

    # ── Documents ─────────────────────────────────────────────────────────────
    _check(
        "Valid ID / Passport available",
        "documents",
        False,  # self-declaration — always pending until user confirms
        "Ensure passport/Aadhar is valid and available. Check expiry date.",
    )
    _check(
        "Travel insurance arranged",
        "documents",
        False,  # cannot auto-verify
        "Strongly recommended — covers medical emergencies, cancellations, and baggage loss.",
        critical=False, points=5,
    )

    # ── Health & Safety ────────────────────────────────────────────────────────
    try:
        if dest_info := (db.session.query(DestinationInfo).filter_by(destination_id=dest.id).first() if dest else None):
            if dest_info.vaccinations_recommended:
                _check(
                    "Vaccinations / health precautions",
                    "health",
                    False,
                    f"Recommended: {', '.join(dest_info.vaccinations_recommended)}",
                    critical=False, points=5,
                )
            if dest_info.water_safety and dest_info.water_safety != "tap":
                _check(
                    "Water safety noted",
                    "health",
                    True,
                    f"Use {dest_info.water_safety} water at this destination.",
                    critical=False, points=3,
                )
    except Exception:
        pass

    _check(
        "Basic medications packed",
        "health",
        False,
        "Pack ORS, antacids, pain relief, antihistamine, and any personal prescriptions.",
        critical=False, points=5,
    )

    # ── Score ─────────────────────────────────────────────────────────────────
    readiness_score = int((earned_points / total_points) * 100) if total_points else 0
    critical_pending = [c for c in checklist if c["status"] == "pending" and c["critical"]]

    status_label = (
        "Ready to go!" if readiness_score >= 80 and not critical_pending
        else "Almost ready" if readiness_score >= 60
        else "Action required"
    )

    return jsonify({
        "trip_id": trip_id,
        "trip_title": trip.trip_title,
        "start_date": trip.start_date,
        "readiness_score": readiness_score,
        "status": status_label,
        "critical_pending_count": len(critical_pending),
        "checklist": checklist,
        "critical_actions": [c["item"] for c in critical_pending],
    }), 200


# ── Daily Briefing ────────────────────────────────────────────────────────────

@trip_tools_bp.route("/api/trip/<int:trip_id>/daily-briefing/<int:day_num>", methods=["GET"])
@jwt_required()
def daily_briefing(trip_id: int, day_num: int):
    """
    Day-before or morning briefing for a specific day.

    Returns everything the traveller needs to know:
    activities, timing, what to wear, what to carry, confirmed bookings,
    weather alerts, crowd warnings, emergency contacts.
    """
    user_id = int(get_jwt_identity())

    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != user_id:
        return jsonify({"error": "Trip not found"}), 404

    itinerary = trip.itinerary_json or {}
    days = itinerary.get("itinerary", [])

    # Find the requested day
    day_data = next((d for d in days if d.get("day") == day_num), None)
    if not day_data:
        return jsonify({"error": f"Day {day_num} not found in itinerary"}), 404

    # Compute actual date for this day
    date_str = None
    if trip.start_date:
        try:
            base = datetime.strptime(trip.start_date, "%Y-%m-%d")
            day_date = base + timedelta(days=day_num - 1)
            date_str = day_date.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Activities (non-break)
    activities = day_data.get("activities", [])
    real_activities = [a for a in activities if not a.get("is_break")]
    activity_types = [a.get("type", "general") for a in real_activities]

    # What to carry
    carry_items = _get_carry_items(activity_types)

    # Dress code — aggregate from activities
    dress_codes = list({
        a.get("dress_code") for a in real_activities
        if a.get("dress_code")
    })

    # What to wear (weather-aware)
    wear_tip = None
    weather_alerts = []
    if date_str:
        try:
            dest_name = day_data.get("location")
            if dest_name:
                dest = db.session.query(Destination).filter_by(name=dest_name).first()
                if dest:
                    alerts = db.session.query(WeatherAlert).filter_by(
                        destination_id=dest.id,
                        alert_date=date_str,
                    ).all()
                    weather_alerts = [
                        {
                            "type": a.alert_type,
                            "severity": a.severity,
                            "probability_pct": a.probability_pct,
                            "description": a.description,
                        }
                        for a in alerts
                    ]
                    wear_tip = _weather_wear_tip(weather_alerts)
        except Exception as e:
            log.warning(f"Daily briefing weather check: {e}")

    # Confirmed bookings for this day
    day_bookings = []
    if date_str:
        try:
            bookings = db.session.query(Booking).filter_by(
                trip_id=trip_id, user_id=user_id, status="booked"
            ).all()
            for b in bookings:
                if b.start_datetime and b.start_datetime.strftime("%Y-%m-%d") == date_str:
                    day_bookings.append({
                        "type": b.booking_type,
                        "item_name": b.item_name,
                        "time": b.start_datetime.strftime("%H:%M") if b.start_datetime else None,
                        "booking_ref": b.booking_ref,
                        "provider": b.provider,
                    })
        except Exception as e:
            log.warning(f"Daily briefing bookings: {e}")

    # Local events happening today
    day_events = []
    if date_str:
        try:
            dest_name = day_data.get("location")
            if dest_name:
                dest = db.session.query(Destination).filter_by(name=dest_name).first()
                if dest:
                    events = db.session.query(LocalEvent).filter(
                        LocalEvent.destination_id == dest.id,
                        LocalEvent.start_date <= date_str,
                    ).filter(
                        (LocalEvent.end_date.is_(None)) | (LocalEvent.end_date >= date_str)
                    ).all()
                    day_events = [
                        {"name": ev.name, "type": ev.event_type, "impact": ev.impact, "tips": ev.tips}
                        for ev in events
                    ]
        except Exception as e:
            log.warning(f"Daily briefing events: {e}")

    # Emergency contacts
    emergency_contacts = {}
    try:
        dest_name = day_data.get("location")
        if dest_name:
            dest = db.session.query(Destination).filter_by(name=dest_name).first()
            if dest:
                dest_info = db.session.query(DestinationInfo).filter_by(
                    destination_id=dest.id
                ).first()
                if dest_info:
                    emergency_contacts = dest_info.emergency_contacts or {}
    except Exception:
        pass

    if not emergency_contacts:
        emergency_contacts = {
            "police": "100",
            "ambulance": "102 / 108",
            "fire": "101",
            "tourist_helpline": "1800-111-363",
        }

    # Photo spots for today
    photo_spots = [a["name"] for a in real_activities if a.get("is_photo_spot")]

    # Advance-booking warning
    advance_needed = [
        a["name"] for a in real_activities
        if a.get("requires_advance_booking")
        and not any(
            b["item_name"] == a["name"]
            for b in day_bookings
        )
    ]

    # Crowd warnings
    crowd_warnings = [
        f"{a['name']}: {a['crowd_level_at_visit']}/100 crowd level"
        for a in real_activities
        if (a.get("crowd_level_at_visit") or 0) >= 70
    ]

    return jsonify({
        "trip_id": trip_id,
        "day": day_num,
        "date": date_str,
        "location": day_data.get("location"),
        "theme": day_data.get("theme"),
        "pacing_level": day_data.get("pacing_level"),
        "activities": activities,
        "what_to_carry": carry_items,
        "dress_code": dress_codes,
        "wear_tip": wear_tip or "Comfortable clothes and walking shoes recommended.",
        "weather_alerts": weather_alerts,
        "confirmed_bookings_today": day_bookings,
        "local_events_today": day_events,
        "advance_booking_needed": advance_needed,
        "crowd_warnings": crowd_warnings,
        "photo_spots": photo_spots,
        "emergency_contacts": emergency_contacts,
        "morning_tip": _morning_tip(day_data, advance_needed, weather_alerts),
    }), 200


def _morning_tip(day_data: dict, advance_needed: list, alerts: list) -> str:
    tips = []
    if advance_needed:
        tips.append(f"Book tickets for {advance_needed[0]} before you leave the hotel.")
    if alerts:
        tips.append("Check the weather before heading out — alerts are active today.")
    pacing = day_data.get("pacing_level", "moderate")
    if pacing == "intense":
        tips.append("It's a packed day — start on time and keep breaks short.")
    elif pacing == "relaxed":
        tips.append("Easy day ahead — enjoy the pace without rushing.")
    first_activity = next(
        (a for a in day_data.get("activities", []) if not a.get("is_break")), None
    )
    if first_activity:
        tips.append(f"First stop: {first_activity.get('name')} at {first_activity.get('time')}.")
    return " ".join(tips) if tips else "Have a wonderful day!"


# ── Activity Swap ─────────────────────────────────────────────────────────────

@trip_tools_bp.route("/api/trip/<int:trip_id>/activity/swap", methods=["POST"])
@jwt_required()
def swap_activity(trip_id: int):
    """
    Replace one activity in a saved trip's itinerary with a better alternative.

    Body:
      day_num:           int    — which day to modify
      activity_name:     str    — exact name of the activity to replace
      preferred_type:    str    — optional type preference for the replacement
                                  (e.g. "museum", "beach", "park")

    The engine:
      1. Identifies the destination for that day.
      2. Finds alternative attractions of a similar type that aren't already
         in the itinerary.
      3. Replaces the activity and re-runs RouteOptimizer for that day.
      4. Saves the updated itinerary to the Trip record.
      5. Returns the updated day schedule.
    """
    user_id = int(get_jwt_identity())

    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != user_id:
        return jsonify({"error": "Trip not found"}), 404

    body = request.get_json() or {}
    day_num = body.get("day_num")
    activity_name = body.get("activity_name", "").strip()
    preferred_type = (body.get("preferred_type") or "").strip().lower()

    if not day_num or not activity_name:
        return jsonify({"error": "day_num and activity_name are required"}), 400

    itinerary = trip.itinerary_json or {}
    days = itinerary.get("itinerary", [])
    day_data = next((d for d in days if d.get("day") == day_num), None)

    if not day_data:
        return jsonify({"error": f"Day {day_num} not found in itinerary"}), 404

    # Find the activity to replace
    target_act = next(
        (a for a in day_data.get("activities", [])
         if not a.get("is_break") and a.get("name", "").strip().lower() == activity_name.lower()),
        None,
    )
    if not target_act:
        return jsonify({"error": f"Activity '{activity_name}' not found on Day {day_num}"}), 404

    target_type = preferred_type or target_act.get("type", "general")
    location_name = day_data.get("location")

    # Find replacement candidates
    try:
        dest = db.session.query(Destination).filter_by(name=location_name).first()
        if not dest:
            return jsonify({"error": f"Destination '{location_name}' not found in DB"}), 404

        # Names already in the full itinerary (to avoid repeats)
        used_names: set[str] = set()
        for d in days:
            for a in d.get("activities", []):
                if not a.get("is_break"):
                    used_names.add((a.get("name") or "").lower())

        # Query alternatives — same type first, fallback to any type
        candidates = (
            db.session.query(Attraction)
            .filter_by(destination_id=dest.id)
            .filter(Attraction.type == target_type)
            .filter(Attraction.popularity_score >= 25)
            .order_by(Attraction.popularity_score.desc())
            .limit(20)
            .all()
        )
        if not candidates:
            candidates = (
                db.session.query(Attraction)
                .filter_by(destination_id=dest.id)
                .filter(Attraction.popularity_score >= 25)
                .order_by(Attraction.popularity_score.desc())
                .limit(20)
                .all()
            )

        # Filter out already-used ones
        alternatives = [
            c for c in candidates
            if c.name.lower() not in used_names
            and c.name.lower() != activity_name.lower()
        ]
        if not alternatives:
            return jsonify({
                "error": "No suitable alternative found for this activity at this destination.",
                "suggestion": "Try a different preferred_type or remove the activity instead.",
            }), 422

        replacement = alternatives[0]

        # Replace in the day's activity list
        current_activities_non_break = [
            a for a in day_data["activities"] if not a.get("is_break")
        ]
        idx = next(
            (i for i, a in enumerate(current_activities_non_break)
             if a.get("name", "").lower() == activity_name.lower()),
            None,
        )

        # Build new activity object to slot in
        new_act_obj = type("_AttrProxy", (), {
            "id": replacement.id,
            "name": replacement.name,
            "description": replacement.description,
            "type": replacement.type,
            "entry_cost_min": replacement.entry_cost_min,
            "entry_cost_max": replacement.entry_cost_max,
            "avg_visit_duration_hours": replacement.avg_visit_duration_hours,
            "best_visit_time_hour": replacement.best_visit_time_hour,
            "latitude": replacement.latitude or replacement.lat,
            "longitude": replacement.longitude or replacement.lng,
            "lat": replacement.lat,
            "lng": replacement.lng,
            "gallery_images": replacement.gallery_images,
            "opening_hours": replacement.opening_hours,
            "crowd_level_by_hour": replacement.crowd_level_by_hour,
            "requires_advance_booking": replacement.requires_advance_booking,
            "difficulty_level": getattr(replacement, "difficulty_level", "easy"),
            "is_photo_spot": getattr(replacement, "is_photo_spot", 0),
            "best_photo_hour": getattr(replacement, "best_photo_hour", None),
            "queue_time_minutes": getattr(replacement, "queue_time_minutes", 0),
            "dress_code": getattr(replacement, "dress_code", None),
            "guide_available": getattr(replacement, "guide_available", 0),
            "min_age": getattr(replacement, "min_age", None),
            "connects_well_with": replacement.connects_well_with,
        })()

        # Replace in pool then re-optimize the day
        current_pool = [
            a for a in candidates
            if a.name.lower() != activity_name.lower()
        ][:1] + alternatives[:5]

        # Re-run route optimizer on the updated pool
        date_str = "2026-01-01"
        if trip.start_date:
            try:
                base = datetime.strptime(trip.start_date, "%Y-%m-%d")
                date_str = (base + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Build the full new attraction list for this day (replace target)
        new_pool = []
        for a in current_activities_non_break:
            if a.get("name", "").lower() == activity_name.lower():
                new_pool.append(new_act_obj)
            else:
                # Re-use the existing attraction objects from DB
                existing = db.session.query(Attraction).filter_by(
                    destination_id=dest.id, name=a.get("name")
                ).first()
                if existing:
                    new_pool.append(existing)

        num_days = trip.duration or 1
        day_type = (
            "arrival" if day_num == 1 and num_days > 1
            else "departure" if day_num == num_days and num_days > 1
            else "normal"
        )
        updated_route = RouteOptimizer().optimize(new_pool, date_str, day_type=day_type)

        # Patch the itinerary
        day_data["activities"] = updated_route["activities"]
        day_data["pacing_level"] = updated_route["pacing_level"]

        trip.itinerary_json = itinerary
        db.session.commit()

        return jsonify({
            "trip_id": trip_id,
            "day": day_num,
            "swapped_out": activity_name,
            "swapped_in": replacement.name,
            "replacement_type": replacement.type,
            "updated_day": day_data,
            "message": (
                f"'{activity_name}' replaced with '{replacement.name}' on Day {day_num}. "
                "Schedule has been re-optimised."
            ),
        }), 200

    except Exception:
        db.session.rollback()
        log.exception("trip_tools.swap_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


# ── Next Trip Ideas ───────────────────────────────────────────────────────────

@trip_tools_bp.route("/api/trip/<int:trip_id>/next-trip-ideas", methods=["GET"])
@jwt_required()
def next_trip_ideas(trip_id: int):
    """
    Post-trip recommendations based on what the traveller did.

    Reads the completed trip's activity types and finds destinations with
    high concentrations of similar attractions.
    """
    user_id = int(get_jwt_identity())

    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != user_id:
        return jsonify({"error": "Trip not found"}), 404

    itinerary = trip.itinerary_json or {}

    # Collect activity types from the completed trip
    type_counts: dict[str, int] = {}
    for day in itinerary.get("itinerary", []):
        for act in day.get("activities", []):
            if not act.get("is_break"):
                t = (act.get("type") or "general").lower()
                type_counts[t] = type_counts.get(t, 0) + 1

    top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    preferred_types = [t for t, _ in top_types]

    try:
        # Find destinations with attractions matching these types
        dest_scores: dict[int, int] = {}
        for attr_type in preferred_types:
            matches = (
                db.session.query(Attraction.destination_id)
                .filter(Attraction.type == attr_type)
                .filter(Attraction.popularity_score >= 40)
                .all()
            )
            for (did,) in matches:
                dest_scores[did] = dest_scores.get(did, 0) + 1

        # Exclude current trip's destinations
        visited_dest = itinerary.get("itinerary", [{}])[0].get("location")
        if visited_dest:
            skip_dest = db.session.query(Destination).filter_by(name=visited_dest).first()
            if skip_dest:
                dest_scores.pop(skip_dest.id, None)

        top_dest_ids = sorted(dest_scores.items(), key=lambda x: x[1], reverse=True)[:6]
        dest_ids = [did for did, _ in top_dest_ids]

        destinations = db.session.query(Destination).filter(
            Destination.id.in_(dest_ids)
        ).all()
        dest_map = {d.id: d for d in destinations}

        results = []
        for did, type_match_count in top_dest_ids:
            d = dest_map.get(did)
            if not d:
                continue
            results.append({
                "id": d.id,
                "name": d.name,
                "location": d.location,
                "image": d.image,
                "tag": d.tag,
                "rating": d.rating,
                "estimated_cost_per_day": d.estimated_cost_per_day,
                "vibe_tags": getattr(d, "vibe_tags", []) or [],
                "highlights": getattr(d, "highlights", []) or [],
                "why_youll_love_it": (
                    f"You enjoyed {', '.join(preferred_types[:2])} activities — "
                    f"{d.name} has lots more of what you loved."
                ),
            })

        return jsonify({
            "based_on_trip": trip.trip_title or f"Trip #{trip_id}",
            "your_top_interests": preferred_types,
            "ideas": results,
        }), 200

    except Exception:
        log.exception("trip_tools.next_trip_ideas_failed")
        return jsonify({"error": "Internal server error"}), 500
