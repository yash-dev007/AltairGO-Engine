import os
from backend.app import create_app
from backend.database import engine, Base
import backend.models

app = create_app()
with app.app_context():
    from sqlalchemy import text
    print("Enabling PostGIS extension...")
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()
    except Exception as e:
        print(f"Warning: Could not enable postgis: {e}")

    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")
