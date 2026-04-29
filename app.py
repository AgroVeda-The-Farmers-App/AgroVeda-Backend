from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import random
import string
from datetime import datetime, timedelta, timezone  
from functools import wraps
from bson.objectid import ObjectId
from db import users, chat_sessions, chat_messages
from config import JWT_SECRET
from flask_mail import Mail, Message
#from routes.forgot_password import forgot_password_bp
#from routes.admin import admin_bp


app = Flask(__name__)
app.config['SECRET_KEY'] = JWT_SECRET  # Add this for session management
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'arch007chowdhury@gmail.com'
app.config['MAIL_PASSWORD'] = 'hpez cqal jivr jakw'  
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEFAULT_SENDER'] = 'arch007chowdhury@gmail.com'

mail = Mail(app)

CORS(
    app,
    supports_credentials=True,
    origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)




# app.register_blueprint(forgot_password_bp, url_prefix='/api/auth') # FOTGOT PASSWORD

# app.register_blueprint(admin_bp, url_prefix='/api/admin') # ADMIN





# Token blacklist (in production, use Redis or database)
token_blacklist = set()

# -------------------- JWT Helper --------------------
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401

        token = auth.split(" ", 1)[1].strip()
        
        # Check if token is blacklisted
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

# -------------------- SIGNUP --------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}
    full_name = data.get("full_name", "").strip()
    address = data.get("address", "").strip()
    gender = data.get("gender", "").strip()
    marital_status = data.get("marital_status", "")
    profession = data.get("profession", "").strip()
    dob = data.get("dob", "")
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not full_name or not email or not password:
        return jsonify({"error": "Full name, email and password are required"}), 400

    # Check duplicate email
    if users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409

    password_hash = generate_password_hash(password)

    user_data = {
        "full_name": full_name,
        "address": address,
        "gender": gender,
        "marital_status": marital_status,
        "profession": profession,
        "dob": dob,
        "email": email,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc)  # ✅ CHANGED: Was datetime.datetime.utcnow()
    }
    
    result = users.insert_one(user_data)
    
    # Generate token for automatic login after signup
    payload = {
        "id": str(result.inserted_id),
        "email": email,
        "full_name": full_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=6),  # ✅ CHANGED: Was datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    return jsonify({
        "message": "Signup successful!",
        "token": token,
        "user": {
            "id": str(result.inserted_id),
            "full_name": full_name,
            "email": email,
            "address": address,
            "gender": gender,
            "marital_status": marital_status,
            "profession": profession,
            "dob": dob
        }
    }), 201

# -------------------- LOGIN --------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = users.find_one({"email": email})
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    payload = {
        "id": str(user["_id"]),
        "email": email,
        "full_name": user["full_name"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=6),  # ✅ CHANGED: Was datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    } 

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256") 

    try:
        msg = Message(
            "Welcome Back!",
            sender="arch007chowdhury@gmail.com",
            recipients=[email],
            body="We are happy that you came back. We are always here for you."
        )
        mail.send(msg)
        print("Mail sent successfully..")
    except Exception as e:
        print(f"Failed to send email: {e}")   

    return jsonify({
        "message": "Login successful!",
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "full_name": user["full_name"],
            "email": user["email"],
            "address": user.get("address", ""),
            "gender": user.get("gender", ""),
            "marital_status": user.get("marital_status", ""),
            "profession": user.get("profession", ""),
            "dob": user.get("dob", "")
        }
    }), 200



