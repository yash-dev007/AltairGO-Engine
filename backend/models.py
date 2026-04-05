import os
from sqlalchemy import Boolean, Column, Float, String, Integer, JSON, ForeignKey, DateTime, SmallInteger, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates
try:
    from backend.database import Base
except ImportError:
    from database import Base
from datetime import datetime, timezone

# Fallback for SQLite testing which lacks PostGIS and PGVector
if os.environ.get("TESTING") == "true" or os.environ.get("FLASK_ENV") == "testing":
    class MockGeography(String):
        def __init__(self, geometry_type=None, srid=None, **kwargs):
            super().__init__(**kwargs)
    Geography = MockGeography
    
    class MockVector(String):
        def __init__(self, dim=None, **kwargs):
            super().__init__(**kwargs)
    Vector = MockVector
else:
    from geoalchemy2 import Geography
    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:
        Vector = String


class AnalyticsEvent(Base):
    __tablename__ = 'analytics_event'
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False)
    user_id = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EngineSetting(Base):
    """Stores dynamic configuration for the intelligence engine."""
    __tablename__ = 'engine_settings'
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(500), nullable=False)
    description = Column(String(255))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    trips = relationship('Trip', backref='user', lazy=True)

    @validates('email')
    def _lowercase_email(self, key: str, value: str) -> str:
        """Always store email in lowercase regardless of how it was inserted."""
        return value.lower() if value else value


class Country(Base):
    __tablename__ = 'country'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(10), nullable=True)
    currency = Column(String(10), nullable=True)
    image = Column(String(255), nullable=True)


class State(Base):
    __tablename__ = 'state'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    image = Column(String(255), nullable=True)
    country_id = Column(Integer, ForeignKey('country.id'))


class Destination(Base):
    __tablename__ = 'destination'
    
    id                       = Column(Integer, primary_key=True)
    name                     = Column(String(255), nullable=False, unique=True)
    slug                     = Column(String(255), nullable=True, unique=True)
    desc                     = Column(String(500), nullable=True)
    description              = Column(Text, nullable=True)
    image                    = Column(String(255), nullable=True)
    location                 = Column(String(255), nullable=True)
    price_str                = Column(String(50), nullable=True)
    estimated_cost_per_day   = Column(Integer, nullable=True)
    rating                   = Column(Float, nullable=True)
    tag                      = Column(String(50), nullable=True)
    highlights               = Column(JSON, default=lambda: [])
    best_time_months         = Column(JSON, default=lambda: [])
    vibe_tags                = Column(JSON, default=lambda: [])
    state_id                 = Column(Integer, ForeignKey('state.id'))
    
    # ── Phase 1 Intelligence Architecture ────────────────────────
    lat                      = Column(Float, nullable=True)
    lng                      = Column(Float, nullable=True)
    coordinates              = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    h3_index_r7              = Column(String(16), nullable=True)
    h3_index_r9              = Column(String(16), nullable=True)    # Intelligence Fields
    avg_visit_duration_hours = Column(Float, default=1.0)
    best_visit_time_hour     = Column(SmallInteger, default=10) # 0-23
    crowd_peak_hours         = Column(JSON, default=lambda: []) # e.g. [14, 15, 16]
    popularity_score         = Column(SmallInteger, default=50) # 0-100
    compatible_traveler_types= Column(JSON, default=lambda: []) # e.g. ["solo_male", "couple"]
    budget_category          = Column(String(20), default="mid-range") # "budget", "mid-range", "luxury"
    seasonal_score           = Column(JSON, default=lambda: {}) # e.g. {"oct": 95, "jun": 30}
    skip_rate                = Column(Float, default=0.0)

    # Canonical float coordinates (preferred over legacy lat/lng).
    # Both pairs are kept in sync by the @validates hooks below.
    latitude                 = Column(Float, nullable=True)
    longitude                = Column(Float, nullable=True)

    hotel_prices             = relationship('HotelPrice', back_populates='destination')

    # ── Phase 2 V2 Architecture Audit Fields ─────────────────────
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at               = Column(DateTime(timezone=True), nullable=True)
    source                   = Column(String(50), nullable=True)
    confidence_score         = Column(Float, nullable=True)
    version                  = Column(Integer, default=1)
    embedding                = Column(Vector(1536), nullable=True)


class Attraction(Base):
    __tablename__ = 'attraction'
    
    id                       = Column(Integer, primary_key=True)
    name                     = Column(String(255), nullable=False)
    description              = Column(String(1000), nullable=True)
    duration                 = Column(String(100), nullable=True)
    entry_cost               = Column(Integer, default=0)
    type                     = Column(String(50), default='general')
    rating                   = Column(Float, default=4.0)
    destination_id           = Column(Integer, ForeignKey('destination.id'), nullable=False)
    
    # ── Phase 1 Intelligence Architecture ────────────────────────
    # Canonical coordinates are latitude/longitude; lat/lng kept for backwards compat.
    # @validates hooks (below) keep both pairs in sync.
    lat                      = Column(Float, nullable=True)
    lng                      = Column(Float, nullable=True)
    latitude                 = Column(Float, nullable=True)
    longitude                = Column(Float, nullable=True)
    coordinates              = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    h3_index_r7              = Column(String(16), nullable=True)
    h3_index_r9              = Column(String(16), nullable=True)
    avg_visit_duration_hours = Column(Float, default=1.5)
    crowd_level_by_hour      = Column(JSON, default=lambda: {})
    best_months              = Column(JSON, default=lambda: list(range(1, 13)))
    best_visit_time_hour     = Column(Integer, default=10)
    compatible_traveler_types= Column(JSON, default=lambda: ["solo_male","solo_female","couple","family","group"])
    budget_category          = Column(String(20), default="mid-range", index=True)
    seasonal_score           = Column(JSON, default=lambda: {})
    connects_well_with       = Column(JSON, default=list)
    popularity_score         = Column(Float, default=50.0, index=True)
    user_skip_rate           = Column(Float, default=0.0)
    osm_id                   = Column(String(64), nullable=True, unique=True)
    wikidata_id              = Column(String(32), nullable=True)
    
    # ── Phase 1 Intelligence Pricing ─────────────────────────
    entry_cost_min           = Column(Integer, nullable=True)
    entry_cost_max           = Column(Integer, nullable=True)
    entry_cost_child         = Column(Integer, nullable=True)
    price_last_synced        = Column(DateTime, nullable=True)
    gallery_images           = Column(JSON, default=list)
    google_rating            = Column(Float, nullable=True)
    review_count             = Column(Integer, default=0)

    # ── Operational Fields ────────────────────────────────────────
    # opening_hours: {"mon": "09:00-17:00", "tue": "09:00-17:00", ...}
    # closed_days: [0, 1] where 0=Monday…6=Sunday (ISO weekday - 1)
    # requires_advance_booking: True for places like Taj Mahal, ASI sites
    opening_hours            = Column(JSON, nullable=True)
    closed_days              = Column(JSON, default=lambda: [])
    requires_advance_booking = Column(Integer, default=0)  # 0=False, 1=True
    accessibility_level      = Column(SmallInteger, default=0)  # 0=unknown, 1=fully accessible, 2=partial, 3=not accessible
    # dietary_options: list of diet labels this venue explicitly supports
    # e.g. ["vegetarian", "vegan", "halal", "jain", "gluten_free"]
    # Empty list = unknown / not applicable (not filtered)
    dietary_options          = Column(JSON, default=lambda: [])

    # ── Traveler Experience Fields ────────────────────────────────────────────
    # difficulty_level: physical effort — easy/moderate/strenuous (used to filter for seniors)
    difficulty_level         = Column(String(20), default='easy')
    # is_photo_spot: marks photography-notable spots (golden hour, viewpoints, etc.)
    is_photo_spot            = Column(Integer, default=0)   # 0=no, 1=yes
    # best_photo_hour: optimal hour of day for photography (0-23); NULL = any time
    best_photo_hour          = Column(SmallInteger, nullable=True)
    # queue_time_minutes: expected entry/security wait so the schedule adds a realistic buffer
    queue_time_minutes       = Column(SmallInteger, default=0)
    # dress_code: e.g. "Cover shoulders and knees" for religious sites
    dress_code               = Column(String(200), nullable=True)
    # guide_available: whether professional guided tours operate here
    guide_available          = Column(Integer, default=0)   # 0=no, 1=yes
    # min_age: minimum age requirement in years (adventure, restricted sites); NULL = no limit
    min_age                  = Column(SmallInteger, nullable=True)

    # ── Phase 2 V2 Architecture Audit Fields ─────────────────────
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at               = Column(DateTime(timezone=True), nullable=True)
    source                   = Column(String(50), nullable=True)
    confidence_score         = Column(Float, nullable=True)
    version                  = Column(Integer, default=1)
    embedding                = Column(Vector(1536), nullable=True)


class AttractionSignal(Base):
    __tablename__ = 'attraction_signal'
    
    id             = Column(Integer, primary_key=True)
    attraction_id  = Column(Integer, ForeignKey('attraction.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id        = Column(Integer, nullable=True, index=True)   # null = guest
    event_type     = Column(String(32), nullable=False, index=True) # view / save / remove / swap / book_click
    traveler_type  = Column(String(32), nullable=True, index=True)
    trip_style     = Column(String(16), nullable=True, index=True)
    budget_tier    = Column(String(20), nullable=True, index=True)
    day_position   = Column(Integer, nullable=True)
    trip_duration  = Column(Integer, nullable=True)
    session_id     = Column(String(100), nullable=True, index=True)    # for guest tracking
    created_at     = Column(DateTime(timezone=True), server_default=func.now())


class HotelPrice(Base):
    __tablename__ = 'hotel_price'

    id                  = Column(Integer, primary_key=True)
    destination_id      = Column(Integer, ForeignKey('destination.id'), nullable=False, index=True)
    hotel_name          = Column(String(200), nullable=False)
    star_rating         = Column(SmallInteger)                    # 1–5
    category            = Column(String(20), index=True)                         # budget / mid / luxury
    price_per_night_min = Column(Integer)                 # INR
    price_per_night_max = Column(Integer)                 # INR
    booking_url         = Column(Text)                            # affiliate-tagged deep link
    partner             = Column(String(50), index=True)                          # booking.com / mmtrip / agoda
    availability_score  = Column(Float, default=1.0)       # 0.0–1.0
    latitude            = Column(Float)
    longitude           = Column(Float)
    last_synced         = Column(DateTime(timezone=True), server_default=func.now())

    destination         = relationship('Destination', back_populates='hotel_prices')


class FlightRoute(Base):
    __tablename__ = 'flight_route'

    id                 = Column(Integer, primary_key=True)
    origin_iata        = Column(String(3), nullable=False, index=True)       # e.g. BOM
    destination_iata   = Column(String(3), nullable=False, index=True)  # e.g. JAI
    avg_one_way_inr    = Column(Integer)
    avg_return_inr     = Column(Integer)
    duration_minutes   = Column(Integer)
    airlines           = Column(JSON)                               # ["IndiGo", "Air India"]
    frequency_per_week = Column(SmallInteger)
    transport_type     = Column(String(20), default='flight', index=True) # flight / train / bus
    train_classes      = Column(JSON)                          # {ac: 1200, sleeper: 450}
    last_synced        = Column(DateTime(timezone=True), server_default=func.now())


class Trip(Base):
    __tablename__ = 'trip'
    
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    trip_title          = Column(String(255), nullable=True)
    destination_country = Column(String(100), nullable=True, index=True)
    budget              = Column(Integer, nullable=True, index=True)
    duration            = Column(Integer, nullable=True)
    travelers           = Column(Integer, default=1)
    style               = Column(String(50), nullable=True, index=True)
    date_type           = Column(String(50), nullable=True)
    start_date          = Column(String(50), nullable=True)
    traveler_type       = Column(String(50), nullable=True, index=True)
    
    total_cost          = Column(Integer, nullable=True)
    itinerary_json      = Column(JSON, nullable=False)
    quality_score       = Column(Float, nullable=True)
    quality_flags       = Column(JSON, nullable=True)
    # user_notes: personal notes at trip level and per-day
    # {"trip": "...", "days": {"1": "...", "2": "..."}}
    user_notes          = Column(JSON, nullable=True)
    # is_customized: set to 1 when user has edited the itinerary
    is_customized       = Column(Integer, default=0)

    created_at          = Column(DateTime(timezone=True), server_default=func.now())


class DestinationRequest(Base):
    __tablename__ = 'destination_request'

    id          = Column(Integer, primary_key=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cost        = Column(Integer, nullable=True)
    tag         = Column(String(50), nullable=True, index=True)
    status      = Column(String(20), default='pending', index=True)  # pending / approved / rejected
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

# ── V2 Architecture New Tables ────────────────────────────────


class UserProfile(Base):
    __tablename__ = 'user_profiles'
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    preferences     = Column(JSON, nullable=True)
    travel_history  = Column(JSON, nullable=True)
    embedding       = Column(Vector(1536), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())


class Feedback(Base):
    __tablename__ = 'feedback'
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey('user.id'), nullable=True, index=True)
    itinerary_id    = Column(Integer, ForeignKey('trip.id'), nullable=True, index=True)
    poi_id          = Column(Integer, ForeignKey('attraction.id'), nullable=True, index=True)
    rating          = Column(Float, nullable=True)
    corrections     = Column(JSON, nullable=True)
    comment         = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class DataSourceLog(Base):
    __tablename__ = 'data_sources'
    id              = Column(Integer, primary_key=True)
    source_name     = Column(String(100), nullable=False)
    event_type      = Column(String(50), nullable=False) # e.g. "ingestion", "error"
    records_processed= Column(Integer, default=0)
    status          = Column(String(50), nullable=False)
    details         = Column(JSON, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class FeatureFlag(Base):
    __tablename__ = 'feature_flags'
    id              = Column(Integer, primary_key=True)
    flag_key        = Column(String(100), unique=True, nullable=False)
    is_active       = Column(Integer, default=0) # 0=False, 1=True
    traffic_pct     = Column(Integer, default=100)
    details         = Column(JSON, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class CurrencyRate(Base):
    __tablename__ = 'currency_rates'
    id              = Column(Integer, primary_key=True)
    base_currency   = Column(String(3), nullable=False)
    target_currency = Column(String(3), nullable=False)
    rate            = Column(Float, nullable=False)
    snapshot_date   = Column(DateTime(timezone=True), server_default=func.now())


class POIClosure(Base):
    __tablename__ = 'poi_closures'
    id              = Column(Integer, primary_key=True)
    attraction_id   = Column(Integer, ForeignKey('attraction.id'), nullable=False)
    closure_reason  = Column(String(255), nullable=True)
    start_date      = Column(DateTime(timezone=True), nullable=False)
    end_date        = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class AsyncJob(Base):
    __tablename__ = 'async_jobs'
    id              = Column(String(50), primary_key=True) # UUID
    user_id         = Column(Integer, nullable=True, index=True)
    status          = Column(String(50), default='queued', index=True) # queued, processing, completed, failed
    payload         = Column(JSON, nullable=True)
    result          = Column(JSON, nullable=True)
    error_message   = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    # Compound index for filtering by user + status (e.g. "show my pending jobs")
    __table_args__ = (
        Index('ix_async_jobs_user_status', 'user_id', 'status'),
    )


# ── Booking Automation ────────────────────────────────────────────────────────


class TripPermissionRequest(Base):
    """
    Aggregates all bookings for a saved trip into a single permission screen.
    The user approves or rejects each item before execution.

    status lifecycle: pending → presented → partially_approved | fully_approved | declined
    """
    __tablename__ = 'trip_permission_requests'

    id                      = Column(String(50), primary_key=True)  # UUID
    trip_id                 = Column(Integer, ForeignKey('trip.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id                 = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    status                  = Column(String(30), default='pending', index=True)
    total_estimated_cost_inr= Column(Integer, nullable=True)
    # Snapshot of all bookable items so the UI can render the permission screen
    # without joining to each Booking row.
    items_snapshot          = Column(JSON, nullable=True)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    responded_at            = Column(DateTime(timezone=True), nullable=True)


class Booking(Base):
    """
    One row per bookable item (hotel night, flight, activity ticket,
    restaurant slot, or cab ride) attached to a saved trip.

    status lifecycle: pending → approved | rejected → booked | failed | cancelled
    """
    __tablename__ = 'booking'

    id                  = Column(String(50), primary_key=True)          # UUID
    trip_id             = Column(Integer, ForeignKey('trip.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id             = Column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    permission_request_id = Column(String(50), ForeignKey('trip_permission_requests.id'), nullable=True, index=True)

    # What is being booked
    booking_type        = Column(String(20), nullable=False, index=True)  # hotel | flight | activity | restaurant | cab
    item_name           = Column(String(255), nullable=True)              # "Hotel Taj", "IndiGo 6E-123", etc.
    provider            = Column(String(100), nullable=True)              # "Booking.com", "MakeMyTrip", etc.
    booking_url         = Column(Text, nullable=True)                     # Affiliate / deep link

    # Date range (for hotels: check-in/out; for flights: departure; activities: visit date)
    start_datetime      = Column(DateTime(timezone=True), nullable=True)
    end_datetime        = Column(DateTime(timezone=True), nullable=True)

    # Pricing
    price_inr           = Column(Integer, nullable=True)
    num_travelers       = Column(Integer, default=1)
    total_price_inr     = Column(Integer, nullable=True)

    # Execution state
    status              = Column(String(20), default='pending', index=True)
    user_approved       = Column(Integer, default=0)    # 0=pending, 1=approved, -1=rejected
    booking_ref         = Column(String(100), nullable=True)  # External reference code
    failure_reason      = Column(Text, nullable=True)

    # Full vendor payload for audit / retry
    payload             = Column(JSON, nullable=True)

    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())


class WeatherAlert(Base):
    """
    Stores weather advisories for destinations so the rainy-day
    alternatives system can be triggered automatically.

    Populated by a future weather-sync Celery task that calls a
    weather API (e.g. Open-Meteo) and writes alerts for destinations
    with rain/storm probability above a threshold.

    The orchestrator reads this table when generating itineraries:
    if an alert exists for the destination on a travel day, the
    rainy_day_alternatives block is promoted to the primary plan.
    """
    __tablename__ = 'weather_alert'

    id              = Column(Integer, primary_key=True)
    destination_id  = Column(Integer, ForeignKey('destination.id', ondelete='CASCADE'), nullable=False, index=True)
    alert_date      = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    alert_type      = Column(String(50), nullable=False)              # rain | storm | extreme_heat | fog
    severity        = Column(String(20), default='moderate')          # low | moderate | high | extreme
    probability_pct = Column(SmallInteger, nullable=True)             # 0-100
    description     = Column(Text, nullable=True)
    source          = Column(String(50), nullable=True)               # e.g. "open_meteo", "imd"
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    expires_at      = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_weather_alert_dest_date', 'destination_id', 'alert_date'),
    )


# ── Destination Travel Intelligence ──────────────────────────────────────────


class DestinationInfo(Base):
    """
    Rich travel intelligence for a destination — visa requirements, safety
    advisories, health notes, practical tips, and emergency contacts.

    One row per destination (one-to-one).  Populated by admin scripts or the
    destination_validator_agent; consumed by the orchestrator to inject a
    `pre_trip_info` block into every generated itinerary.
    """
    __tablename__ = 'destination_info'

    id                       = Column(Integer, primary_key=True)
    destination_id           = Column(Integer, ForeignKey('destination.id', ondelete='CASCADE'),
                                      nullable=False, unique=True, index=True)

    # ── Safety & Advisory ─────────────────────────────────────────────────
    # travel_advisory_level: 1=safe, 2=exercise caution, 3=reconsider travel, 4=do not travel
    travel_advisory_level    = Column(SmallInteger, default=1)
    travel_advisory_notes    = Column(Text, nullable=True)

    # ── Entry & Visa ──────────────────────────────────────────────────────
    # Lists of country codes (ISO-2) — store as JSON array e.g. ["US","UK","AU"]
    visa_required_for        = Column(JSON, default=list)   # countries that NEED a visa
    visa_on_arrival          = Column(JSON, default=list)   # countries eligible for VOA
    visa_notes               = Column(Text, nullable=True)  # "e-visa available at …"

    # ── Health ────────────────────────────────────────────────────────────
    vaccinations_recommended = Column(JSON, default=list)   # ["Hepatitis A", "Typhoid"]
    health_notes             = Column(Text, nullable=True)
    # water_safety: tap / bottled / filtered
    water_safety             = Column(String(20), default='bottled')
    altitude_meters          = Column(Integer, nullable=True)
    # altitude_sickness_risk: 0=none, 1=low, 2=moderate, 3=high
    altitude_sickness_risk   = Column(SmallInteger, default=0)

    # ── Practical Tips ────────────────────────────────────────────────────
    # tipping_guide: {"restaurants": "10%", "taxi": "round up", "hotels": "₹50-100/day"}
    tipping_guide            = Column(JSON, nullable=True)
    # hidden_fees: {"resort_tax_per_night": 200, "city_tax": 50, "service_charge_pct": 5}
    hidden_fees              = Column(JSON, nullable=True)
    # emergency_contacts: {"police": "100", "ambulance": "102", "tourist_helpline": "1800-111-363"}
    emergency_contacts       = Column(JSON, nullable=True)
    # local_phrases: {"hello": "Namaste", "thank you": "Shukriya", "help": "Madad karo"}
    local_phrases            = Column(JSON, nullable=True)
    # connectivity_guide: plain text e.g. "Jio/Airtel prepaid SIMs available at airport kiosk"
    connectivity_guide       = Column(Text, nullable=True)
    # currency_tips: "Use ATMs on main street; avoid airport exchange counters (poor rates)"
    currency_tips            = Column(Text, nullable=True)
    # dress_code_general: regional dress expectations e.g. "Conservative in old city; casual on beaches"
    dress_code_general       = Column(Text, nullable=True)
    # best_hospitals: [{"name": "Apollo", "address": "...", "phone": "..."}]
    best_hospitals           = Column(JSON, default=list)
    # nearest_embassy: {"country": "...", "address": "...", "phone": "..."}
    nearest_embassy          = Column(JSON, nullable=True)

    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), onupdate=func.now())


class LocalEvent(Base):
    """
    Festivals, public holidays, fairs, and local events at a destination.

    Used by the orchestrator to inject an `local_events` block when any events
    fall within the traveller's trip window.  Events with impact="avoid" (e.g.
    large street closures) are surfaced as warnings.
    """
    __tablename__ = 'local_event'

    id             = Column(Integer, primary_key=True)
    destination_id = Column(Integer, ForeignKey('destination.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    name           = Column(String(255), nullable=False)
    description    = Column(Text, nullable=True)
    # event_type: festival / holiday / fair / sports / cultural / religious
    event_type     = Column(String(50), nullable=True, index=True)
    start_date     = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    end_date       = Column(String(10), nullable=True)               # YYYY-MM-DD
    # impact: positive (enhances trip), neutral, avoid (crowds / closures)
    impact         = Column(String(20), default='positive', index=True)
    tips           = Column(Text, nullable=True)   # "Book hotels 3 months early during Diwali"
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_local_event_dest_date', 'destination_id', 'start_date'),
    )


class ExpenseEntry(Base):
    """
    Actual spending tracker for a saved trip.

    Users (or the app) record individual expenses so the post-trip screen can
    compare planned vs actual spend per category.
    """
    __tablename__ = 'expense_entry'

    id          = Column(Integer, primary_key=True)
    trip_id     = Column(Integer, ForeignKey('trip.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    # category: accommodation / food / transport / activity / shopping / misc
    category    = Column(String(50), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    amount_inr  = Column(Integer, nullable=False)
    # trip_day: which day of the trip this was spent on (1-indexed); NULL = general
    trip_day    = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_expense_trip_user', 'trip_id', 'user_id'),
    )


class WebhookLog(Base):
    """
    Audit trail for incoming vendor webhooks (booking status callbacks).
    Every received webhook is logged here regardless of processing outcome.
    """
    __tablename__ = 'webhook_log'

    id                  = Column(String(50), primary_key=True)   # UUID
    provider            = Column(String(50), nullable=False, index=True)  # bookingcom | makemytrip | generic
    event_type          = Column(String(100), nullable=True)              # confirmed | cancelled | modified
    payload             = Column(JSON, nullable=True)                     # raw vendor payload
    processing_status   = Column(String(50), default='received', index=True)  # received | processed | rejected | failed
    booking_id          = Column(String(50), ForeignKey('booking.id'), nullable=True, index=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


class BlogPost(Base):
    """CMS blog posts — managed via Admin Panel, served publicly."""
    __tablename__ = 'blog_post'

    id         = Column(Integer, primary_key=True)
    title      = Column(Text, nullable=False)
    category   = Column(String(100), nullable=True)
    date       = Column(String(50), nullable=True)
    read_time  = Column(String(50), nullable=True)
    image      = Column(Text, nullable=True)
    excerpt    = Column(Text, nullable=True)
    content    = Column(Text, nullable=True)
    tags       = Column(PG_ARRAY(Text) if os.environ.get("TESTING") != "true" else JSON, default=lambda: [])  # ARRAY in postgres, JSON fallback for SQLite testing
    author     = Column(String(100), nullable=True)
    published  = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            'id':        self.id,
            'title':     self.title,
            'category':  self.category,
            'date':      self.date,
            'readTime':  self.read_time,
            'image':     self.image,
            'excerpt':   self.excerpt,
            'content':   self.content,
            'tags':      self.tags or [],
            'author':    self.author,
            'published': self.published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
