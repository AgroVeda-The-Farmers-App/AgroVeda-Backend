from flask import Blueprint, request, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import jwt
from db import users
from config import JWT_SECRET
from middleware.requireauth import require_auth
from app import mail


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["POST"])


def signup():

    data = request.json or {}
    full_name = data.get("full_name", "").strip()
    email     = data.get("email", "").strip().lower()
    password  = data.get("password", "")

    if not full_name or not email or not password:
        return jsonify({"error": "Full name, email and password are required"}), 400

    if users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409

    user_data = {
        "language":       data.get("language", "en"),
        "full_name":      full_name,
        "phone_no":       data.get("phone_no", ""),
        "address":        data.get("address", ""),
        "gender":         data.get("gender", ""),
        "marital_status": data.get("marital_status", ""),
        "profession":     data.get("profession", ""),
        "dob":            data.get("dob", ""),
        "email":          email,
        "password_hash":  generate_password_hash(password),
        "is_admin":       False,
        "created_at":     datetime.now(timezone.utc),
    }
    result = users.insert_one(user_data)

    token = jwt.encode({
        "id": str(result.inserted_id),
        "email": email,
        "full_name": full_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=6),
    }, JWT_SECRET, algorithm="HS256")

    return jsonify({
        "message": "Signup successful!",
        "token": token,
        "user": {
            "id": str(result.inserted_id),
            "full_name": full_name,
            "email": email,
        }
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.json or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = users.find_one({"email": email})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "id": str(user["_id"]),
        "email": email,
        "full_name": user["full_name"],
        "is_admin": user.get("is_admin", False),
        "exp": datetime.now(timezone.utc) + timedelta(hours=6),
    }, JWT_SECRET, algorithm="HS256")

    try:
        mail.send(Message(
            subject="Welcome Back to Agroveda!",
            recipients=[email],
            body=f"Hello {user['full_name']},\n\nGlad you're back!\n\n— Team Agroveda"
        ))
    except Exception as e:
        print(f"[Mail] {e}")

    return jsonify({
        "message": "Login successful!",
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "full_name": user["full_name"],
            "email": user["email"],
            "is_admin": user.get("is_admin", False),
        }
    }), 200


token_blacklist = set()

@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    token = request.headers.get("Authorization", "").split(" ", 1)[1].strip()
    token_blacklist.add(token)
    return jsonify({"message": "Logged out successfully"}), 200