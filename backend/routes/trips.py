from uuid import uuid4

from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
import structlog

from backend.database import db
from backend.engine.orchestrator import TripGenerationOrchestrator
from backend.extensions import limiter
from backend.models import AnalyticsEvent, AsyncJob, Trip
from backend.request_validation import load_request_json
from backend.schemas import GenerateItinerarySchema, SaveTripSchema
from backend.services.gemini_service import get_gemini_service
from backend.services.cache_service import get_cached, set_cached
from backend.utils.responses import normalize_api_response
from backend.utils.helpers import _extract_destination_names, _is_truthy

trips_bp = Blueprint("trips", __name__)
log = structlog.get_logger(__name__)
GEMINI_SERVICE = get_gemini_service()


@trips_bp.after_request
def _normalize_trips_response(response):
    return normalize_api_response(response)


@trips_bp.route("/generate-itinerary", methods=["POST"])
@limiter.limit("5 per minute")
def generate_itinerary():
    # Throttle anonymous itinerary generation so one IP cannot exhaust API quota.
    data, error = load_request_json(GenerateItinerarySchema())
    if error:
        return error

    destination_names = _extract_destination_names(data)
    if not destination_names:
        return jsonify({"error": "At least one selected destination is required"}), 400

    try:
        request_user_id = None
        try:
            verify_jwt_in_request(optional=True)
            request_user_id = get_jwt_identity()
        except Exception as exc:
            log.warning(f"Could not verify JWT for itinerary job: {exc}")

        job_id = str(uuid4())

        cache_prefs = {
            "origin_city": data["start_city"],
            "destination_names": sorted(destination_names),
            "budget": data["budget"],
            "duration": data["duration"],
            "travelers": data.get("travelers", 1),
            "style": data.get("style", "standard"),
            "traveler_type": data.get("traveler_type", "couple"),
            "travel_month": data.get("travel_month", "any"),
            "start_date": data.get("start_date"),
            # Include all user-visible parameters so two requests that differ only
            # in interests or date_type don't incorrectly share a cached result.
            "interests": sorted(data.get("interests") or []),
            "date_type": data.get("date_type", "fixed"),
            "use_engine": data.get("use_engine", True),
            # Traveler-specific params that change the filtered pool
            "dietary_restrictions": sorted(data.get("dietary_restrictions") or []),
            "accessibility": data.get("accessibility", 0),
            "children_count": data.get("children_count", 0),
        }
        cached_result = get_cached(cache_prefs)
        if cached_result:
            job = AsyncJob(
                id=job_id,
                user_id=request_user_id,
                status="completed",
                payload=data,
                result=cached_result,
            )
            db.session.add(job)
            db.session.commit()
            log.info("Returning cached itinerary via completed async job")
            return jsonify({"job_id": job_id, "status": "completed"}), 202

        job = AsyncJob(
            id=job_id,
            user_id=request_user_id,
            status="queued",
            payload=data,
        )
        db.session.add(job)
        db.session.add(AnalyticsEvent(
            event_type="GenerateItineraryQueued",
            user_id=request_user_id,
            # Store only metadata (not full itinerary) to keep payload size small
            # and prevent truncation of the JSON column.
            payload={
                "job_id": job_id,
                "origin_city": data["start_city"],
                "selected_destination_names": destination_names,
                "budget": data["budget"],
                "duration": data["duration"],
                "travelers": data.get("travelers", 1),
                "style": data.get("style", "standard"),
                "traveler_type": data.get("traveler_type", "couple"),
                "travel_month": data.get("travel_month", "any"),
                "use_engine": data.get("use_engine", True),
            },
        ))
        db.session.commit()

        # Offload itinerary generation to Celery so long-running Gemini calls do not occupy request workers.
        from backend.celery_tasks import generate_itinerary_job
        generate_itinerary_job.delay(job_id)

        return jsonify({"job_id": job_id, "status": "queued"}), 202

    except Exception:
        db.session.rollback()
        log.exception("itinerary.generation_failed")
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None)
        }), 500


@trips_bp.route("/generate-variants", methods=["POST"])
@limiter.limit("3 per minute")
def generate_variants():
    """
    Generate three plan variants (relaxed / balanced / intense) for the same
    trip parameters in one call. Returns all three itineraries together so
    the traveller can pick the density that suits them.
    """
    data, error = load_request_json(GenerateItinerarySchema())
    if error:
        return error

    destination_names = _extract_destination_names(data)
    if not destination_names:
        return jsonify({"error": "At least one selected destination is required"}), 400

    try:
        request_user_id = None
        try:
            verify_jwt_in_request(optional=True)
            request_user_id = get_jwt_identity()
        except Exception:
            pass

        orchestrator = TripGenerationOrchestrator(
            db_session=db.session,
            gemini_service=GEMINI_SERVICE,
        )
        variants = orchestrator.generate_variants(data, request_user_id=request_user_id)

        return jsonify({"variants": variants}), 200

    except Exception:
        db.session.rollback()
        log.exception("variants.generation_failed")
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None),
        }), 500


@trips_bp.route("/get-itinerary-status/<job_id>", methods=["GET"])
@limiter.limit("60 per minute")
def get_itinerary_status(job_id):
    try:
        job = db.session.get(AsyncJob, job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Ownership check: if the job was created by a logged-in user, only that
        # user may poll it. Anonymous jobs (user_id=None) remain publicly accessible.
        if job.user_id is not None:
            try:
                verify_jwt_in_request(optional=True)
                caller_id = get_jwt_identity()
                if caller_id is None or int(caller_id) != job.user_id:
                    return jsonify({"error": "Job not found"}), 404
            except Exception:
                return jsonify({"error": "Job not found"}), 404

        body = {
            "job_id": job.id,
            "status": job.status,
        }
        if job.result is not None:
            body["result"] = job.result
        if job.error_message:
            body["error"] = job.error_message
        return jsonify(body), 200
    except Exception:
        log.exception("itinerary.status_fetch_failed")
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None)
        }), 500


@trips_bp.route("/get-itinerary-status/<job_id>/stream", methods=["GET"])
def stream_itinerary_status(job_id):
    """
    SSE endpoint that pushes a single event when the job completes or fails.
    Eliminates the need for the frontend to poll GET /get-itinerary-status.

    Emits: data: {"job_id": "...", "status": "completed"|"failed"}

    Falls back to periodic DB checks when Redis is unavailable.
    """
    import json
    import time
    from flask import Response, stream_with_context
    from backend.services.metrics_service import get_metrics_redis

    # Validate job existence and ownership before opening the stream
    try:
        job = db.session.get(AsyncJob, job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        if job.user_id is not None:
            try:
                verify_jwt_in_request(optional=True)
                caller_id = get_jwt_identity()
                if caller_id is None or int(caller_id) != job.user_id:
                    return jsonify({"error": "Job not found"}), 404
            except Exception:
                return jsonify({"error": "Job not found"}), 404
    except Exception:
        return jsonify({"error": "Internal server error"}), 500

    def generate():
        # If already terminal, emit immediately and close
        current_job = db.session.get(AsyncJob, job_id)
        if current_job and current_job.status in ("completed", "failed"):
            evt = {"job_id": job_id, "status": current_job.status}
            if current_job.status == "completed" and current_job.result:
                evt["result"] = current_job.result
            if current_job.status == "failed" and current_job.error_message:
                evt["error_message"] = current_job.error_message
            yield f"data: {json.dumps(evt)}\n\n"
            return

        client = get_metrics_redis()
        stream_key = f"job:events:{job_id}"
        last_id = "0"
        max_wait = 300  # 5 minute ceiling (Ollama local fallback can take ~100s)
        start = time.monotonic()

        if client:
            # Redis path: subscribe to the job event stream
            while time.monotonic() - start < max_wait:
                try:
                    events = client.xread({stream_key: last_id}, count=10, block=3000)
                except Exception:
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                    continue

                if not events:
                    yield f"data: {json.dumps({'job_id': job_id, 'status': 'processing', 'heartbeat': True})}\n\n"
                    continue

                for _stream, messages in events:
                    for msg_id, payload in messages:
                        last_id = msg_id
                        data = dict(payload)
                        # Enrich terminal events with result/error from DB
                        if data.get("status") == "completed":
                            terminal_job = db.session.get(AsyncJob, job_id)
                            if terminal_job and terminal_job.result:
                                data["result"] = terminal_job.result
                        elif data.get("status") == "failed":
                            terminal_job = db.session.get(AsyncJob, job_id)
                            if terminal_job and terminal_job.error_message:
                                data["error_message"] = terminal_job.error_message
                        yield f"data: {json.dumps(data)}\n\n"
                        if data.get("status") in ("completed", "failed"):
                            return
        else:
            # Fallback: poll DB every second
            for _ in range(max_wait):
                time.sleep(1)
                polled = db.session.get(AsyncJob, job_id)
                if polled and polled.status in ("completed", "failed"):
                    evt = {"job_id": job_id, "status": polled.status}
                    if polled.status == "completed" and polled.result:
                        evt["result"] = polled.result
                    if polled.status == "failed" and polled.error_message:
                        evt["error_message"] = polled.error_message
                    yield f"data: {json.dumps(evt)}\n\n"
                    return
                yield f"data: {json.dumps({'job_id': job_id, 'status': 'processing', 'heartbeat': True})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@trips_bp.route("/api/save-trip", methods=["POST"])
@jwt_required()
def save_trip():
    # Validate saved-trip payloads so malformed itinerary submissions fail with field-level errors.
    data, error = load_request_json(SaveTripSchema())
    if error:
        return error
    user_id = get_jwt_identity()

    try:
        new_trip = Trip(
            user_id=user_id,
            trip_title=data.get("trip_title"),
            destination_country=data.get("destination_country"),
            budget=data.get("budget"),
            duration=data.get("duration"),
            travelers=data.get("travelers", 1),
            style=data.get("style"),
            date_type=data.get("date_type"),
            start_date=data.get("start_date"),
            traveler_type=data.get("traveler_type"),
            total_cost=data.get("total_cost"),
            itinerary_json=data.get("itinerary_json"),
        )
        db.session.add(new_trip)
        db.session.commit()
        return jsonify({"trip_id": new_trip.id, "message": "Trip saved successfully"}), 201
    except Exception:
        db.session.rollback()
        log.exception("trip.save_failed")
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None)
        }), 500


@trips_bp.route("/get-trip/<int:trip_id>", methods=["GET"])
@jwt_required()
def get_trip(trip_id):
    try:
        user_id = int(get_jwt_identity())
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"error": "Trip not found"}), 404

        return jsonify({
            "id": trip.id,
            "trip_title": trip.trip_title,
            "destination_country": trip.destination_country,
            "budget": trip.budget,
            "duration": trip.duration,
            "travelers": trip.travelers,
            "style": trip.style,
            "date_type": trip.date_type,
            "start_date": trip.start_date,
            "traveler_type": trip.traveler_type,
            "total_cost": trip.total_cost,
            "itinerary_json": trip.itinerary_json,
            "is_customized": bool(trip.is_customized),
            "user_notes": trip.user_notes,
            "quality_score": getattr(trip, 'quality_score', None),
            "created_at": trip.created_at.isoformat() if trip.created_at else None,
        }), 200
    except Exception:
        log.exception("trip.fetch_failed")
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None)
        }), 500


@trips_bp.route("/api/user/trips", methods=["GET"])
@jwt_required()
def get_user_trips():
    try:
        user_id = get_jwt_identity()
        page = max(request.args.get("page", type=int, default=1), 1)
        page_size = min(request.args.get("page_size", type=int, default=50), 200)

        query = db.session.query(Trip).filter_by(user_id=user_id).order_by(Trip.created_at.desc())
        total = query.count()
        items = query.limit(page_size).offset((page - 1) * page_size).all()

        return jsonify({
            "items": [{
                "id": t.id,
                "trip_title": t.trip_title,
                "destination_country": t.destination_country,
                "budget": t.budget,
                "duration": t.duration,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            } for t in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": -(-total // page_size),
        }), 200
    except Exception:
        log.exception("user_trips.fetch_failed")
        return jsonify({
            "error": "Internal server error",
            "request_id": getattr(g, "request_id", None)
        }), 500
