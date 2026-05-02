from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from db import users
from middleware.requireauth import require_auth




profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile", methods=["GET"])
@require_auth
def get_profile():
    user = users.find_one({"_id": ObjectId(request.user["id"])})
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "id":             str(user["_id"]),
        "full_name":      user["full_name"],
        "email":          user["email"],
        "language":       user.get("language", ""),
        "phone_no":       user.get("phone_no", ""),
        "address":        user.get("address", ""),
        "gender":         user.get("gender", ""),

        "profession":     user.get("profession", ""),
        "dob":            user.get("dob", ""),
        "is_admin":       user.get("is_admin", False),
    }), 200


@profile_bp.route("/profile", methods=["PUT"])
@require_auth
def update_profile():
    data    = request.json or {}
    allowed = ["full_name", "phone_no", "address", "gender", "profession", "dob", "language"]
    update  = {k: v for k, v in data.items() if k in allowed}

    if not update:
        return jsonify({"error": "No valid fields to update"}), 400

    users.update_one({"_id": ObjectId(request.user["id"])}, {"$set": update})
    return jsonify({"message": "Profile updated successfully"}), 200