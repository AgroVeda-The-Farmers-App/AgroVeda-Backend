from flask import Blueprint, request, jsonify, current_app
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import jwt
from db import users
from config import JWT_SECRET
from middleware.requireauth import require_auth

auth_bp = Blueprint("auth", __name__)
token_blacklist = set()


# ── SIGNUP ──────────────────────────────────────────────────────
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data      = request.json or {}
    full_name = data.get("full_name", "").strip()
    phone_no  = data.get("phone_no", "").strip()
    password  = data.get("password", "")

    # Validate required fields
    if not full_name or not phone_no or not password:
        return jsonify({"error": "Full name, phone number and password are required"}), 400

    if len(phone_no) != 10 or not phone_no.isdigit():
        return jsonify({"error": "Enter a valid 10-digit phone number"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Duplicate check by phone number
    if users.find_one({"phone_no": phone_no}):
        return jsonify({"error": "User already registered with this phone number"}), 409

    user_data = {
        "language":       data.get("language", "en"),
        "full_name":      full_name,
        "phone_no":       phone_no,
        "dob":            data.get("dob", ""),
        "gender":         data.get("gender", ""),
        "address":        data.get("address", ""),
        "password_hash":  generate_password_hash(password),
        "is_admin":       False,
        "created_at":     datetime.now(timezone.utc),
    }

    result = users.insert_one(user_data)

    token = jwt.encode({
        "id":        str(result.inserted_id),
        "phone_no":  phone_no,
        "full_name": full_name,
        "exp":       datetime.now(timezone.utc) + timedelta(hours=6),
    }, JWT_SECRET, algorithm="HS256")

    return jsonify({
        "message": "Signup successful!",
        "token": token,
        "user": {
            "id":        str(result.inserted_id),
            "full_name": full_name,
            "phone_no":  phone_no,
        }
    }), 201


# ── LOGIN ───────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.json or {}
    phone_no = data.get("phone_no", "").strip()
    password = data.get("password", "")

    if not phone_no or not password:
        return jsonify({"error": "Phone number and password are required"}), 400

    user = users.find_one({"phone_no": phone_no})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "id":        str(user["_id"]),
        "phone_no":  phone_no,
        "full_name": user["full_name"],
        "is_admin":  user.get("is_admin", False),
        "exp":       datetime.now(timezone.utc) + timedelta(hours=6),
    }, JWT_SECRET, algorithm="HS256")

    return jsonify({
        "message": "Login successful!",
        "token": token,
        "user": {
            "id":        str(user["_id"]),
            "full_name": user["full_name"],
            "phone_no":  user["phone_no"],
            "is_admin":  user.get("is_admin", False),
        }
    }), 200


# ── LOGOUT ──────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    token = request.headers.get("Authorization", "").split(" ", 1)[1].strip()
    token_blacklist.add(token)
    return jsonify({"message": "Logged out successfully"}), 200