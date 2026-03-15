"""
test_signals.py - Tests for attraction signal collection.
"""


class TestAttractionSignals:
    def test_records_signal(self, client, db, seed_destination, seed_attractions):
        from backend.models import AttractionSignal

        before = db.session.query(AttractionSignal).count()
        response = client.post("/api/attraction-signal", json={
            "attraction_id": seed_attractions[0].id,
            "event_type": "view",
            "traveler_type": "solo_male",
            "trip_style": "standard",
            "budget_tier": "budget",
            "day_position": 1,
            "trip_duration": 3,
            "session_id": "guest-session-1",
        })

        assert response.status_code == 201
        after = db.session.query(AttractionSignal).count()
        assert after == before + 1

    def test_rejects_invalid_event_type(self, client, seed_destination, seed_attractions):
        response = client.post("/api/attraction-signal", json={
            "attraction_id": seed_attractions[0].id,
            "event_type": "invalid-event",
        })

        assert response.status_code == 400
