from pymongo import MongoClient
from dotenv import load_dotenv
import os



load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "agroveda")


client = MongoClient(MONGO_URI)

db = client[DB_NAME]


# Collections
users = db["users"]
support_tickets = db["support_tickets"] 

def get_db():

    return db