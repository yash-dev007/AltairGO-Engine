import os
from sqlalchemy import Column, Float, String, Integer, JSON, ForeignKey, DateTime, SmallInteger, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    highlights               = Column(JSON, default=list)
    best_time_months         = Column(JSON, default=list)
    vibe_tags                = Column(JSON, default=list)
    state_id                 = Column(Integer, ForeignKey('state.id'))
    
    # ── Phase 1 Intelligence Architecture ────────────────────────
    lat                      = Column(Float, nullable=True)
    lng                      = Column(Float, nullable=True)
    coordinates              = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    h3_index_r7              = Column(String(16), nullable=True)
    h3_index_r9              = Column(String(16), nullable=True)    # Intelligence Fields
    avg_visit_duration_hours = Column(Float, default=1.0)
    best_visit_time_hour     = Column(SmallInteger, default=10) # 0-23
    crowd_peak_hours         = Column(JSON, default=list) # e.g. [14, 15, 16]
    popularity_score         = Column(SmallInteger, default=50) # 0-100
    compatible_traveler_types= Column(JSON, default=list) # e.g. ["solo_male", "couple"]
    budget_category          = Column(String(20), default="mid-range") # "budget", "mid-range", "luxury"
    seasonal_score           = Column(JSON, default=dict) # e.g. {"oct": 95, "jun": 30}
    skip_rate                = Column(Float, default=0.0)
    
    # Coordinates (Plain floats for easier serialization/testing fallback)
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
    lat                      = Column(Float, nullable=True)
    lng                      = Column(Float, nullable=True)
    latitude                 = Column(Float, nullable=True)
    longitude                = Column(Float, nullable=True)
    coordinates              = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    h3_index_r7              = Column(String(16), nullable=True)
    h3_index_r9              = Column(String(16), nullable=True)
    avg_visit_duration_hours = Column(Float, default=1.5)
    crowd_level_by_hour      = Column(JSON, default=dict)
    best_months              = Column(JSON, default=lambda: list(range(1, 13)))
    best_visit_time_hour     = Column(Integer, default=10)
    compatible_traveler_types= Column(JSON, default=lambda: ["solo_male","solo_female","couple","family","group"])
    budget_category          = Column(String(20), default="mid-range", index=True)
    seasonal_score           = Column(JSON, default=dict)
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
    last_synced         = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    last_synced        = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    user_id         = Column(Integer, nullable=True)
    status          = Column(String(50), default='queued') # queued, processing, completed, failed
    payload         = Column(JSON, nullable=True)
    result          = Column(JSON, nullable=True)
    error_message   = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

