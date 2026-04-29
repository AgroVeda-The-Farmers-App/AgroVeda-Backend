# delete_and_recreate_admin.py
from db import users
from werkzeug.security import generate_password_hash
from datetime import datetime

# Delete existing admin
users.delete_one({"email": "admin@agroveda.com"})
print("Deleted existing admin (if any)")

# creating admin manually
admin_data = {
    "full_name": "Admin",
    "email": "admin@agroveda.com",
    "password_hash": generate_password_hash("admin2025"),
    "address": "",
    "gender": "Other",
    "marital_status": "Single",
    "profession": "Administrator",
    "dob": "1990-01-01",
    "is_admin": True,
    "created_at": datetime.utcnow()
}

result = users.insert_one(admin_data)
print(f"Admin created successfully!")
print(f"Email: admin@agroveda.com")
print(f"Password: admin2025")
print(f"ID: {result.inserted_id}")