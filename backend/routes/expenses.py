"""
routes/expenses.py — Trip Expense Tracker
══════════════════════════════════════════

Allows users to log actual spending against a saved trip so they can compare
planned vs actual costs per category and per day.

Endpoints
---------
  POST /api/trip/<trip_id>/expense
      Log a new expense entry.
      Body: {category, description?, amount_inr, trip_day?}

  GET  /api/trip/<trip_id>/expenses
      List all expenses with a per-category and per-day summary comparing
      planned (from itinerary cost_breakdown) vs actual spend.

  DELETE /api/expense/<expense_id>
      Remove a logged expense.
"""

import structlog
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate
from backend.utils.responses import normalize_api_response

from backend.database import db
from backend.models import ExpenseEntry, Trip

expenses_bp = Blueprint("expenses", __name__)
log = structlog.get_logger(__name__)


@expenses_bp.after_request
def _normalize_expenses_response(response):
    return normalize_api_response(response)

_VALID_CATEGORIES = frozenset({
    "accommodation", "food", "transport", "activity", "shopping", "misc",
})


class AddExpenseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    category    = fields.Str(required=True, validate=validate.OneOf(list(_VALID_CATEGORIES)))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    amount_inr  = fields.Int(required=True, validate=validate.Range(min=1))
    trip_day    = fields.Int(required=False, allow_none=True, validate=validate.Range(min=1, max=100))


@expenses_bp.route("/api/trip/<int:trip_id>/expense", methods=["POST"])
@jwt_required()
def add_expense(trip_id: int):
    """Log a new expense for a saved trip."""
    user_id = int(get_jwt_identity())

    body = request.get_json() or {}
    schema = AddExpenseSchema()
    try:
        data = schema.load(body)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        entry = ExpenseEntry(
            trip_id=trip_id,
            user_id=user_id,
            category=data["category"],
            description=data.get("description"),
            amount_inr=data["amount_inr"],
            trip_day=data.get("trip_day"),
        )
        db.session.add(entry)
        db.session.commit()

        log.info(f"Expense logged: trip={trip_id} category={data['category']} amount=₹{data['amount_inr']}")

        return jsonify({
            "id": entry.id,
            "trip_id": trip_id,
            "category": entry.category,
            "description": entry.description,
            "amount_inr": entry.amount_inr,
            "trip_day": entry.trip_day,
            "recorded_at": entry.recorded_at.isoformat() if entry.recorded_at else None,
        }), 201

    except Exception:
        db.session.rollback()
        log.exception("expense.add_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@expenses_bp.route("/api/trip/<int:trip_id>/expenses", methods=["GET"])
@jwt_required()
def get_expenses(trip_id: int):
    """
    List all expenses for a trip with planned vs actual summary.

    Returns:
      - entries: all individual expense records
      - actual_by_category: {category: total_spent}
      - planned_by_category: {category: planned_amount} from itinerary cost_breakdown
      - variance_by_category: {category: {actual, planned, diff, over_budget}}
      - total_actual_inr: sum of all logged expenses
      - total_planned_inr: itinerary total_cost
      - by_day: {day_num: total_spent_that_day}
    """
    user_id = int(get_jwt_identity())

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        entries = (
            db.session.query(ExpenseEntry)
            .filter_by(trip_id=trip_id, user_id=user_id)
            .order_by(ExpenseEntry.recorded_at)
            .all()
        )

        # Actual spend per category
        actual_by_category: dict[str, int] = {}
        by_day: dict[str, int] = {}
        for e in entries:
            actual_by_category[e.category] = actual_by_category.get(e.category, 0) + e.amount_inr
            if e.trip_day:
                day_key = str(e.trip_day)
                by_day[day_key] = by_day.get(day_key, 0) + e.amount_inr

        total_actual = sum(actual_by_category.values())

        # Planned spend from itinerary cost_breakdown
        itinerary = trip.itinerary_json or {}
        planned_breakdown = itinerary.get("cost_breakdown", {})
        total_planned = itinerary.get("total_cost", trip.total_cost or 0)

        variance: dict = {}
        all_cats = _VALID_CATEGORIES | set(actual_by_category.keys())
        for cat in all_cats:
            actual = actual_by_category.get(cat, 0)
            planned = int(planned_breakdown.get(cat, 0))
            diff = actual - planned
            variance[cat] = {
                "actual_inr": actual,
                "planned_inr": planned,
                "diff_inr": diff,
                "over_budget": diff > 0 and planned > 0,
            }

        serialized_entries = [
            {
                "id": e.id,
                "category": e.category,
                "description": e.description,
                "amount_inr": e.amount_inr,
                "trip_day": e.trip_day,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
            }
            for e in entries
        ]

        return jsonify({
            "trip_id": trip_id,
            "entries": serialized_entries,
            "actual_by_category": actual_by_category,
            "planned_by_category": {k: int(v) for k, v in planned_breakdown.items()},
            "variance_by_category": variance,
            "by_day": by_day,
            "total_actual_inr": total_actual,
            "total_planned_inr": int(total_planned),
            "savings_or_overspend_inr": int(total_planned) - total_actual,
        }), 200

    except Exception:
        log.exception("expense.get_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500


@expenses_bp.route("/api/expense/<int:expense_id>", methods=["DELETE"])
@jwt_required()
def delete_expense(expense_id: int):
    """Delete a logged expense."""
    user_id = int(get_jwt_identity())

    try:
        entry = db.session.get(ExpenseEntry, expense_id)
        if not entry or entry.user_id != user_id:
            return jsonify({"error": "Expense not found"}), 404

        db.session.delete(entry)
        db.session.commit()
        return jsonify({"message": "Expense deleted."}), 200

    except Exception:
        db.session.rollback()
        log.exception("expense.delete_failed")
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500
