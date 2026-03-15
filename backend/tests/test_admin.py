"""
test_admin.py — Tests for /api/admin/* endpoints.
Covers: auth, stats, destination CRUD, user list, request approval/rejection.
"""

import pytest



class TestAdminAuth:
    """POST /api/admin/verify-key"""

    def test_valid_key_accepted(self, client, admin_headers):
        res = client.post("/api/admin/verify-key",
                          json={"key": "test-admin-key-2026"})
        assert res.status_code == 200

    def test_wrong_key_rejected(self, client):
        res = client.post("/api/admin/verify-key",
                          json={"key": "wrong-key"})
        assert res.status_code == 401

    def test_missing_key_rejected(self, client):
        res = client.post("/api/admin/verify-key", json={})
        assert res.status_code == 400


class TestAdminStats:
    """GET /api/admin/stats"""

    def test_stats_require_admin_key(self, client):
        res = client.get("/api/admin/stats")
        assert res.status_code == 401

    def test_stats_reject_admin_key_in_query_string(self, client):
        # Reject query-string admin keys so secrets do not leak into access logs.
        res = client.get("/api/admin/stats?admin_key=test-admin-key-2026")
        assert res.status_code == 401

    def test_stats_returns_expected_fields(self, client, admin_headers):
        res = client.get("/api/admin/stats", headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        for field in ["total_users", "total_trips", "total_destinations"]:
            assert field in data, f"Missing stats field: {field}"

    def test_stats_counts_are_non_negative(self, client, admin_headers):
        res = client.get("/api/admin/stats", headers=admin_headers)
        data = res.get_json()
        for key, val in data.items():
            if isinstance(val, (int, float)):
                assert val >= 0, f"Stat {key} is negative: {val}"


class TestAdminDestinations:
    """GET/PUT/DELETE /api/admin/destinations"""

    def test_list_destinations_as_admin(self, client, admin_headers, seed_destination):
        res = client.get("/api/admin/destinations", headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_destinations_blocked_without_key(self, client, seed_destination):
        res = client.get("/api/admin/destinations")
        assert res.status_code == 401

    def test_update_destination(self, client, admin_headers, seed_destination):
        res = client.put(
            f"/api/admin/destinations/{seed_destination.id}",
            json={"rating": 4.9, "desc": "Updated desc"},
            headers=admin_headers
        )
        assert res.status_code == 200

    def test_update_nonexistent_destination(self, client, admin_headers):
        res = client.put(
            "/api/admin/destinations/999999",
            json={"rating": 4.9},
            headers=admin_headers
        )
        assert res.status_code == 404

    def test_delete_destination(self, client, admin_headers, seed_destination, db):
        from backend.models import Destination
        dest_id = seed_destination.id
        res = client.delete(
            f"/api/admin/destinations/{dest_id}",
            headers=admin_headers
        )
        assert res.status_code == 200
        assert db.session.get(Destination, dest_id) is None


class TestAdminUsers:
    """GET /api/admin/users"""

    def test_returns_user_list(self, client, admin_headers, registered_user):
        res = client.get("/api/admin/users", headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_user_list_no_passwords_exposed(self, client, admin_headers, registered_user):
        res = client.get("/api/admin/users", headers=admin_headers)
        body = res.get_data(as_text=True)
        assert "password_hash" not in body
        assert registered_user["payload"]["password"] not in body


class TestAdminRequests:
    """GET/POST /api/admin/requests and approve/reject"""

    def _submit_request(self, client):
        client.post("/api/destination-request", json={
            "name": "Spiti Valley",
            "description": "High-altitude cold desert",
            "cost": 4000,
            "tag": "Adventure"
        })

    def test_list_requests_as_admin(self, client, admin_headers):
        self._submit_request(client)
        res = client.get("/api/admin/requests", headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_approve_request_creates_destination(self, client, admin_headers, db):
        from backend.models import DestinationRequest, Destination
        self._submit_request(client)
        req = db.session.query(DestinationRequest).filter_by(name="Spiti Valley").first()
        assert req is not None

        before = db.session.query(Destination).count()
        res = client.post(
            f"/api/admin/requests/{req.id}/approve",
            headers=admin_headers
        )
        assert res.status_code == 200
        after = db.session.query(Destination).count()
        assert after == before + 1

    def test_approve_request_updates_status(self, client, admin_headers, db):
        from backend.models import DestinationRequest
        self._submit_request(client)
        req = db.session.query(DestinationRequest).filter_by(name="Spiti Valley").first()
        client.post(f"/api/admin/requests/{req.id}/approve", headers=admin_headers)
        db.session.refresh(req)
        assert req.status == "approved"

    def test_reject_request_updates_status(self, client, admin_headers, db):
        from backend.models import DestinationRequest
        client.post("/api/destination-request", json={
            "name": "Fake Place XYZ",
            "description": "Not a real place",
            "cost": 1000,
            "tag": "Other"
        })
        req = db.session.query(DestinationRequest).filter_by(name="Fake Place XYZ").first()
        res = client.post(
            f"/api/admin/requests/{req.id}/reject",
            headers=admin_headers
        )
        assert res.status_code == 200
        db.session.refresh(req)
        assert req.status == "rejected"

    def test_approve_nonexistent_request_404(self, client, admin_headers):
        res = client.post("/api/admin/requests/999999/approve", headers=admin_headers)
        assert res.status_code == 404


class TestAdminTrips:
    """GET /api/admin/trips"""

    def test_admin_can_view_all_trips(self, client, admin_headers, mock_gemini,
                                       seed_destination, registered_user, auth_headers):
        from backend.tests.test_trips import VALID_TRIP_PAYLOAD, generate_and_resolve_itinerary
        itinerary = generate_and_resolve_itinerary(client, VALID_TRIP_PAYLOAD)
        client.post("/api/save-trip", json={
            **VALID_TRIP_PAYLOAD,
            "itinerary_json": itinerary["itinerary"],
            "total_cost": itinerary["total_cost"],
            "trip_title": itinerary["trip_title"],
        }, headers=auth_headers)

        res = client.get("/api/admin/trips", headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 1
