from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "mindspace")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users = db["users"]
chat_sessions = db["chat_sessions"]
chat_messages = db["chat_messages"]

def get_db():
    return db