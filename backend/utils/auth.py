from functools import wraps
from datetime import datetime
import hmac
from flask import current_app, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt

import structlog
log = structlog.get_logger(__name__)

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Check for Admin Key Header (for simple tool access)
        admin_key = request.headers.get("X-Admin-Key")
        if admin_key and hmac.compare_digest(admin_key, current_app.config.get("ADMIN_ACCESS_KEY", "")):
            return f(*args, **kwargs)
            
        # 2. Check for JWT
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") != "admin":
                log.warning("auth.admin_role_missing", claims=claims)
                return jsonify({"error": "Admin role required"}), 403
        except Exception as e:
            log.warning("auth.jwt_verification_failed", error=str(e))
            return jsonify({"error": "Unauthorized"}), 401
            
        # 3. If auth passed, call the function (do NOT catch its exceptions here)
        return f(*args, **kwargs)

    return decorated
