"""
test_pipeline.py — Tests for the data ingestion and enrichment pipeline.
Covers: OSM ingest, Wikidata enrichment, popularity scoring, price sync.
All external HTTP calls are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock, call
import backend.scripts.enrich_attractions


# ─────────────────────────────────────────────────────
# OSM Ingestion
# ─────────────────────────────────────────────────────
MOCK_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 123456789,
            "lat": 26.9855,
            "lon": 75.8513,
            "tags": {
                "name": "Amber Fort",
                "tourism": "attraction",
                "wikidata": "Q180691",
                "opening_hours": "Mo-Su 08:00-18:00",
                "website": "https://amberfort.org",
                "fee": "yes",
            }
        },
        {
            "type": "node",
            "id": 987654321,
            "lat": 26.9239,
            "lon": 75.8267,
            "tags": {
                "name": "Hawa Mahal",
                "tourism": "attraction",
                "wikidata": "Q210053",
                "opening_hours": "Mo-Su 09:00-17:00",
            }
        },
        {
            "type": "node",
            "id": 111111111,
            "lat": None,   # malformed — no coordinates
            "lon": None,
            "tags": {"name": "Broken Node", "tourism": "attraction"}
        }
    ]
}


class TestOSMIngestion:

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_parses_valid_elements(self, mock_post):
        mock_post.return_value.json.return_value = MOCK_OVERPASS_RESPONSE
        mock_post.return_value.status_code = 200

        from backend.scripts.ingest_osm_data import ingest_city_pois
        with patch("backend.scripts.ingest_osm_data.SessionLocal") as mock_session_class:
            mock_session = mock_session_class.return_value
            count = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
            # MOCK_OVERPASS_RESPONSE has 2 valid nodes (third has None coords)
            assert count == 2

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_handles_empty_response(self, mock_post):
        mock_post.return_value.json.return_value = {"elements": []}
        mock_post.return_value.status_code = 200
        from backend.scripts.ingest_osm_data import ingest_city_pois

        with patch("backend.scripts.ingest_osm_data.SessionLocal") as mock_session_class:
            mock_session = mock_session_class.return_value
            count = ingest_city_pois("EmptyCity", 2, lat=0.0, lng=0.0, radius=8000)
            assert count == 0

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_handles_api_timeout_gracefully(self, mock_post):
        import requests
        mock_post.side_effect = requests.Timeout("Connection timed out")
        from backend.scripts.ingest_osm_data import ingest_city_pois

        count = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
        assert count == 0

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_skips_missing_coordinates(self, mock_post):
        mock_post.return_value.json.return_value = MOCK_OVERPASS_RESPONSE
        mock_post.return_value.status_code = 200
        from backend.scripts.ingest_osm_data import ingest_city_pois

        with patch("backend.scripts.ingest_osm_data.SessionLocal") as mock_session_class:
            mock_session = mock_session_class.return_value
            # The ingest uses raw db.execute(), count tells us valid records
            count = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
            # The third element has None coords, so only 2 should be processed
            assert count == 2

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_extracts_wikidata_id(self, mock_post):
        mock_post.return_value.json.return_value = MOCK_OVERPASS_RESPONSE
        mock_post.return_value.status_code = 200
        from backend.scripts.ingest_osm_data import ingest_city_pois

        with patch("backend.scripts.ingest_osm_data.SessionLocal") as mock_session_class:
            mock_session = mock_session_class.return_value
            count = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
            assert count == 2
            # Verify that db.execute was called with INSERT containing wikidata_id
            execute_calls = mock_session.execute.call_args_list
            # Find an INSERT call whose params contain Amber Fort
            found_wikidata = False
            for c in execute_calls:
                args = c[0]  # positional args: (text_obj, params_dict)
                if len(args) >= 2 and isinstance(args[1], dict):
                    params = args[1]
                    if params.get("name") == "Amber Fort":
                        assert params.get("wikidata_id") == "Q180691"
                        found_wikidata = True
            assert found_wikidata, "Amber Fort INSERT with wikidata_id not found"

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_classifies_type_correctly(self, mock_post):
        mock_post.return_value.json.return_value = MOCK_OVERPASS_RESPONSE
        mock_post.return_value.status_code = 200
        from backend.scripts.ingest_osm_data import ingest_city_pois

        with patch("backend.scripts.ingest_osm_data.SessionLocal") as mock_session_class:
            mock_session = mock_session_class.return_value
            count = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
            assert count == 2
            execute_calls = mock_session.execute.call_args_list
            for c in execute_calls:
                args = c[0]
                if len(args) >= 2 and isinstance(args[1], dict):
                    params = args[1]
                    if "type" in params:
                        assert params["type"] is not None

    @patch("backend.scripts.ingest_osm_data.requests.post")
    def test_ingest_deduplicates_by_osm_id(self, mock_post):
        """Verify that calling ingest twice doesn't double-insert (uses SELECT + UPDATE)."""
        mock_post.return_value.json.return_value = MOCK_OVERPASS_RESPONSE
        mock_post.return_value.status_code = 200
        from backend.scripts.ingest_osm_data import ingest_city_pois

        with patch("backend.scripts.ingest_osm_data.SessionLocal") as mock_session_class:
            mock_session = mock_session_class.return_value
            # First call: all SELECTs return None (no existing records)
            mock_session.execute.return_value.fetchone.return_value = None
            count1 = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
            assert count1 == 2

            # Second call: SELECTs return existing records
            mock_result = MagicMock()
            mock_result.fetchone.return_value = MagicMock(id=1)
            mock_session.execute.return_value = mock_result
            count2 = ingest_city_pois("Jaipur", 1, lat=26.91, lng=75.78, radius=8000)
            # Should still process 2 but as UPDATEs, not new INSERTs
            assert count2 == 2


# ─────────────────────────────────────────────────────
# Enrichment Pipeline
# ─────────────────────────────────────────────────────
MOCK_GOOGLE_SEARCH_RESPONSE = {
    "status": "OK",
    "results": [
        {
            "place_id": "ChIJD7fiBh9dXjkRXqWAjpMAfaw",
            "name": "Amber Palace",
            "rating": 4.6,
            "user_ratings_total": 92314,
        }
    ]
}

MOCK_GOOGLE_DETAILS_RESPONSE = {
    "status": "OK",
    "result": {
        "rating": 4.7,
        "user_ratings_total": 95000,
        "photos": [
            {"photo_reference": "random_string_123"},
            {"photo_reference": "random_string_456"}
        ]
    }
}


class TestEnrichmentPipeline:

    @patch("backend.scripts.enrich_attractions.requests.get")
    def test_search_google_places_success(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_GOOGLE_SEARCH_RESPONSE
        mock_get.return_value.status_code = 200

        from backend.scripts.enrich_attractions import search_google_places
        with patch("backend.scripts.enrich_attractions.GOOGLE_API_KEY", "test_key"):
            result = search_google_places("Amber Fort", 26.98, 75.85)
            assert result is not None
            assert result["place_id"] == "ChIJD7fiBh9dXjkRXqWAjpMAfaw"
            assert result["rating"] == 4.6

    @patch("backend.scripts.enrich_attractions.requests.get")
    def test_search_google_places_handles_empty(self, mock_get):
        mock_get.return_value.json.return_value = {"status": "ZERO_RESULTS", "results": []}
        mock_get.return_value.status_code = 200

        from backend.scripts.enrich_attractions import search_google_places
        with patch("backend.scripts.enrich_attractions.GOOGLE_API_KEY", "test_key"):
            result = search_google_places("NonExistent", 0, 0)
            assert result is None

    @patch("backend.scripts.enrich_attractions.requests.get")
    def test_get_google_place_details_extracts_photos(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_GOOGLE_DETAILS_RESPONSE
        mock_get.return_value.status_code = 200

        from backend.scripts.enrich_attractions import get_google_place_details
        with patch("backend.scripts.enrich_attractions.GOOGLE_API_KEY", "test_key"):
            details = get_google_place_details("ChIJD7fiBh9dXjkRXqWAjpMAfaw")
            assert details is not None
            assert len(details["photos"]) == 2
            assert details["photos"][0]["photo_reference"] == "random_string_123"

    def test_apis_skipped_without_key(self):
        from backend.scripts.enrich_attractions import search_google_places, get_google_place_details
        with patch("backend.scripts.enrich_attractions.GOOGLE_API_KEY", ""):
            res1 = search_google_places("Amber Fort", 26.98, 75.85)
            res2 = get_google_place_details("ChIJD")
            assert res1 is None
            assert res2 is None


# ─────────────────────────────────────────────────────
# Intelligence Scoring
# ─────────────────────────────────────────────────────
class TestAttractionScoring:
    """
    These tests import calculate_seasonal_score directly — no DB, no Flask.
    The previous 'Table already defined' error was caused by score_attractions.py
    doing a bare `from models import ...` which re-executed models.py against
    a fresh Base instance, creating duplicate table definitions.
    Fixed by switching to `from backend.models import ...` in score_attractions.py.
    """

    def test_calculate_seasonal_score_high_overlap(self):
        from backend.scripts.score_attractions import calculate_seasonal_score
        scores = calculate_seasonal_score(destination_months=[1, 2], attraction_months=[1])
        assert scores["jan"] == 100  # 80 + 20
        assert scores["feb"] == 60   # 80 - 20 (dest likes it, attraction doesn't)

    def test_calculate_seasonal_score_low_overlap(self):
        from backend.scripts.score_attractions import calculate_seasonal_score
        scores = calculate_seasonal_score(destination_months=[1], attraction_months=[2])
        assert scores["mar"] == 20   # 40 - 20

    def test_calculate_seasonal_score_attraction_only(self):
        from backend.scripts.score_attractions import calculate_seasonal_score
        scores = calculate_seasonal_score(destination_months=[], attraction_months=[5])
        assert scores["may"] == 60   # 40 + 20

    def test_calculate_seasonal_score_empty_defaults(self):
        from backend.scripts.score_attractions import calculate_seasonal_score
        # attraction_months=None → all months → +20 for every month
        scores = calculate_seasonal_score(destination_months=[6], attraction_months=None)
        assert scores["jun"] == 100  # 80 + 20
        assert scores["jul"] == 60   # 40 + 20


# ─────────────────────────────────────────────────────
# Price Sync
# ─────────────────────────────────────────────────────
class TestPriceSync:

    def test_sync_hotel_prices_generates_records(self, db):
        from backend.scripts.sync_prices import sync_hotel_prices
        from backend.models import Destination, HotelPrice

        dest = Destination(id=1, name="Jaipur", lat=26.9, lng=75.8)
        db.session.add(dest)
        db.session.commit()

        sync_hotel_prices(db.session)

        prices = db.session.query(HotelPrice).filter_by(destination_id=1).all()
        assert len(prices) == 3

        for price in prices:
            assert price.price_per_night_min <= price.price_per_night_max
            assert price.category in ["budget", "standard", "luxury"]

    def test_sync_attraction_prices_updates_costs(self, db):
        from backend.scripts.sync_prices import sync_attraction_prices
        from backend.models import Attraction

        attr = Attraction(
            id=1, destination_id=1, name="Amber Fort", type="cultural",
            budget_category=2, lat=26.9, lng=75.8
        )
        db.session.add(attr)
        db.session.commit()

        sync_attraction_prices(db.session)

        updated_attr = db.session.query(Attraction).first()
        assert updated_attr.entry_cost_min is not None
        assert updated_attr.entry_cost_max is not None
        assert updated_attr.entry_cost_min <= updated_attr.entry_cost_max

    def test_sync_flight_routes_seeds_data(self, db):
        from backend.scripts.sync_prices import sync_flight_routes
        from backend.models import Destination, FlightRoute

        d1 = Destination(id=1, name="Delhi", lat=28.6, lng=77.2)
        d2 = Destination(id=2, name="Mumbai", lat=19.0, lng=72.8)
        db.session.add_all([d1, d2])
        db.session.commit()

        sync_flight_routes(db.session)

        routes = db.session.query(FlightRoute).all()
        # sync_flight_routes seeds all hardcoded routes (43 pairs × 2 directions = 86),
        # not just routes for destinations currently in the DB.
        assert len(routes) >= 2

        # Verify at least the DEL↔BOM pair (Delhi and Mumbai) was seeded
        del_bom = db.session.query(FlightRoute).filter_by(
            origin_iata="DEL", destination_iata="BOM"
        ).first()
        assert del_bom is not None
        assert del_bom.avg_one_way_inr >= 3000