import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
dotenv_paths = [
    os.path.join(os.path.dirname(__file__), '../.env'),
    os.path.join(os.path.dirname(__file__), '../../.env')
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

uri = os.getenv("MONGODB_URI")
if not uri:
    # Fallback to local or print warning
    print("Warning: MONGODB_URI not found in environment variables. DB connection might fail.", file=sys.stderr)
    uri = "mongodb://localhost:27017/logos_log"

try:
    # Setup MongoClient with connection pool settings
    client = MongoClient(uri, maxPoolSize=50, minPoolSize=5)
    db = client.get_default_database("logos_log")
    print(f"Connected successfully to MongoDB: {db.name}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}", file=sys.stderr)
    client = None
    db = None

def get_db():
    if db is None:
        raise ValueError("Database connection is not initialized.")
    return db
