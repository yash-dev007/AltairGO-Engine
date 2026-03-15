import sys
import os
import logging
from sqlalchemy import text

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import engine

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

MIGRATION_SQL = [
    # 1. Enable PostGIS
    "CREATE EXTENSION IF NOT EXISTS postgis;",

    # 2. Alter Destination table
    """
    ALTER TABLE destination 
    ADD COLUMN IF NOT EXISTS lat FLOAT,
    ADD COLUMN IF NOT EXISTS lng FLOAT,
    ADD COLUMN IF NOT EXISTS coordinates geography(POINT, 4326),
    ADD COLUMN IF NOT EXISTS h3_index_r7 VARCHAR(16),
    ADD COLUMN IF NOT EXISTS h3_index_r9 VARCHAR(16),
    ADD COLUMN IF NOT EXISTS avg_visit_duration_hours FLOAT DEFAULT 3.0,
    ADD COLUMN IF NOT EXISTS crowd_level_by_hour JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS best_months JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS compatible_traveler_types JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS budget_category INTEGER DEFAULT 2,
    ADD COLUMN IF NOT EXISTS connects_well_with JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS popularity_score FLOAT DEFAULT 50.0,
    ADD COLUMN IF NOT EXISTS user_skip_rate FLOAT DEFAULT 0.0;
    """,

    # 3. Alter Attraction table
    """
    ALTER TABLE attraction 
    ADD COLUMN IF NOT EXISTS lat FLOAT,
    ADD COLUMN IF NOT EXISTS lng FLOAT,
    ADD COLUMN IF NOT EXISTS coordinates geography(POINT, 4326),
    ADD COLUMN IF NOT EXISTS h3_index_r9 VARCHAR(16),
    ADD COLUMN IF NOT EXISTS avg_visit_duration_hours FLOAT DEFAULT 1.5,
    ADD COLUMN IF NOT EXISTS crowd_level_by_hour JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS best_months JSONB DEFAULT '[1,2,3,4,5,6,7,8,9,10,11,12]',
    ADD COLUMN IF NOT EXISTS best_visit_time_hour INTEGER DEFAULT 10,
    ADD COLUMN IF NOT EXISTS compatible_traveler_types JSONB DEFAULT '["solo_male","solo_female","couple","family","group"]',
    ADD COLUMN IF NOT EXISTS budget_category INTEGER DEFAULT 2,
    ADD COLUMN IF NOT EXISTS connects_well_with JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS popularity_score FLOAT DEFAULT 50.0,
    ADD COLUMN IF NOT EXISTS user_skip_rate FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS osm_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS wikidata_id VARCHAR(32);
    """,

    # 4. Create Signal Table
    """
    CREATE TABLE IF NOT EXISTS attraction_signal (
        id SERIAL PRIMARY KEY,
        attraction_id INTEGER REFERENCES attraction(id) ON DELETE CASCADE,
        event_type VARCHAR(32) NOT NULL,
        traveler_type VARCHAR(32),
        trip_style VARCHAR(16),
        day_position INTEGER,
        trip_duration INTEGER,
        budget_tier INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,

    # 5. Constraints and Indexes
    "CREATE INDEX IF NOT EXISTS idx_attraction_osm_id ON attraction(osm_id);",
    "CREATE INDEX IF NOT EXISTS idx_destination_coords ON destination USING GIST(coordinates);",
    "CREATE INDEX IF NOT EXISTS idx_attraction_coords ON attraction USING GIST(coordinates);",
    "CREATE INDEX IF NOT EXISTS idx_attraction_h3_r9 ON attraction(h3_index_r9);",
]

def apply_migration():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            for sql in MIGRATION_SQL:
                conn.execute(text(sql))
            transaction.commit()
            log.info("Phase 1 Migration applied successfully.")
        except Exception as e:
            transaction.rollback()
            log.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    apply_migration()
