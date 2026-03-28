import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

_redis_url = os.getenv("REDIS_URL")
_testing = os.getenv("TESTING") == "true"
_dev_eager = os.getenv("DEV_EAGER", "false").lower() in ("1", "true", "yes")

if not _redis_url:
    if _testing or _dev_eager:
        _redis_url = "memory://"
    else:
        raise RuntimeError(
            "REDIS_URL env var is required.\n"
            "Set it in backend/.env — e.g. redis://localhost:6379/0"
        )

# In dev-eager mode (local dev without Redis), fall back to in-memory limiter.
# In production with Redis, use Redis for distributed rate limiting.
_storage_uri = "memory://" if (_testing or _dev_eager) else _redis_url

limiter = Limiter(
    key_func=get_remote_address,
    # Conservative global default — individual endpoints may override with stricter limits.
    default_limits=["200 per minute"],
    storage_uri=_storage_uri,
    # Do NOT silently swallow rate-limit errors — fail closed so limits stay enforced.
    swallow_errors=False,
)
