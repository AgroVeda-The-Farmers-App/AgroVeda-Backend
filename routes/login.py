from flask import Flask, request, jsonify
from werkzeug.security import check_password_hash
from db import users
from app import app
from flask_mail import Mail,Message

mail = Mail(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'arch007chowdhury@gmail.com'
app.config['MAIL_PASSWORD'] = 'lzgb ioft ksit npxr'
app.config['MAIL_USE_TSL'] = True
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEFAULT_SENDER'] = 'arch007chowdhury@gmail.com'

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = users.find_one({"email": email})

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401


    msg = Message(
       "Welcome Back My friend",
       sender="arch007chowdhury@gmail.com",
       recipients=[email],
       body="We are happay that you came back. We are always here for you."
    )
    mail.send(msg)
    print("Mail sent successfully..")

    return jsonify({
        "message": "Login successful!",
        "user": {
            "id": str(user["_id"]),
            "full_name": user["full_name"],
            "email": user["email"]
        }
    }), 200

    