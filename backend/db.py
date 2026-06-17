import os
import threading
import time
from pymongo import MongoClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from services.intention_loop import STATUS_OPEN
from services.observability import log_event

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
    log_event("mongodb_uri_missing", level="warning")
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
    log_event("mongodb_connected", database=db.name)
except Exception as e:
    log_event("mongodb_connection_error", level="error", error_type=type(e).__name__)
    client = None
    db = None

def ensure_indexes():
    global _index_thread_started
    if client is None or db is None:
        return

    try:
        client.admin.command("ping")
    except PyMongoError as e:
        log_event("mongodb_ping_failed", level="warning", error_type=type(e).__name__)
        _index_thread_started = False
        return

    try:
        db.users.create_index(
            [("email", ASCENDING)],
            name="users_email_unique",
            unique=True,
        )
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="users_email_unique", error_type=type(e).__name__)
        try:
            db.users.create_index(
                [("email", ASCENDING)],
                name="users_email_lookup",
            )
        except PyMongoError as fallback_error:
            log_event("mongodb_index_create_failed", level="warning", index_name="users_email_lookup", error_type=type(fallback_error).__name__)

    ensure_secondary_indexes(db)

    try:
        ensure_intentions_open_hash_unique_index(db)
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="intentions_open_hash_unique", error_type=type(e).__name__)

    try:
        db.value_experiment_recommendations.create_index(
            [("user_id", ASCENDING), ("fingerprint", ASCENDING), ("prompt_version", ASCENDING)],
            name="value_experiment_recommendations_cache",
            unique=True,
        )
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="value_experiment_recommendations_cache", error_type=type(e).__name__)

    try:
        db.refresh_tokens.create_index(
            [("jti_hash", ASCENDING)],
            name="refresh_tokens_jti_hash_unique",
            unique=True,
        )
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="refresh_tokens_jti_hash_unique", error_type=type(e).__name__)

    try:
        db.refresh_tokens.create_index(
            [("expires_at", ASCENDING)],
            name="refresh_tokens_expires_at_ttl",
            expireAfterSeconds=0,
        )
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="refresh_tokens_expires_at_ttl", error_type=type(e).__name__)

    try:
        db.refresh_tokens.create_index(
            [("user_id", ASCENDING), ("revoked_at", ASCENDING), ("expires_at", DESCENDING)],
            name="refresh_tokens_user_active_lookup",
        )
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="refresh_tokens_user_active_lookup", error_type=type(e).__name__)

    try:
        db.refresh_tokens.create_index(
            [("user_id", ASCENDING), ("family_id", ASCENDING), ("revoked_at", ASCENDING)],
            name="refresh_tokens_family_revoke_lookup",
        )
    except PyMongoError as e:
        log_event("mongodb_index_create_failed", level="warning", index_name="refresh_tokens_family_revoke_lookup", error_type=type(e).__name__)

_index_thread_started = False
_last_index_attempt = 0.0
_INDEX_RETRY_SECONDS = 60


def ensure_intentions_open_hash_unique_index(database):
    database.intentions.create_index(
        [("user_id", ASCENDING), ("card_id", ASCENDING), ("intention_hash", ASCENDING)],
        name="intentions_open_hash_unique",
        unique=True,
        partialFilterExpression={
            "status": STATUS_OPEN,
            "intention_hash": {"$type": "string"},
        },
    )


def secondary_index_specs(database):
    return [
        (database.journals, [("user_id", ASCENDING), ("created_at", DESCENDING)], "journals_user_created_at"),
        (database.value_cards, [("user_id", ASCENDING), ("created_at", DESCENDING)], "value_cards_user_created_at"),
        (database.chat_messages, [("user_id", ASCENDING), ("journal_id", ASCENDING), ("created_at", ASCENDING)], "chat_messages_user_journal_created_at"),
        (database.chat_messages, [("journal_id", ASCENDING), ("created_at", ASCENDING)], "chat_messages_journal_created_at"),
        (database.chat_messages, [("user_id", ASCENDING)], "chat_messages_user"),
        (database.intentions, [("user_id", ASCENDING), ("status", ASCENDING), ("created_at", ASCENDING)], "intentions_user_status_created_at"),
        (database.intentions, [("user_id", ASCENDING), ("card_id", ASCENDING), ("status", ASCENDING), ("intention_hash", ASCENDING)], "intentions_user_card_status_hash"),
    ]


def ensure_secondary_indexes(database):
    for collection, keys, name in secondary_index_specs(database):
        try:
            collection.create_index(keys, name=name)
        except PyMongoError as e:
            log_event("mongodb_index_create_failed", level="warning", index_name=name, error_type=type(e).__name__)


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
