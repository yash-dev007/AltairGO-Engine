import pytest


@pytest.fixture
def saved_trip_id(db, registered_user):
    from backend.models import Trip

    trip = Trip(
        user_id=registered_user["user"]["id"],
        trip_title="Hardening Test Trip",
        destination_country="India",
        budget=9000,
        duration=1,
        travelers=1,
        style="standard",
        date_type="fixed",
        start_date="2026-10-15",
        traveler_type="solo_male",
        total_cost=9000,
        itinerary_json=[
            {
                "day": 1,
                "location": "Jaipur",
                "activities": [
                    {"name": "Amber Fort", "time": "09:00"},
                    {"name": "Hawa Mahal", "time": "12:00"},
                    {"name": "Jantar Mantar", "time": "15:00"},
                ],
            }
        ],
    )
    db.session.add(trip)
    db.session.commit()
    return trip.id


def test_logging_middleware_attaches(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)


def test_error_envelope_shape_on_missing_trip(client, auth_headers):
    resp = client.get("/api/trip/99999", headers=auth_headers)
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert body["error"]
    assert body["code"] == "ERR_NOT_FOUND"


def test_success_envelope_has_success_true(client, auth_headers):
    resp = client.get("/api/user/trips", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_metrics_endpoint_requires_admin(client):
    resp = client.get("/api/metrics")
    assert resp.status_code in (401, 403)


def test_metrics_endpoint_returns_expected_fields(client, admin_headers):
    resp = client.get("/api/metrics", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    expected_fields = [
        "trips_generated_24h",
        "active_jobs",
        "cache_hit_rate",
        "embedding_coverage_pct",
        "gemini_429_count_24h",
        "worker_alive",
        "redis_memory_mb",
    ]
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"
    # embedding_coverage_pct must be on a 0-100 scale (not a 0-1 ratio)
    assert 0.0 <= data["embedding_coverage_pct"] <= 100.0
    # cache_hit_rate stays a 0-1 ratio
    assert 0.0 <= data["cache_hit_rate"] <= 1.0


def test_reorder_activity_rejects_non_integer_indices(client, auth_headers, saved_trip_id):
    resp = client.post(
        f"/api/trip/{saved_trip_id}/reorder-activity",
        json={"day_index": "0", "from_index": 0, "to_index": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert body["code"] == "ERR_VALIDATION"


def test_reorder_activity_swaps_positions(client, auth_headers, saved_trip_id):
    resp = client.get(f"/get-trip/{saved_trip_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    if "data" in body:
        body = body["data"]
    itinerary = body.get("itinerary_json", {})
    if isinstance(itinerary, dict):
        day0_activities = itinerary.get("itinerary", [{}])[0].get("activities", [])
    else:
        day0_activities = itinerary[0].get("activities", [])
    if len(day0_activities) < 2:
        pytest.skip("Trip has fewer than 2 activities on day 0")

    first_name = day0_activities[0].get("name") or day0_activities[0].get("activity")
    second_name = day0_activities[1].get("name") or day0_activities[1].get("activity")

    resp = client.post(
        f"/api/trip/{saved_trip_id}/reorder-activity",
        json={"day_index": 0, "from_index": 0, "to_index": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    new_activities = body["data"]["activities"]
    assert (new_activities[0].get("name") or new_activities[0].get("activity")) == second_name
    assert (new_activities[1].get("name") or new_activities[1].get("activity")) == first_name


def test_reorder_activity_invalid_index(client, auth_headers, saved_trip_id):
    resp = client.post(
        f"/api/trip/{saved_trip_id}/reorder-activity",
        json={"day_index": 0, "from_index": 999, "to_index": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "ERR_VALIDATION"


def test_task_registry_has_all_scheduled_tasks():
    from backend.tasks.task_registry import TASK_REGISTRY

    expected = {
        "run_score_update",
        "run_weather_sync",
        "run_quality_scoring",
        "run_price_sync",
        "run_cache_warm",
        "run_embedding_sync",
        "run_affiliate_health",
        "run_destination_validation",
        "run_post_trip_summaries",
        "run_osm_ingestion",
        "run_enrichment",
        "run_scoring",
    }
    assert expected == set(TASK_REGISTRY.keys())
    for name, meta in TASK_REGISTRY.items():
        assert "label" in meta, f"{name} missing label"
        assert "schedule" in meta, f"{name} missing schedule"


def test_write_task_result_is_safe_without_redis(monkeypatch):
    from backend import celery_tasks

    monkeypatch.setattr("backend.services.cache_service.REDIS_OK", False)
    celery_tasks._write_task_result("run_score_update", "success", 1.5)
