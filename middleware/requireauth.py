from functools import wraps
from flask import request, jsonify
import jwt
from config import JWT_SECRET



token_blacklist = set()

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401

        token = auth.split(" ", 1)[1].strip()
        if token in token_blacklist:
            return jsonify({"error": "Token has been revoked"}), 401

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except Exception:
            return jsonify({"error": "Invalid token"}), 401

        request.user = payload
        return f(*args, **kwargs)
    


    return wrapper