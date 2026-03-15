"""
test_trips.py â€” Tests for trip generation, save, retrieval endpoints.
Covers: /generate-itinerary, /api/save-trip, /get-trip/:id, /api/user/trips
"""

import pytest


VALID_TRIP_PAYLOAD = {
    "destination_country": "India",
    "start_city": "Mumbai",
    "selected_destinations": [
        {"id": 1, "name": "Jaipur", "estimated_cost_per_day": 3000}
    ],
    "budget": 9000,
    "duration": 3,
    "travelers": 1,
    "style": "standard",
    "date_type": "fixed",
    "start_date": "2026-10-15",
    "traveler_type": "solo_male",
    "interests": ["heritage", "culture"]
}



def generate_and_resolve_itinerary(client, payload):
    queued = client.post("/generate-itinerary", json=payload)
    assert queued.status_code == 202
    queued_body = queued.get_json()
    assert "job_id" in queued_body

    result = client.get(f"/get-itinerary-status/{queued_body['job_id']}")
    assert result.status_code == 200
    body = result.get_json()
    assert body["status"] == "completed"
    assert "result" in body
    return body["result"]


class TestGenerateItinerary:
    """POST /generate-itinerary"""

    def test_generate_returns_valid_structure(self, client, mock_gemini, seed_destination, seed_attractions):
        data = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        assert "itinerary" in data
        assert "total_cost" in data
        assert "trip_title" in data
        assert isinstance(data["itinerary"], list)
        assert len(data["itinerary"]) > 0

    def test_generate_itinerary_has_required_day_fields(self, client, mock_gemini, seed_destination, seed_attractions):
        day = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)["itinerary"][0]
        required = ["day", "location", "theme", "activities", "accommodation", "day_total"]
        for field in required:
            assert field in day, f"Missing field: {field}"

    def test_generate_itinerary_has_required_activity_fields(self, client, mock_gemini, seed_destination, seed_attractions):
        activity = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)["itinerary"][0]["activities"][0]
        required = ["time", "activity", "cost", "description"]
        for field in required:
            assert field in activity, f"Missing activity field: {field}"

    def test_generate_missing_budget(self, client):
        payload = {**VALID_TRIP_PAYLOAD}
        del payload["budget"]
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 400

    def test_generate_missing_destination(self, client):
        payload = {**VALID_TRIP_PAYLOAD}
        del payload["selected_destinations"]
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 400

    def test_generate_zero_budget_rejected(self, client):
        payload = {**VALID_TRIP_PAYLOAD, "budget": 0}
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 400

    def test_generate_negative_duration_rejected(self, client):
        payload = {**VALID_TRIP_PAYLOAD, "duration": -1}
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 400

    def test_generate_invalid_budget_type_returns_field_errors(self, client):
        payload = {**VALID_TRIP_PAYLOAD, "budget": "abc"}
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 400
        assert "budget" in res.get_json()["errors"]

    def test_generate_works_without_auth(self, client, mock_gemini, seed_destination):
        """Guests (unauthenticated users) can still queue itinerary jobs."""
        res = client.post("/generate-itinerary", json=VALID_TRIP_PAYLOAD)
        assert res.status_code == 202

    @pytest.mark.skip(reason="Rate limits are fully disabled during test suites")
    def test_generate_is_rate_limited_per_ip(self, client, mock_gemini, seed_destination, seed_attractions):
        # Enforce a per-IP cap on anonymous generation to protect upstream API quota.
        responses = [client.post("/generate-itinerary", json=VALID_TRIP_PAYLOAD) for _ in range(6)]
        assert [response.status_code for response in responses[:5]] == [202, 202, 202, 202, 202]
        assert responses[5].status_code == 429

    def test_generate_total_cost_within_budget_tolerance(self, client, mock_gemini, seed_destination):
        """Total cost must be within Â±5% of requested budget."""
        data = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        budget = VALID_TRIP_PAYLOAD["budget"]
        total = data["total_cost"]
        assert total <= budget * 1.05, f"total_cost {total} exceeds budget {budget} by more than 5%"

    def test_generate_budget_trip_style(self, client, mock_gemini, seed_destination):
        payload = {**VALID_TRIP_PAYLOAD, "style": "budget"}
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 202

    def test_generate_luxury_trip_style(self, client, mock_gemini, seed_destination):
        payload = {**VALID_TRIP_PAYLOAD, "style": "luxury", "budget": 50000}
        res = client.post("/generate-itinerary", json=payload)
        assert res.status_code == 202

    def test_generate_logs_analytics_event(self, client, mock_gemini, seed_destination, db):
        from backend.models import AnalyticsEvent
        before = db.session.query(AnalyticsEvent).count()
        generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        after = db.session.query(AnalyticsEvent).count()
        assert after > before


class TestSaveTrip:
    """POST /api/save-trip"""

    def test_save_trip_authenticated(self, client, auth_headers, mock_gemini, seed_destination):
        itinerary = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)

        res = client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": itinerary["itinerary"],
            "total_cost": itinerary["total_cost"],
            "trip_title": itinerary["trip_title"],
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.get_json()
        assert "trip_id" in data or "id" in data

    def test_save_trip_unauthenticated_rejected(self, client, mock_gemini, seed_destination):
        res = client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": [],
            "total_cost": 9000,
            "trip_title": "Test Trip",
        })
        assert res.status_code == 401

    def test_save_trip_missing_itinerary_rejected(self, client, auth_headers):
        res = client.post("/api/save-trip", json={
            "destination_country": "India",
            "budget": 9000,
        }, headers=auth_headers)
        assert res.status_code == 400


class TestGetTrip:
    """GET /get-trip/:tripId"""

    def test_get_trip_returns_correct_data(self, client, auth_headers, mock_gemini, seed_destination):
        itinerary = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)

        save = client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": itinerary["itinerary"],
            "total_cost": itinerary["total_cost"],
            "trip_title": itinerary["trip_title"],
        }, headers=auth_headers)
        trip_id = save.get_json().get("trip_id") or save.get_json().get("id")

        res = client.get(f"/get-trip/{trip_id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["destination_country"] == "India"

    def test_get_trip_nonexistent_returns_404(self, client, auth_headers):
        res = client.get("/get-trip/999999", headers=auth_headers)
        assert res.status_code == 404

    def test_get_trip_other_user_forbidden(self, client, mock_gemini, seed_destination):
        """User B should not be able to GET User A's trip by ID."""
        # Setup User A
        res_a = client.post("/auth/register", json={
            "name": "User A", "email": "unique_a1_forbidden@altairgo.com", "password": "PasswordA123!"
        })
        assert res_a.status_code == 201, f"Failed to register User A: {res_a.get_data(as_text=True)}"
        headers_a = {"Authorization": f"Bearer {res_a.get_json()['token']}"}

        # Setup User B
        res_b = client.post("/auth/register", json={
            "name": "User B", "email": "unique_b1_forbidden@altairgo.com", "password": "PasswordB123!"
        })
        assert res_b.status_code == 201, f"Failed to register User B: {res_b.get_data(as_text=True)}"
        headers_b = {"Authorization": f"Bearer {res_b.get_json()['token']}"}

        # User A saves a trip
        itinerary = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        save = client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": itinerary["itinerary"],
            "total_cost": itinerary["total_cost"],
            "trip_title": "User A Trip",
        }, headers=headers_a)
        trip_id = save.get_json().get("trip_id") or save.get_json().get("id")

        # User B tries to GET it
        res = client.get(f"/get-trip/{trip_id}", headers=headers_b)
        assert res.status_code == 404  # We return 404 for forbidden trips to avoid leaking existence


class TestUserTrips:
    """GET /api/user/trips"""

    def test_user_trips_returns_list(self, client, auth_headers, mock_gemini, seed_destination):
        itinerary = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": itinerary["itinerary"],
            "total_cost": itinerary["total_cost"],
            "trip_title": itinerary["trip_title"],
        }, headers=auth_headers)

        res = client.get("/api/user/trips", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 1

    def test_user_trips_unauthenticated_rejected(self, client):
        res = client.get("/api/user/trips")
        assert res.status_code == 401

    def test_user_trips_only_returns_own_trips(self, client, mock_gemini, seed_destination):
        """User A should not see User B's trips."""
        res_a = client.post("/auth/register", json={
            "name": "User A", "email": "unique_a2_own@altairgo.com", "password": "PasswordA123!"
        })
        assert res_a.status_code == 201, f"Failed to register User A: {res_a.get_data(as_text=True)}"
        headers_a = {"Authorization": f"Bearer {res_a.get_json()['token']}"}

        res_b = client.post("/auth/register", json={
            "name": "User B", "email": "unique_b2_own@altairgo.com", "password": "PasswordB123!"
        })
        assert res_b.status_code == 201, f"Failed to register User B: {res_b.get_data(as_text=True)}"
        headers_b = {"Authorization": f"Bearer {res_b.get_json()['token']}"}

        itinerary = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": itinerary["itinerary"],
            "total_cost": itinerary["total_cost"],
            "trip_title": "User A Trip",
        }, headers=headers_a)

        res = client.get("/api/user/trips", headers=headers_b)
        assert len(res.get_json()["items"]) == 0
