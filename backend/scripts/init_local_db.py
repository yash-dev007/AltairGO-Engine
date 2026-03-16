import os
from backend.app import create_app
from backend.database import db
import backend.models

app = create_app()
with app.app_context():
    from sqlalchemy import text
    print("Enabling PostGIS extension...")
    try:
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        db.session.commit()
    except Exception as e:
        print(f"Warning: Could not enable postgis: {e}")

    print("Creating all tables...")
    db.create_all()
    print("Database tables created successfully.")
