"""
conftest.py — Shared fixtures for AltairGO Intelligence test suite.
All tests import from here. Never duplicate fixture logic.
"""

# ── CRITICAL: Set TESTING env var BEFORE any project imports so
#    database.py picks up SQLite instead of PostgreSQL. ──────────
import os
from pathlib import Path

TEST_DB_PATH = Path(f"backend_test_{os.getpid()}.db").absolute()
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("REDIS_URL", "memory://")
# ─────────────────────────────────────────────────────────────────

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime


def _reset_test_db():
    from backend.database import init_db
    init_db()


# ─────────────────────────────────────────────────────────────────
# Flask app fixture — uses SQLite in-memory DB
# ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def app():
    """Create application for testing with an isolated in-memory SQLite DB."""
    from backend.app import create_app
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": TEST_DATABASE_URL,
        "REDIS_URL": os.environ.get("REDIS_URL", "memory://"),
        "JWT_SECRET_KEY": "test-secret-key-at-least-32-chars-long",
        "ADMIN_ACCESS_KEY": "test-admin-key-2026",
        "WTF_CSRF_ENABLED": False,
        "GEMINI_API_KEY": "fake-gemini-key",
        "PEXELS_API_KEY": "fake-pexels-key",
        "VALIDATION_STRICT": "true",
        "RATELIMIT_ENABLED": False,
    }
    app = create_app(test_config)
    with app.app_context():
        _reset_test_db()
        yield app
        
    # Cleanup DB file after tests if it exists
    if TEST_DB_PATH.exists():
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture(scope="function")
def client(app, db):
    """Flask test client — fresh per test function."""
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """
    Database session — drops and recreates schema before each test for
    full isolation. Yields a wrapper with .engine and .session attrs.
    """
    from backend.database import db as _db

    with app.app_context():
        _reset_test_db()
        yield _db
        _db.session.remove()


# ─────────────────────────────────────────────────────────────────
# Auth fixtures
# ─────────────────────────────────────────────────────────────────
@pytest.fixture
def registered_user(client):
    """Register + return a user dict with JWT token. Falls back to login if exists."""
    payload = {
        "name": "Test User",
        "email": "testuser@altairgo.com",
        "password": "SecurePass123!"
    }
    res = client.post("/auth/register", json=payload)

    if res.status_code == 409:
        res = client.post("/auth/login", json=payload)

    assert res.status_code in [200, 201], f"Auth failed: {res.get_json()}"
    data = res.get_json()
    return {"token": data["token"], "user": data["user"], "payload": payload}


@pytest.fixture
def auth_headers(registered_user):
    """Authorization headers with valid JWT."""
    return {"Authorization": f"Bearer {registered_user['token']}"}


@pytest.fixture
def admin_headers(app):
    """Admin authorization headers using JWT with admin role."""
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity="admin_test", additional_claims={"role": "admin"})
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────
# Seed data fixtures
# ─────────────────────────────────────────────────────────────────
@pytest.fixture
def seed_country(db):
    """Insert a test Country record."""
    from backend.models import Country
    country = Country(name="India", code="IN", currency="INR", image="india.jpg")
    db.session.add(country)
    db.session.commit()
    return country


@pytest.fixture
def seed_destination(db, seed_country):
    """Insert a test Destination record."""
    from backend.models import State, Destination
    state = State(name="Rajasthan", image="raj.jpg", country_id=seed_country.id)
    db.session.add(state)
    db.session.commit()

    destination = Destination(
        name="Jaipur",
        slug="jaipur",
        desc="Pink City of India",
        description="Jaipur is the capital of Rajasthan...",
        image="jaipur.jpg",
        location="Rajasthan, India",
        price_str="₹3,000/day",
        estimated_cost_per_day=3000,
        rating=4.5,
        tag="Heritage",
        highlights=["Amber Fort", "Hawa Mahal"],
        best_time_months=["oct", "nov", "dec", "jan", "feb"],
        vibe_tags=["heritage", "culture"],
        state_id=state.id,
    )
    db.session.add(destination)
    db.session.commit()
    return destination


@pytest.fixture
def seed_attractions(db, seed_destination):
    """Insert test Attraction records with intelligence fields."""
    from backend.models import Attraction
    attractions = [
        Attraction(
            name="Amber Fort",
            description="Magnificent hilltop fort overlooking Maota Lake.",
            entry_cost=550,
            duration="2-3 hours",
            rating=4.7,
            type="fort",
            destination_id=seed_destination.id,
            latitude=26.9855,
            longitude=75.8513,
            popularity_score=95,
            avg_visit_duration_hours=2.0,
            best_visit_time_hour=9,
            budget_category="mid-range",
            compatible_traveler_types=["solo_male", "solo_female", "couple", "family"],
            seasonal_score={"oct": 95, "nov": 95, "dec": 90, "jun": 40, "jul": 30},
        ),
        Attraction(
            name="Hawa Mahal",
            description="Palace of winds with 953 small windows.",
            entry_cost=200,
            duration="1 hour",
            rating=4.5,
            type="palace",
            destination_id=seed_destination.id,
            latitude=26.9239,
            longitude=75.8267,
            popularity_score=88,
            avg_visit_duration_hours=1.0,
            best_visit_time_hour=10,
            budget_category="budget",
            compatible_traveler_types=["solo_male", "solo_female", "couple", "family"],
            seasonal_score={"oct": 90, "nov": 90, "dec": 85, "jun": 50},
        ),
        Attraction(
            name="Jantar Mantar",
            description="UNESCO World Heritage astronomical observatory.",
            entry_cost=200,
            duration="1-1.5 hours",
            rating=4.3,
            type="heritage",
            destination_id=seed_destination.id,
            latitude=26.9249,
            longitude=75.8237,
            popularity_score=75,
            avg_visit_duration_hours=1.5,
            best_visit_time_hour=10,
            budget_category="budget",
            compatible_traveler_types=["solo_male", "solo_female", "couple", "family"],
            seasonal_score={"oct": 90, "nov": 90, "dec": 85, "jun": 50},
        ),
    ]
    for a in attractions:
        db.session.add(a)
    db.session.commit()
    return attractions


# ─────────────────────────────────────────────────────────────────
# Mock Gemini response
# ─────────────────────────────────────────────────────────────────
MOCK_ITINERARY_RESPONSE = {
    "trip_title": "Jaipur Heritage Explorer — 3 Days",
    "total_cost": 9000,
    "cost_breakdown": {
        "accommodation": 3150,
        "food": 2250,
        "transport": 1800,
        "activities": 1350,
        "misc": 450
    },
    "itinerary": [
        {
            "day": 1,
            "date": "2026-10-15",
            "location": "Jaipur",
            "theme": "Heritage & Forts",
            "pacing_level": "moderate",
            "day_total": 3200,
            "travel_hours": 0,
            "intensity_score": 6,
            "image_keyword": "Amber Fort Jaipur",
            "accommodation": {
                "name": "Hotel Pink City",
                "type": "mid-range",
                "cost_per_night": 1800,
                "location": "MI Road, Jaipur",
                "why_this": "Central location, great reviews",
                "booking_tip": "Book 2 weeks in advance"
            },
            "activities": [
                {
                    "time": "09:00",
                    "time_range": "09:00-11:30",
                    "activity": "Amber Fort",
                    "description": "Explore the magnificent hilltop fort.",
                    "why_this_fits": "Perfect for heritage lovers",
                    "local_secret": "Visit on weekdays to avoid crowds",
                    "cost": 550,
                    "how_to_reach": "Auto-rickshaw from city center",
                    "crowd_level": "moderate",
                    "meal_type": None,
                    "google_maps_search_query": "Amber Fort Jaipur"
                }
            ]
        }
    ],
    "travel_between_cities": [],
    "smart_insights": ["Best visited in winter months", "Carry cash for local markets"],
    "packing_tips": ["Light cotton clothes", "Comfortable walking shoes"]
}


@pytest.fixture
def mock_gemini(monkeypatch):
    """Patch Gemini API to return deterministic mock response."""
    mock = MagicMock(return_value=MOCK_ITINERARY_RESPONSE)
    return mock


@pytest.fixture
def mock_gemini_chat(monkeypatch):
    """Patch Gemini chat endpoint."""
    mock = MagicMock(return_value={"reply": "Jaipur is best visited in October."})
    monkeypatch.setattr(
        "backend.services.gemini_service.GeminiService.chat_with_data",
        mock
    )
    return mock
