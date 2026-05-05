from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone
import random
import os
import requests
from db import users

forgot_bp = Blueprint("forgot", __name__)

FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")

otp_store = {}


def send_sms_fast2sms(phone_no: str, otp: str) -> bool:
    """Send OTP via Fast2SMS Quick SMS (Bulk) route — no verification needed."""
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        payload = {
            "route":    "q",                        # ← Quick/Bulk route (works immediately)
            "message":  f"Your Agroveda OTP is {otp}. Valid for 10 minutes. Do not share.",
            "language": "english",
            "numbers":  phone_no,
        }
        headers = {
            "authorization": FAST2SMS_API_KEY,
            "Content-Type":  "application/json"
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        data = res.json()
        print(f"[Fast2SMS] Response: {data}")
        return data.get("return") == True
    except Exception as e:
        print(f"[Fast2SMS] Error: {e}")
        return False


# ── STEP 1: Send OTP ─────────────────────────────────────────────
@forgot_bp.route("/forgot-password/send-otp", methods=["POST"])
def send_otp():
    data     = request.json or {}
    phone_no = data.get("phone_no", "").strip()

    if not phone_no or not phone_no.isdigit() or len(phone_no) != 10:
        return jsonify({"error": "Enter a valid 10-digit phone number"}), 400

    user = users.find_one({"phone_no": phone_no})
    if not user:
        return jsonify({"error": "No account found with this phone number"}), 404

    # Rate limit — 60 sec between requests
    existing = otp_store.get(phone_no)
    if existing:
        sent_at = existing.get("sent_at", datetime.now(timezone.utc))
        diff = (datetime.now(timezone.utc) - sent_at).seconds
        if diff < 60:
            return jsonify({"error": f"Please wait {60 - diff} seconds before requesting again"}), 429

    otp = str(random.randint(100000, 999999))
    now = datetime.now(timezone.utc)

    otp_store[phone_no] = {
        "otp":      otp,
        "expires":  now + timedelta(minutes=10),
        "sent_at":  now,
        "verified": False,
    }

    success = send_sms_fast2sms(phone_no, otp)
    if not success:
        otp_store.pop(phone_no, None)
        return jsonify({"error": "Failed to send OTP. Please try again."}), 500

    return jsonify({"message": "OTP sent successfully"}), 200


# ── STEP 2: Verify OTP ───────────────────────────────────────────
@forgot_bp.route("/forgot-password/verify-otp", methods=["POST"])
def verify_otp():
    data     = request.json or {}
    phone_no = data.get("phone_no", "").strip()
    otp      = data.get("otp", "").strip()

    if not phone_no or not otp:
        return jsonify({"error": "Phone number and OTP are required"}), 400

    record = otp_store.get(phone_no)

    if not record:
        return jsonify({"error": "OTP not found. Please request a new one"}), 400

    if datetime.now(timezone.utc) > record["expires"]:
        otp_store.pop(phone_no, None)
        return jsonify({"error": "OTP has expired. Please request a new one"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Incorrect OTP. Please try again"}), 400

    otp_store[phone_no]["verified"] = True
    return jsonify({"message": "OTP verified successfully"}), 200


# ── STEP 3: Reset Password ───────────────────────────────────────
@forgot_bp.route("/forgot-password/reset", methods=["POST"])
def reset_password():
    data         = request.json or {}
    phone_no     = data.get("phone_no", "").strip()
    new_password = data.get("new_password", "")
    confirm      = data.get("confirm_password", "")

    if not phone_no or not new_password:
        return jsonify({"error": "Phone number and new password are required"}), 400

    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if new_password != confirm:
        return jsonify({"error": "Passwords do not match"}), 400

    record = otp_store.get(phone_no)
    if not record or not record.get("verified"):
        return jsonify({"error": "Please verify your OTP first"}), 403

    result = users.update_one(
        {"phone_no": phone_no},
        {"$set": {
            "password_hash": generate_password_hash(new_password),
            "updated_at":    datetime.now(timezone.utc),
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "User not found"}), 404

    otp_store.pop(phone_no, None)
    return jsonify({"message": "Password reset successful! Please log in."}), 200