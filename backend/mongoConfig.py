from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

load_dotenv("atlas-credentials.env")

uri = os.getenv("MONGO_URI")


client = MongoClient(uri,server_api=ServerApi("1"))

db = client.sl_db
user_collection = db["sl_users"]
occupancy_collection = db["sl_occupancy"]


