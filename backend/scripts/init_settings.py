import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.database import db, SessionLocal
from backend.models import EngineSetting
from backend import app

def init_settings():
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
            {"key": "GEMINI_MODEL", "value": "gemini-1.5-pro", "description": "The primary LLM model used for generation"},
            {"key": "THEME_THRESHOLD", "value": "0.20", "description": "Minimum topical relevance score (0.0 to 1.0)"},
        ]

        for setting in defaults:
            existing = db.session.query(EngineSetting).filter_by(key=setting["key"]).first()
            if not existing:
                print(f"Adding default setting: {setting['key']} = {setting['value']}")
                new_setting = EngineSetting(
                    key=setting["key"],
                    value=setting["value"],
                    description=setting["description"]
                )
                db.session.add(new_setting)
            else:
                print(f"Setting {setting['key']} already exists.")
        
        db.session.commit()
        print("Settings initialization complete.")

if __name__ == "__main__":
    init_settings()
