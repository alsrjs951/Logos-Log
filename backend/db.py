import os
import sys
import threading
import time
from pymongo import MongoClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

# Load environment variables
dotenv_paths = [
    os.path.join(os.path.dirname(__file__), '../.env'),
    os.path.join(os.path.dirname(__file__), '../../.env')
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

def get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

uri = os.getenv("MONGODB_URI")
if not uri:
    # Fallback to local or print warning
    print("Warning: MONGODB_URI not found in environment variables. DB connection might fail.", file=sys.stderr)
    uri = "mongodb://localhost:27017/logos_log"

try:
    # Setup MongoClient with connection pool settings
    client = MongoClient(
        uri,
        maxPoolSize=50,
        minPoolSize=5,
        serverSelectionTimeoutMS=get_int_env("MONGODB_SERVER_SELECTION_TIMEOUT_MS", 2000),
        connectTimeoutMS=get_int_env("MONGODB_CONNECT_TIMEOUT_MS", 2000),
        socketTimeoutMS=get_int_env("MONGODB_SOCKET_TIMEOUT_MS", 8000),
    )
    db = client.get_default_database("logos_log")
    print(f"Connected successfully to MongoDB: {db.name}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}", file=sys.stderr)
    client = None
    db = None

def ensure_indexes():
    global _index_thread_started
    if client is None or db is None:
        return

    try:
        client.admin.command("ping")
    except PyMongoError as e:
        print(f"Warning: MongoDB ping failed; skipping index creation for now: {e}", file=sys.stderr)
        _index_thread_started = False
        return

    try:
        db.users.create_index(
            [("email", ASCENDING)],
            name="users_email_unique",
            unique=True,
        )
    except PyMongoError as e:
        print(f"Warning: failed to create users email index: {e}", file=sys.stderr)
        try:
            db.users.create_index(
                [("email", ASCENDING)],
                name="users_email_lookup",
            )
        except PyMongoError as fallback_error:
            print(f"Warning: failed to create users email lookup index: {fallback_error}", file=sys.stderr)

    secondary_indexes = [
        (db.journals, [("user_id", ASCENDING), ("created_at", DESCENDING)], "journals_user_created_at"),
        (db.value_cards, [("user_id", ASCENDING), ("created_at", DESCENDING)], "value_cards_user_created_at"),
        (db.chat_messages, [("journal_id", ASCENDING), ("created_at", ASCENDING)], "chat_messages_journal_created_at"),
        (db.chat_messages, [("user_id", ASCENDING)], "chat_messages_user"),
    ]

    for collection, keys, name in secondary_indexes:
        try:
            collection.create_index(keys, name=name)
        except PyMongoError as e:
            print(f"Warning: failed to create {name} index: {e}", file=sys.stderr)

_index_thread_started = False
_last_index_attempt = 0.0
_INDEX_RETRY_SECONDS = 60

def start_index_ensure_thread():
    global _index_thread_started, _last_index_attempt
    if db is None or _index_thread_started:
        return
    now = time.monotonic()
    if now - _last_index_attempt < _INDEX_RETRY_SECONDS:
        return
    _index_thread_started = True
    _last_index_attempt = now
    thread = threading.Thread(target=ensure_indexes, name="mongodb-indexes", daemon=True)
    thread.start()

start_index_ensure_thread()


def get_db():
    if db is None:
        raise ValueError("Database connection is not initialized.")
    start_index_ensure_thread()
    return db
