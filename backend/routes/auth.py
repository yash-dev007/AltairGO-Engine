import re
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
import structlog
from backend.database import db
from backend.extensions import limiter
from backend.models import User
from backend.request_validation import load_request_json
from backend.schemas import LoginSchema, RegisterSchema

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
log = structlog.get_logger(__name__)


@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    try:
        data, error = load_request_json(RegisterSchema())
        if error:
            return error

        email = data['email'].lower()
        if not re.match(r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,4}$", email):
            return jsonify({"error": "Invalid email format"}), 400

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
    data, error = load_request_json(LoginSchema())
    if error:
        return error

    email = data['email'].lower()
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({"error": "Invalid credentials"}), 401

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
