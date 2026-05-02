from flask import Flask
from flask_cors import CORS
from flask_mail import Mail
from config import JWT_SECRET, MAIL_USERNAME, MAIL_PASSWORD


app = Flask(__name__)
app.config['SECRET_KEY'] = JWT_SECRET
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEFAULT_SENDER'] = MAIL_USERNAME

mail = Mail(app)

CORS(app,
    supports_credentials=True,
    origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# Register blueprints
from routes.auth import auth_bp
from routes.profile import profile_bp

app.register_blueprint(auth_bp, url_prefix="/api")
app.register_blueprint(profile_bp, url_prefix="/api")

if __name__ == "__main__":
    app.run(debug=True, port=5000)