# test_db.py — run this separately: python test_db.py
from db import client

try:
    client.admin.command('ping')
    print("MongoDB connected!")
except Exception as e:
    print(f" Failed: {e}")