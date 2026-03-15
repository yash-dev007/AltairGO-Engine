import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# ── Proper Flask-SQLAlchemy ───────────────────────────────────────────────────
db = SQLAlchemy()

# ── Standalone session factory for Celery tasks and scripts ──────────────────
# This is NOT the Flask-SQLAlchemy session. It creates independent sessions
# that can be used outside of Flask request context (Celery workers, CLI scripts).
_session_factory = None


def SessionLocal():
    """
    Create a new database session for use OUTSIDE Flask request context.
    Used by Celery tasks, background scripts, and CLI tools.
    Returns a new Session instance that the caller MUST close.
    """
    global _session_factory
    if _session_factory is None:
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            if os.environ.get("TESTING") == "true":
                database_url = "sqlite:///:memory:"
            else:
                raise RuntimeError("DATABASE_URL is not set")
        connect_args = (
            {"check_same_thread": False}
            if database_url.startswith("sqlite")
            else {}
        )
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args=connect_args,
        )
        _session_factory = scoped_session(sessionmaker(bind=engine))
    return _session_factory()


def configure_database(app, database_url: str):
    """Call this once from create_app() with the resolved URL."""
    if not database_url:
        _is_testing = (
            os.environ.get("TESTING") == "true"
            or os.environ.get("FLASK_ENV") == "testing"
            or app.config.get("TESTING")
        )
        if _is_testing:
            database_url = "sqlite:///:memory:"
        else:
            raise RuntimeError(
                "DATABASE_URL env var is required.\n"
                "Set it in backend/.env"
            )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {}
          if not database_url.startswith("sqlite")
          else {"check_same_thread": False}
    }
    db.init_app(app)

Base = db.Model  # All models inherit from db.Model

def init_db(app=None):
    """Test-only. Production uses: flask db upgrade."""
    if app:
        if not app.config.get("TESTING"):
            raise RuntimeError("init_db() is for tests only.")
        with app.app_context():
            import backend.models  # noqa: F401
            db.drop_all()
            db.create_all()
    else:
        # Called without app — assume we are inside an app context already
        import backend.models  # noqa: F401
        db.drop_all()
        db.create_all()
