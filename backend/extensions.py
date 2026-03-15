import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

_redis_url = os.getenv("REDIS_URL")
if not _redis_url:
    if os.getenv("TESTING") == "true" or os.getenv("FLASK_ENV") == "testing":
        _redis_url = "memory://"
    else:
        raise RuntimeError(
            "REDIS_URL env var is required.\n"
            "Set it in backend/.env — e.g. redis://localhost:6379/0"
        )

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=_redis_url,
    swallow_errors=True,
)
