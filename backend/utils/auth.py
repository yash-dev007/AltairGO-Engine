from functools import wraps
import hmac
from flask import current_app, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt

import structlog
log = structlog.get_logger(__name__)

_ADMIN_KEY_MAX_ATTEMPTS = 10   # Failed attempts before lockout
_ADMIN_KEY_LOCKOUT_SEC = 900   # 15-minute lockout window


def _check_admin_key_lockout(ip: str) -> bool:
    """Returns True if this IP is currently locked out for bad admin key attempts."""
    try:
        import redis as _redis
        redis_url = current_app.config.get("REDIS_URL", "")
        if not redis_url:
            return False
        r = _redis.from_url(redis_url, decode_responses=True)
        key = f"admin_key_fail:{ip}"
        count = r.get(key)
        return count is not None and int(count) >= _ADMIN_KEY_MAX_ATTEMPTS
    except Exception:
        return False


def _record_admin_key_failure(ip: str) -> None:
    """Increment the failed admin key counter for this IP."""
    try:
        import redis as _redis
        redis_url = current_app.config.get("REDIS_URL", "")
        if not redis_url:
            return
        r = _redis.from_url(redis_url, decode_responses=True)
        key = f"admin_key_fail:{ip}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, _ADMIN_KEY_LOCKOUT_SEC)
        pipe.execute()
    except Exception:
        pass


def _clear_admin_key_failures(ip: str) -> None:
    """Reset failure counter on successful admin key auth."""
    try:
        import redis as _redis
        redis_url = current_app.config.get("REDIS_URL", "")
        if not redis_url:
            return
        r = _redis.from_url(redis_url, decode_responses=True)
        r.delete(f"admin_key_fail:{ip}")
    except Exception:
        pass


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr or "unknown"

        # 1. Check for Admin Key Header (for simple tool access)
        admin_key = request.headers.get("X-Admin-Key")
        if admin_key:
            if _check_admin_key_lockout(ip):
                log.warning("auth.admin_key_lockout", ip=ip)
                return jsonify({"error": "Too many failed attempts. Try again later."}), 429
            if hmac.compare_digest(admin_key, current_app.config.get("ADMIN_ACCESS_KEY", "")):
                _clear_admin_key_failures(ip)
                return f(*args, **kwargs)
            _record_admin_key_failure(ip)
            log.warning("auth.admin_key_invalid", ip=ip)
            return jsonify({"error": "Unauthorized"}), 401

        # 2. Check for JWT with admin role
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") != "admin":
                log.warning("auth.admin_role_missing")
                return jsonify({"error": "Admin role required"}), 403
        except Exception as e:
            log.warning("auth.jwt_verification_failed", error=str(e))
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated
