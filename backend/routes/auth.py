from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
import redis
import structlog
from backend.database import db
from backend.extensions import limiter
from backend.models import User
from backend.request_validation import load_request_json
from backend.schemas import LoginSchema, RegisterSchema

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
log = structlog.get_logger(__name__)

_LOCKOUT_MAX_ATTEMPTS = 5
_LOCKOUT_WINDOW = 900  # 15 minutes
_redis_pool = {}  # keyed by REDIS_URL → ConnectionPool


def _get_redis():
    try:
        url = current_app.config.get("REDIS_URL", "")
        if not url:
            return None
        if url not in _redis_pool:
            _redis_pool[url] = redis.ConnectionPool.from_url(url)
        return redis.Redis(connection_pool=_redis_pool[url], decode_responses=True)
    except Exception:
        return None


def _check_lockout(email: str) -> bool:
    """Returns True if the account is currently locked out."""
    r = _get_redis()
    if not r:
        return False
    try:
        count = r.get(f"login:fail:{email}")
        return count is not None and int(count) >= _LOCKOUT_MAX_ATTEMPTS
    except Exception:
        return False


def _record_failed_login(email: str):
    r = _get_redis()
    if not r:
        return
    try:
        key = f"login:fail:{email}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, _LOCKOUT_WINDOW)
        pipe.execute()
    except Exception:
        pass


def _clear_failed_logins(email: str):
    r = _get_redis()
    if not r:
        return
    try:
        r.delete(f"login:fail:{email}")
    except Exception:
        pass


@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    try:
        data, error = load_request_json(RegisterSchema())
        if error:
            return error

        # Email format is already validated by RegisterSchema (fields.Email).
        # A second manual regex here would be redundant and breaks modern TLDs > 4 chars.
        email = data['email'].lower()

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "User already exists"}), 409

        hashed_pw = generate_password_hash(data['password'])
        new_user = User(name=data['name'], email=email, password_hash=hashed_pw)

        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=str(new_user.id))
        refresh_token = create_refresh_token(identity=str(new_user.id))

        return jsonify({
            "message": "User created",
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": new_user.id,
                "name": new_user.name,
                "email": new_user.email
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        log.error("registration_failed", error=str(e))
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    try:
        data, error = load_request_json(LoginSchema())
        if error:
            return error

        email = data['email'].lower()

        if _check_lockout(email):
            log.warning("login_locked_out", email=email)
            return jsonify({
                "error": "Too many failed attempts. Account locked for 15 minutes."
            }), 429

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, data['password']):
            _record_failed_login(email)
            log.warning("login_failed", email=email)
            return jsonify({"error": "Invalid credentials"}), 401

        _clear_failed_logins(email)
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        return jsonify({
            "message": "Login successful",
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        log.exception("login_failed_unexpected", error=str(e))
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/refresh', methods=['POST'])
@limiter.limit("30 per minute")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    new_token = create_access_token(identity=user_id)
    return jsonify({"token": new_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 401
        
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email
    }), 200
