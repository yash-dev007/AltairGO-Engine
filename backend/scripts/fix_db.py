import os
import sys
# Add current directory to path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.database import db
from sqlalchemy import text
from backend.models import User, Destination, Attraction, Trip, DestinationRequest, AnalyticsEvent, AttractionSignal

def get_columns(table_name):
    result = db.session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = 'public'"))
    return [r[0] for r in result]

def add_column_if_missing(table_name, col_name, col_type):
    existing = get_columns(table_name)
    if col_name.lower() not in [c.lower() for c in existing]:
        try:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            print(f"SUCCESS: Added {col_name} to {table_name}")
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: Failed to add {col_name} to {table_name}: {e}")
    else:
        # print(f"INFO: {col_name} already exists in {table_name}")
        pass

def sync_schema():
    app = create_app()
    with app.app_context():
        # Common Audit Fields
        audit_fields = [
            ("created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP WITH TIME ZONE"),
            ("deleted_at", "TIMESTAMP WITH TIME ZONE"),
            ("version", "INTEGER DEFAULT 1"),
            ("source", "VARCHAR(50)"),
            ("confidence_score", "FLOAT")
        ]

        tables_to_check = ["user", "destination", "attraction", "trip", "destination_request", "analytics_event", "attraction_signal"]
        
        for table in tables_to_check:
            print(f"Checking table: {table}")
            for col, ctype in audit_fields:
                add_column_if_missing(table, col, ctype)
        
        # Specific fields for Trip
        add_column_if_missing("trip", "quality_score", "FLOAT")
        add_column_if_missing("trip", "quality_flags", "JSON")
        
        # Specific fields for Destination
        dest_fields = [
            ("lat", "FLOAT"), ("lng", "FLOAT"), 
            ("h3_index_r7", "VARCHAR(16)"), ("h3_index_r9", "VARCHAR(16)"),
            ("avg_visit_duration_hours", "FLOAT DEFAULT 1.0"), 
            ("best_visit_time_hour", "SMALLINT DEFAULT 10"),
            ("crowd_peak_hours", "JSON DEFAULT '[]'"), 
            ("popularity_score", "SMALLINT DEFAULT 50"),
            ("compatible_traveler_types", "JSON DEFAULT '[]'"), 
            ("budget_category", "VARCHAR(20) DEFAULT 'mid-range'"),
            ("seasonal_score", "JSON DEFAULT '{}'"), 
            ("skip_rate", "FLOAT DEFAULT 0.0"),
            ("latitude", "FLOAT"), ("longitude", "FLOAT")
        ]
        for col, ctype in dest_fields:
            add_column_if_missing("destination", col, ctype)

        # Vector fields (optional check, might fail if no pgvector)
        try:
            add_column_if_missing("destination", "embedding", "VECTOR(1536)")
            add_column_if_missing("user_profiles", "embedding", "VECTOR(1536)")
            add_column_if_missing("attraction", "embedding", "VECTOR(1536)")
        except Exception:
            print("INFO: Vector fields skipped (pgvector may not be installed)")

        print("Comprehensive schema sync complete.")

if __name__ == "__main__":
    sync_schema()
