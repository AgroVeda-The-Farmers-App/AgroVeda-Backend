from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from db import users
from bson.objectid import ObjectId

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json
    required = ["language","full_name","address","gender","dob","phone_no","email","password"]

    if not all(field in data and data[field] for field in required):
        return jsonify({"error": "All fields are required"}), 400

    # Check duplicate email
    if users.find_one({"email": data["email"]}):
        return jsonify({"error": "Email already registered"}), 409

    hashed = generate_password_hash(data["password"])

    new_user = {
        "language" : data["language"],
        "full_name": data["full_name"],
        "address": data["address"],
        "gender": data["gender"],
        "marital_status": data["marital_status"],
        "profession": data["profession"],
        "dob": data["dob"],
        "phone_no":data["phone_no"],
        "email": data["email"],
        "password_hash": hashed
    }

    users.insert_one(new_user)

    return jsonify({"message": "User registered successfully"}), 201