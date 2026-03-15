"""
test_destinations.py — Tests for destination, country, and region endpoints.
Covers: /countries, /regions, /destinations, /destinations/:id, destination requests.
"""

import pytest


class TestCountries:
    """GET /countries"""

    def test_returns_list(self, client, seed_country):
        res = client.get("/countries")
        assert res.status_code == 200
        data = res.get_json()
        # /countries is NOT paginated yet, still returns plain list
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_country_has_required_fields(self, client, seed_country):
        res = client.get("/countries")
        country = res.get_json()[0]
        for field in ["id", "name", "code"]:
            assert field in country, f"Missing field: {field}"

    def test_india_present_after_seed(self, client, seed_country):
        res = client.get("/countries")
        names = [c["name"] for c in res.get_json()]
        assert "India" in names


class TestDestinations:
    """GET /destinations and GET /destinations/:id"""

    def test_list_all_destinations(self, client, seed_destination):
        res = client.get("/destinations")
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_destination_has_required_fields(self, client, seed_destination):
        res = client.get("/destinations")
        dest = res.get_json()["items"][0]
        required = ["id", "name", "slug", "image", "rating", "estimated_cost_per_day"]
        for field in required:
            assert field in dest, f"Missing field: {field}"

    def test_destination_detail_by_id(self, client, seed_destination):
        res = client.get(f"/destinations/{seed_destination.id}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["name"] == "Jaipur"
        assert data["slug"] == "jaipur"

    def test_destination_detail_includes_attractions(self, client, seed_destination, seed_attractions):
        res = client.get(f"/destinations/{seed_destination.id}")
        data = res.get_json()
        assert "attractions" in data
        assert len(data["attractions"]) >= 1

    def test_destination_not_found_returns_404(self, client):
        res = client.get("/destinations/999999")
        assert res.status_code == 404

    def test_filter_destinations_by_tag(self, client, seed_destination):
        res = client.get("/destinations?tag=Heritage")
        assert res.status_code == 200
        data = res.get_json()["items"]
        for d in data:
            assert d.get("tag") == "Heritage"

    def test_filter_destinations_by_max_cost(self, client, seed_destination):
        res = client.get("/destinations?max_cost=5000")
        assert res.status_code == 200
        for d in res.get_json()["items"]:
            assert d["estimated_cost_per_day"] <= 5000


class TestDestinationRequest:
    """POST /api/destination-request"""

    def test_submit_destination_request(self, client):
        res = client.post("/api/destination-request", json={
            "name": "Hampi",
            "description": "Ancient ruins in Karnataka",
            "cost": 2500,
            "tag": "Heritage"
        })
        assert res.status_code in [200, 201]

    def test_destination_request_missing_name_rejected(self, client):
        res = client.post("/api/destination-request", json={
            "description": "Some description",
            "cost": 2000
        })
        assert res.status_code == 400

    def test_destination_request_creates_pending_record(self, client, db):
        from backend.models import DestinationRequest
        before = db.session.query(DestinationRequest).count()
        client.post("/api/destination-request", json={
            "name": "Munnar",
            "description": "Hill station in Kerala",
            "cost": 2000,
            "tag": "Nature"
        })
        after = db.session.query(DestinationRequest).count()
        assert after == before + 1

    def test_destination_request_default_status_pending(self, client, db):
        from backend.models import DestinationRequest
        client.post("/api/destination-request", json={
            "name": "Coorg",
            "description": "Scotland of India",
            "cost": 3000,
            "tag": "Nature"
        })
        req = db.session.query(DestinationRequest).filter_by(name="Coorg").first()
        assert req is not None
        assert req.status == "pending"


class TestBudgetCalculation:
    """POST /calculate-budget"""

    def test_budget_calculation_returns_estimate(self, client, seed_destination):
        res = client.post("/calculate-budget", json={
            "selected_destinations": [{"id": seed_destination.id, "name": "Jaipur"}],
            "duration": 3,
            "travelers": 2,
            "style": "standard"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "estimated_budget" in data or "budget" in data

    def test_budget_luxury_higher_than_budget_tier(self, client, seed_destination):
        dest = [{"id": seed_destination.id, "name": "Jaipur"}]
        base = {"selected_destinations": dest, "duration": 3, "travelers": 1}

        res_budget = client.post("/calculate-budget", json={**base, "style": "budget"})
        res_luxury = client.post("/calculate-budget", json={**base, "style": "luxury"})

        budget_est = res_budget.get_json().get("estimated_budget") or res_budget.get_json().get("budget")
        luxury_est = res_luxury.get_json().get("estimated_budget") or res_luxury.get_json().get("budget")

        assert luxury_est > budget_est, "Luxury should always cost more than budget tier"
