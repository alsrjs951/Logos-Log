import os
import sys
import unittest
import copy
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-for-auth-token-tests-32bytes")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from bson import ObjectId

from api.auth import (
    create_jwt_token,
    create_refresh_token,
    decode_refresh_token,
    hash_refresh_jti,
    issue_refresh_token,
    refresh_access_token,
    rotate_refresh_token,
)
from api.deps import get_current_user


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def insert_one(self, doc):
        stored = copy.deepcopy(doc)
        stored["_id"] = stored.get("_id") or ObjectId()
        self.docs.append(stored)
        return FakeInsertResult(stored["_id"])

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find_one_and_update(self, query, update, return_document=None):
        for doc in self.docs:
            if self._matches(doc, query):
                before = copy.deepcopy(doc)
                self._apply_update(doc, update)
                return before
        return None

    def update_one(self, query, update):
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)
                break

    def update_many(self, query, update):
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)

    def _matches(self, doc, query):
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$gt" in expected and not (actual > expected["$gt"]):
                    return False
                continue
            if actual != expected:
                return False
        return True

    def _apply_update(self, doc, update):
        for key, value in update.get("$set", {}).items():
            doc[key] = value


class FakeDB:
    def __init__(self, user_id, email):
        self.users = FakeCollection([{"_id": ObjectId(user_id), "email": email}])
        self.refresh_tokens = FakeCollection()


class FakeRequest:
    def __init__(self, headers=None, scheme="https"):
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}
        self.method = "POST"
        self.url = SimpleNamespace(scheme=scheme, path="/api/auth/refresh")


class AuthTokenTests(unittest.TestCase):
    def test_refresh_token_decodes_only_refresh_tokens(self):
        refresh = create_refresh_token("user-1", "user@example.com")
        payload = decode_refresh_token(refresh)

        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["email"], "user@example.com")
        self.assertEqual(payload["token_type"], "refresh")
        self.assertTrue(payload["jti"])
        self.assertTrue(payload["family_id"])

    def test_access_token_is_not_valid_refresh_token(self):
        access = create_jwt_token("user-1", "user@example.com")

        with self.assertRaises(HTTPException) as ctx:
            decode_refresh_token(access)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_refresh_endpoint_rejects_untrusted_origin_before_cookie_validation(self):
        request = FakeRequest({
            "origin": "https://evil.example.com",
            "host": "api.example.com",
        })
        response = SimpleNamespace()

        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "",
            "CSRF_REQUIRE_ORIGIN": "true",
        }, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(refresh_access_token(request, response, refresh_token=None))

        self.assertEqual(ctx.exception.status_code, 403)

    def test_refresh_token_is_not_valid_access_token(self):
        refresh = create_refresh_token("user-1", "user@example.com")

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {refresh}")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_refresh_session_rotation_rejects_reused_token(self):
        user_id = str(ObjectId())
        email = "user@example.com"
        db = FakeDB(user_id, email)

        refresh = issue_refresh_token(db, user_id, email)
        payload = decode_refresh_token(refresh)
        self.assertEqual(len(db.refresh_tokens.docs), 1)
        self.assertEqual(db.refresh_tokens.docs[0]["jti_hash"], hash_refresh_jti(payload["jti"]))
        self.assertNotEqual(db.refresh_tokens.docs[0]["jti_hash"], payload["jti"])

        rotated_refresh, rotated_email = rotate_refresh_token(db, payload)
        rotated_payload = decode_refresh_token(rotated_refresh)

        self.assertEqual(rotated_email, email)
        self.assertEqual(len(db.refresh_tokens.docs), 2)
        self.assertEqual(db.refresh_tokens.docs[0]["revoked_reason"], "rotated")
        self.assertIsNotNone(db.refresh_tokens.docs[0]["revoked_at"])
        self.assertNotEqual(payload["jti"], rotated_payload["jti"])
        self.assertEqual(payload["family_id"], rotated_payload["family_id"])

        with self.assertRaises(HTTPException) as ctx:
            rotate_refresh_token(db, payload)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(db.refresh_tokens.docs[1]["revoked_reason"], "reuse_detected")
        self.assertIsNotNone(db.refresh_tokens.docs[1]["revoked_at"])


if __name__ == "__main__":
    unittest.main()
