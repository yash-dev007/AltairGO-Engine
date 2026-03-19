import os
import sys
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.database import db, SessionLocal
from backend.models import EngineSetting
from backend import app

def init_settings(force_update: bool = False):
    flask_app = app.create_app()
    with flask_app.app_context():
        # Create table if it doesn't exist
        print("Ensuring engine_settings table exists...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS engine_settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value VARCHAR(500) NOT NULL,
                description VARCHAR(255),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()

        defaults = [
            {"key": "VALIDATION_STRICT", "value": "false", "description": "Enforce strict schema validation for outputs"},
            {"key": "GEMINI_MODEL", "value": "gemini-2.0-flash", "description": "The primary LLM model used for generation"},
            {"key": "THEME_THRESHOLD", "value": "0.20", "description": "Minimum topical relevance score (0.0 to 1.0)"},
            {"key": "MAX_ATTRACTIONS_PER_GENERATION", "value": "500", "description": "Max attractions loaded from DB per generation run"},
            {"key": "POPULARITY_HARD_FLOOR", "value": "25", "description": "Minimum popularity score for an attraction to pass the primary filter"},
            {"key": "POPULARITY_SOFT_FLOOR", "value": "10", "description": "Fallback popularity floor when hard floor yields 0 results"},
            {"key": "SEASONAL_SCORE_GATE", "value": "40", "description": "Minimum seasonal score required to pass the seasonal filter"},
            {"key": "INTERESTS_CATEGORY_MULTIPLIER", "value": "2", "description": "Category cap multiplier for attraction types matching user interests"},
            {"key": "AVG_URBAN_SPEED_KMH", "value": "15", "description": "Assumed urban travel speed in km/h for schedule timing"},
            {"key": "MAX_ACTIVITIES_PER_DAY", "value": "6", "description": "Maximum number of activities allowed per day in a generated itinerary"},
        ]

        for setting in defaults:
            existing = db.session.query(EngineSetting).filter_by(key=setting["key"]).first()
            if not existing:
                print(f"Adding:   {setting['key']} = {setting['value']}")
                db.session.add(EngineSetting(
                    key=setting["key"],
                    value=setting["value"],
                    description=setting["description"],
                ))
            elif force_update:
                print(f"Updating: {setting['key']} = {setting['value']}")
                existing.value = setting["value"]
                existing.description = setting["description"]
            else:
                print(f"Skipping: {setting['key']} (already exists; use --force to overwrite)")

        db.session.commit()
        print("Settings initialization complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialise default engine settings.")
    parser.add_argument(
        "--force", dest="force_update", action="store_true",
        help="Overwrite existing settings with default values.",
    )
    args = parser.parse_args()
    init_settings(force_update=args.force_update)
