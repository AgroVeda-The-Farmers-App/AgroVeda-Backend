from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta, timezone
from bson.objectid import ObjectId
import jwt
from db import users
from config import JWT_SECRET
from middleware.requireauth import require_auth
from functools import wraps
from db import support_tickets




admin_bp = Blueprint("admin", __name__)

# ── Admin-only decorator ─────────────────────────────────────────
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        if not payload.get("is_admin"):
            return jsonify({"error": "Admin access required"}), 403
        request.user = payload
        return f(*args, **kwargs)
    return wrapper


# ── ADMIN LOGIN ──────────────────────────────────────────────────
@admin_bp.route("/admin/login", methods=["POST"])
def admin_login():
    data     = request.json or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    
    ADMIN_EMAIL = "admin@agroveda.com"
    ADMIN_PASSWORD = "admin@12345"

    
    if email != ADMIN_EMAIL or password != ADMIN_PASSWORD:
        return jsonify({"error": "Invalid admin credentials"}), 401

    token = jwt.encode({
        "id": "admin",
        "email": email,
        "full_name": "Agroveda Admin",
        "is_admin": True,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }, JWT_SECRET, algorithm="HS256")

    return jsonify({
        "message": "Admin login successful",
        "token": token,
        "admin": {
            "id": "admin",
            "full_name": "Agroveda Admin",
            "email": "admin@agroveda.com"
        }
    }), 200


# ── STATS OVERVIEW ───────────────────────────────────────────────
@admin_bp.route("/admin/stats", methods=["GET"])
@require_admin
def get_stats():
    now   = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week  = today - timedelta(days=7)
    month = today - timedelta(days=30)

    total       = users.count_documents({"is_admin": {"$ne": True}})
    today_count = users.count_documents({"is_admin": {"$ne": True}, "created_at": {"$gte": today}})
    week_count  = users.count_documents({"is_admin": {"$ne": True}, "created_at": {"$gte": week}})
    month_count = users.count_documents({"is_admin": {"$ne": True}, "created_at": {"$gte": month}})

    return jsonify({
        "total":       total,
        "today":       today_count,
        "this_week":   week_count,
        "this_month":  month_count,
    }), 200


# ── USERS BY STATE ───────────────────────────────────────────────
@admin_bp.route("/admin/users-by-state", methods=["GET"])
@require_admin
def users_by_state():
    pipeline = [
        {"$match": {"is_admin": {"$ne": True}, "address": {"$ne": ""}}},
        {"$group": {"_id": "$address", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 15}
    ]
    result = list(users.aggregate(pipeline))
    return jsonify([{"state": r["_id"], "count": r["count"]} for r in result if r["_id"]]), 200


# ── USERS BY PROFESSION ──────────────────────────────────────────
@admin_bp.route("/admin/users-by-profession", methods=["GET"])
@require_admin
def users_by_profession():
    pipeline = [
        {"$match": {"is_admin": {"$ne": True}}},
        {"$group": {"_id": "$profession", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    result = list(users.aggregate(pipeline))
    return jsonify([{"profession": r["_id"] or "Not specified", "count": r["count"]} for r in result]), 200


# ── USERS BY GENDER ──────────────────────────────────────────────
@admin_bp.route("/admin/users-by-gender", methods=["GET"])
@require_admin
def users_by_gender():
    pipeline = [
        {"$match": {"is_admin": {"$ne": True}}},
        {"$group": {"_id": "$gender", "count": {"$sum": 1}}}
    ]
    result = list(users.aggregate(pipeline))
    return jsonify([{"gender": r["_id"] or "Not specified", "count": r["count"]} for r in result]), 200


# ── USERS BY LANGUAGE ────────────────────────────────────────────
@admin_bp.route("/admin/users-by-language", methods=["GET"])
@require_admin
def users_by_language():
    pipeline = [
        {"$match": {"is_admin": {"$ne": True}}},
        {"$group": {"_id": "$language", "count": {"$sum": 1}}}
    ]
    result = list(users.aggregate(pipeline))
    lang_map = {"en": "English", "bn": "Bengali"}
    return jsonify([{
        "language": lang_map.get(r["_id"], r["_id"] or "Unknown"),
        "count": r["count"]
    } for r in result]), 200


# ── SIGNUPS OVER TIME (last 30 days) ─────────────────────────────
@admin_bp.route("/admin/signups-over-time", methods=["GET"])
@require_admin
def signups_over_time():
    pipeline = [
        {"$match": {
            "is_admin": {"$ne": True},
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}
        }},
        {"$group": {
            "_id": {
                "year":  {"$year":  "$created_at"},
                "month": {"$month": "$created_at"},
                "day":   {"$dayOfMonth": "$created_at"},
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
    ]
    result = list(users.aggregate(pipeline))
    data = []
    for r in result:
        d = r["_id"]
        date_str = f"{d['year']}-{str(d['month']).zfill(2)}-{str(d['day']).zfill(2)}"
        data.append({"date": date_str, "count": r["count"]})
    return jsonify(data), 200


# ── ALL USERS LIST ───────────────────────────────────────────────
@admin_bp.route("/admin/users", methods=["GET"])
@require_admin
def get_all_users():
    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    search   = request.args.get("search", "").strip()

    query = {"is_admin": {"$ne": True}}
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"phone_no":  {"$regex": search, "$options": "i"}},
            {"address":   {"$regex": search, "$options": "i"}},
        ]

    total = users.count_documents(query)
    docs  = list(
        users.find(query, {"password_hash": 0})
             .sort("created_at", -1)
             .skip((page - 1) * per_page)
             .limit(per_page)
    )

    user_list = []
    for u in docs:
        user_list.append({
            "id":             str(u["_id"]),
            "full_name":      u.get("full_name", ""),
            "phone_no":       u.get("phone_no", ""),
            "address":        u.get("address", ""),
            "gender":         u.get("gender", ""),
            "profession":     u.get("profession", ""),
            "language":       u.get("language", "en"),
            "dob":            u.get("dob", ""),
            "created_at":     str(u.get("created_at", ""))[:10],
        })

    return jsonify({
        "users":      user_list,
        "total":      total,
        "page":       page,
        "per_page":   per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }), 200


# ── DELETE USER ──────────────────────────────────────────────────
@admin_bp.route("/admin/users/<user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    result = users.delete_one({"_id": ObjectId(user_id), "is_admin": {"$ne": True}})
    if result.deleted_count == 0:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"message": "User deleted successfully"}), 200




# ==========================================
# CREATE SUPPORT TICKET
# ==========================================
@admin_bp.route("/support-tickets", methods=["POST"])
@require_auth
def create_support_ticket():
    data = request.json or {}

    issue_key   = data.get("issue_key")
    issue_label = data.get("issue_label")
    bot_reply   = data.get("bot_reply")

    if not issue_key or not issue_label:
        return jsonify({"error": "Missing issue details"}), 400

    # logged-in user
    user = users.find_one({"_id": ObjectId(request.user["id"])})

    ticket = {
        "user_id": str(user["_id"]),
        "user_name": user.get("full_name"),
        "phone": user.get("phone_no"),
        "issue_key": issue_key,
        "issue_label": issue_label,
        "bot_reply": bot_reply,
        "status": "open",
        "created_at": datetime.now().strftime("%d %b %Y, %I:%M %p")
    }

    result = support_tickets.insert_one(ticket)

    return jsonify({
        "message": "Support ticket created",
        "ticket_id": str(result.inserted_id)
    }), 201



# ==========================================
# GET ALL SUPPORT TICKETS
# ==========================================
@admin_bp.route("/admin/support-tickets", methods=["GET"])
@require_auth
def get_support_tickets():
    tickets = []

    for ticket in support_tickets.find().sort("_id", -1):
        tickets.append({
            "id": str(ticket["_id"]),
            "user_name": ticket.get("user_name"),
            "phone": ticket.get("phone"),
            "issue_key": ticket.get("issue_key"),
            "issue_label": ticket.get("issue_label"),
            "bot_reply": ticket.get("bot_reply"),
            "status": ticket.get("status", "open"),
            "created_at": ticket.get("created_at")
        })

    return jsonify(tickets), 200


# ==========================================
# UPDATE SUPPORT TICKET STATUS
# ==========================================
@admin_bp.route("/admin/support-tickets/<ticket_id>", methods=["PATCH"])
@require_auth
def update_support_ticket(ticket_id):
    data = request.json or {}

    status = data.get("status")

    if status not in ["open", "resolved"]:
        return jsonify({"error": "Invalid status"}), 400

    support_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {"status": status}}
    )

    return jsonify({
        "message": "Ticket updated successfully"
    }), 200