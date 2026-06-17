import asyncio
import datetime
import hashlib
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-for-intention-events-32bytes")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from api.intentions import (  # noqa: E402
    _action_source,
    _clean_action_source,
    _experiment_event_fields,
    _find_duplicate_open_intention,
    _hmac_intention_text_hash,
    _intention_text_hash,
    _intention_age_days,
    _legacy_jwt_intention_text_hash,
    _normalize_intention_text,
    create_intention,
    dismiss_intention,
    reflect_intention,
    serialize_intention,
)
from bson import ObjectId  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from models.intentions import IntentionCreate, IntentionReflect  # noqa: E402
from pymongo.errors import DuplicateKeyError  # noqa: E402


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


class FakeUpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeIntentionsCollection:
    def __init__(self, docs, duplicate_on_insert=False, hide_docs_until_insert=False, update_miss_once=False):
        self.docs = docs
        self.duplicate_on_insert = duplicate_on_insert
        self.hide_docs_until_insert = hide_docs_until_insert
        self.update_miss_once = update_miss_once
        self.insert_attempts = 0
        self.updated = []

    def find_one(self, query):
        if self.hide_docs_until_insert and self.insert_attempts == 0:
            return None
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    def find(self, query):
        if self.hide_docs_until_insert and self.insert_attempts == 0:
            return []
        return [
            doc for doc in self.docs
            if doc.get("user_id") == query.get("user_id")
            and doc.get("card_id") == query.get("card_id")
            and doc.get("status") == query.get("status")
            and ("intention_hash" not in doc or doc.get("intention_hash") is None)
        ]

    def update_one(self, query, update):
        self.updated.append((query, update))
        if self.update_miss_once:
            self.update_miss_once = False
            return FakeUpdateResult(0)
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    def _matches(self, doc, query):
        for key, expected in query.items():
            if doc.get(key) != expected:
                return False
        return True

    def insert_one(self, data):
        self.insert_attempts += 1
        if self.duplicate_on_insert:
            raise DuplicateKeyError("duplicate intention")
        data = dict(data)
        data["_id"] = ObjectId()
        self.docs.append(data)

        class Result:
            inserted_id = data["_id"]

        return Result()


class FakeValueCardsCollection:
    def __init__(self, card):
        self.card = card

    def find_one(self, query):
        if (
            self.card
            and str(query.get("_id")) == str(self.card.get("_id"))
            and query.get("user_id") == self.card.get("user_id")
        ):
            return self.card
        return None

    def find(self, query, projection=None):
        if not self.card:
            return []
        ids = query.get("_id", {}).get("$in", [])
        if self.card.get("_id") in ids and query.get("user_id") == self.card.get("user_id"):
            return [self.card]
        return []


class FakeDb:
    def __init__(self, docs, card=None, duplicate_on_insert=False, hide_docs_until_insert=False, update_miss_once=False):
        self.intentions = FakeIntentionsCollection(
            docs,
            duplicate_on_insert=duplicate_on_insert,
            hide_docs_until_insert=hide_docs_until_insert,
            update_miss_once=update_miss_once,
        )
        self.value_cards = FakeValueCardsCollection(card)


class IntentionEventTests(unittest.TestCase):
    def test_action_source_is_normalized_and_bounded(self):
        self.assertEqual(_clean_action_source("meaning-network"), "meaning_network")
        self.assertEqual(_clean_action_source("Dashboard Action Loop"), "dashboard_action_loop")
        self.assertEqual(_clean_action_source(None), "unknown")
        self.assertEqual(_clean_action_source("unexpected<script>"), "other")

    def test_action_source_prefers_explicit_body_value(self):
        request = FakeRequest({"x-logos-action-source": "meaning_network"})

        self.assertEqual(_action_source(request, "value_card_modal"), "value_card_modal")

    def test_intention_text_hash_normalizes_common_duplicates(self):
        self.assertEqual(
            _normalize_intention_text("  이번 주에   작은 선택 하나  "),
            "이번 주에 작은 선택 하나",
        )
        self.assertEqual(
            _intention_text_hash("이번 주에 작은 선택 하나"),
            _intention_text_hash("  이번 주에   작은 선택 하나  "),
        )
        self.assertNotEqual(
            _intention_text_hash("이번 주에 작은 선택 하나"),
            hashlib.sha256("이번 주에 작은 선택 하나".encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(
            _intention_text_hash("이번 주에 작은 선택 하나"),
            _intention_text_hash("이번 주에 감사 표현 하나"),
        )

    def test_intention_text_hash_uses_dedicated_secret_when_configured(self):
        intention_text = "이번 주에 작은 선택 하나"

        with patch.dict(os.environ, {"INTENTION_HASH_SECRET": "dedicated-secret-a"}):
            dedicated_hash = _intention_text_hash(intention_text)

        with patch.dict(os.environ, {"INTENTION_HASH_SECRET": "dedicated-secret-b"}):
            other_dedicated_hash = _intention_text_hash(intention_text)

        self.assertEqual(
            dedicated_hash,
            _hmac_intention_text_hash(intention_text, "dedicated-secret-a"),
        )
        self.assertNotEqual(dedicated_hash, other_dedicated_hash)
        self.assertNotEqual(dedicated_hash, _legacy_jwt_intention_text_hash(intention_text))

    def test_duplicate_lookup_backfills_legacy_open_intention_hash(self):
        intention_text = "이번 주에 작은 선택 하나"
        intention_hash = _intention_text_hash(intention_text)
        db = FakeDb([
            {
                "_id": "legacy-1",
                "user_id": "user-123",
                "card_id": "card-123",
                "status": "open",
                "intention": "  이번 주에   작은 선택 하나  ",
            }
        ])

        duplicate = _find_duplicate_open_intention(
            db,
            "user-123",
            "card-123",
            intention_hash,
            intention_text,
        )

        self.assertEqual(duplicate["_id"], "legacy-1")
        self.assertEqual(duplicate["intention_hash"], intention_hash)
        self.assertEqual(db.intentions.updated[0][0], {"_id": "legacy-1", "user_id": "user-123"})
        self.assertEqual(db.intentions.updated[0][1]["$set"]["intention_hash"], intention_hash)

    def test_duplicate_lookup_backfills_legacy_sha_hash(self):
        intention_text = "이번 주에 작은 선택 하나"
        new_hash = _intention_text_hash(intention_text)
        legacy_hash = hashlib.sha256(intention_text.encode("utf-8")).hexdigest()
        db = FakeDb([
            {
                "_id": "legacy-sha-1",
                "user_id": "user-123",
                "card_id": "card-123",
                "status": "open",
                "intention": intention_text,
                "intention_hash": legacy_hash,
            }
        ])

        duplicate = _find_duplicate_open_intention(
            db,
            "user-123",
            "card-123",
            new_hash,
            intention_text,
        )

        self.assertEqual(duplicate["_id"], "legacy-sha-1")
        self.assertEqual(duplicate["intention_hash"], new_hash)
        self.assertEqual(db.intentions.updated[0][0], {"_id": "legacy-sha-1", "user_id": "user-123"})
        self.assertEqual(db.intentions.updated[0][1]["$set"]["intention_hash"], new_hash)

    def test_duplicate_lookup_backfills_legacy_jwt_hmac_hash(self):
        intention_text = "이번 주에 작은 선택 하나"
        with patch.dict(os.environ, {"INTENTION_HASH_SECRET": "new-intention-secret"}):
            new_hash = _intention_text_hash(intention_text)
        legacy_hash = _legacy_jwt_intention_text_hash(intention_text)
        self.assertNotEqual(new_hash, legacy_hash)
        db = FakeDb([
            {
                "_id": "legacy-jwt-hmac-1",
                "user_id": "user-123",
                "card_id": "card-123",
                "status": "open",
                "intention": intention_text,
                "intention_hash": legacy_hash,
            }
        ])

        duplicate = _find_duplicate_open_intention(
            db,
            "user-123",
            "card-123",
            new_hash,
            intention_text,
        )

        self.assertEqual(duplicate["_id"], "legacy-jwt-hmac-1")
        self.assertEqual(duplicate["intention_hash"], new_hash)
        self.assertEqual(db.intentions.updated[0][0], {"_id": "legacy-jwt-hmac-1", "user_id": "user-123"})
        self.assertEqual(db.intentions.updated[0][1]["$set"]["intention_hash"], new_hash)

    def test_create_intention_reuses_duplicate_after_unique_index_race(self):
        card_id = str(ObjectId())
        user_id = "user-123"
        intention_text = "이번 주에 작은 선택 하나"
        intention_hash = _intention_text_hash(intention_text)
        existing = {
            "_id": ObjectId(),
            "user_id": user_id,
            "card_id": card_id,
            "status": "open",
            "intention": intention_text,
            "intention_hash": intention_hash,
            "created_at": "2026-06-10T12:00:00+00:00",
        }
        db = FakeDb(
            [existing],
            card={
                "_id": ObjectId(card_id),
                "user_id": user_id,
                "keyword": "자율성",
                "canonical_value": "자기주도",
            },
            duplicate_on_insert=True,
            hide_docs_until_insert=True,
        )

        with (
            patch("api.intentions.get_db", return_value=db),
            patch("api.intentions.encrypt", side_effect=lambda value: value),
        ):
            response = asyncio.run(create_intention(
                IntentionCreate(card_id=card_id, intention=intention_text, source="dashboard_action_loop"),
                FakeRequest(),
                {"id": user_id},
            ))

        self.assertEqual(db.intentions.insert_attempts, 1)
        self.assertEqual(response["id"], str(existing["_id"]))
        self.assertTrue(response["was_duplicate"])

    def test_dismiss_intention_records_dismissed_at(self):
        intention_id = ObjectId()
        card_id = ObjectId()
        user_id = "user-123"
        db = FakeDb(
            [{
                "_id": intention_id,
                "user_id": user_id,
                "card_id": str(card_id),
                "status": "open",
                "intention": "작은 선택 하나",
                "created_at": "2026-06-10T12:00:00+00:00",
            }],
            card={
                "_id": card_id,
                "user_id": user_id,
                "keyword": "자율성",
                "canonical_value": "자기주도",
            },
        )

        with (
            patch("api.intentions.get_db", return_value=db),
            patch("api.intentions._utc_now_iso", return_value="2026-06-14T12:00:00+00:00"),
        ):
            response = asyncio.run(dismiss_intention(
                str(intention_id),
                FakeRequest({"x-logos-action-source": "dashboard_action_loop"}),
                {"id": user_id},
            ))

        self.assertEqual(response["status"], "dismissed")
        self.assertEqual(response["dismissed_at"], "2026-06-14T12:00:00+00:00")
        self.assertEqual(db.intentions.updated[0][0], {
            "_id": intention_id,
            "user_id": user_id,
            "status": "open",
        })
        self.assertEqual(db.intentions.updated[0][1]["$set"]["dismissed_at"], "2026-06-14T12:00:00+00:00")

    def test_reflect_intention_rejects_already_closed_intention(self):
        intention_id = ObjectId()
        db = FakeDb([{
            "_id": intention_id,
            "user_id": "user-123",
            "card_id": str(ObjectId()),
            "status": "dismissed",
            "intention": "작은 선택 하나",
            "created_at": "2026-06-10T12:00:00+00:00",
            "dismissed_at": "2026-06-14T12:00:00+00:00",
        }])

        with patch("api.intentions.get_db", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(reflect_intention(
                    str(intention_id),
                    IntentionReflect(outcome="해봤더니 부담이 줄었습니다.", helpfulness=4),
                    FakeRequest(),
                    {"id": "user-123"},
                ))

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(db.intentions.updated, [])

    def test_reflect_intention_update_is_scoped_to_user(self):
        intention_id = ObjectId()
        card_id = ObjectId()
        user_id = "user-123"
        db = FakeDb(
            [{
                "_id": intention_id,
                "user_id": user_id,
                "card_id": str(card_id),
                "status": "open",
                "intention": "작은 선택 하나",
                "created_at": "2026-06-10T12:00:00+00:00",
            }],
            card={
                "_id": card_id,
                "user_id": user_id,
                "keyword": "자율성",
                "canonical_value": "자기주도",
            },
        )

        with (
            patch("api.intentions.get_db", return_value=db),
            patch("api.intentions.encrypt", side_effect=lambda value: value),
        ):
            response = asyncio.run(reflect_intention(
                str(intention_id),
                IntentionReflect(outcome="해봤더니 부담이 줄었습니다.", helpfulness=4),
                FakeRequest({"x-logos-action-source": "dashboard_action_loop"}),
                {"id": user_id},
            ))

        self.assertEqual(response["status"], "reflected")
        self.assertEqual(db.intentions.updated[0][0], {
            "_id": intention_id,
            "user_id": user_id,
            "status": "open",
        })

    def test_reflect_intention_rejects_atomic_status_race(self):
        intention_id = ObjectId()
        db = FakeDb(
            [{
                "_id": intention_id,
                "user_id": "user-123",
                "card_id": str(ObjectId()),
                "status": "open",
                "intention": "작은 선택 하나",
                "created_at": "2026-06-10T12:00:00+00:00",
            }],
            update_miss_once=True,
        )

        with patch("api.intentions.get_db", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(reflect_intention(
                    str(intention_id),
                    IntentionReflect(outcome="해봤더니 부담이 줄었습니다.", helpfulness=4),
                    FakeRequest(),
                    {"id": "user-123"},
                ))

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(db.intentions.updated[0][0], {
            "_id": intention_id,
            "user_id": "user-123",
            "status": "open",
        })
        self.assertEqual(db.intentions.docs[0]["status"], "open")

    def test_dismiss_intention_rejects_already_closed_intention(self):
        intention_id = ObjectId()
        db = FakeDb([{
            "_id": intention_id,
            "user_id": "user-123",
            "card_id": str(ObjectId()),
            "status": "reflected",
            "intention": "작은 선택 하나",
            "created_at": "2026-06-10T12:00:00+00:00",
            "outcome": "해봤더니 좋았습니다.",
            "outcome_logged_at": "2026-06-14T12:00:00+00:00",
        }])

        with patch("api.intentions.get_db", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dismiss_intention(
                    str(intention_id),
                    FakeRequest(),
                    {"id": "user-123"},
                ))

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(db.intentions.updated, [])

    def test_dismiss_intention_rejects_atomic_status_race(self):
        intention_id = ObjectId()
        db = FakeDb(
            [{
                "_id": intention_id,
                "user_id": "user-123",
                "card_id": str(ObjectId()),
                "status": "open",
                "intention": "작은 선택 하나",
                "created_at": "2026-06-10T12:00:00+00:00",
            }],
            update_miss_once=True,
        )

        with patch("api.intentions.get_db", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dismiss_intention(
                    str(intention_id),
                    FakeRequest(),
                    {"id": "user-123"},
                ))

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(db.intentions.updated[0][0], {
            "_id": intention_id,
            "user_id": "user-123",
            "status": "open",
        })
        self.assertEqual(db.intentions.docs[0]["status"], "open")

    def test_experiment_event_fields_hash_sensitive_identifiers(self):
        fields = _experiment_event_fields(
            "user-123",
            {"_id": "intention-123", "card_id": "card-123"},
            {"canonical_value": "자기주도"},
            "dashboard_action_loop",
        )

        self.assertNotEqual(fields["user_hash"], "user-123")
        self.assertNotEqual(fields["intention_id_hash"], "intention-123")
        self.assertNotEqual(fields["card_hash"], "card-123")
        self.assertEqual(fields["card_value"], "자기주도")
        self.assertEqual(fields["source"], "dashboard_action_loop")

    def test_intention_age_days_is_best_effort(self):
        created_at = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=3, hours=1)).isoformat()

        self.assertGreaterEqual(_intention_age_days({"created_at": created_at}), 3)
        self.assertIsNone(_intention_age_days({"created_at": "not-a-date"}))

    def test_serialized_intention_includes_review_timing(self):
        created_at = "2026-06-10T12:00:00+00:00"
        serialized = serialize_intention({
            "_id": "intention-123",
            "card_id": "card-123",
            "intention": "작은 선택 하나 고르기",
            "status": "open",
            "created_at": created_at,
        })

        self.assertEqual(serialized["review_available_at"], "2026-06-13T12:00:00+00:00")
        self.assertIn("is_due", serialized)
        self.assertFalse(serialized["was_duplicate"])

    def test_serialized_intention_marks_duplicate_reuse(self):
        serialized = serialize_intention({
            "_id": "intention-123",
            "card_id": "card-123",
            "intention": "작은 선택 하나 고르기",
            "status": "open",
            "created_at": "2026-06-10T12:00:00+00:00",
            "_was_duplicate": True,
        })

        self.assertTrue(serialized["was_duplicate"])

    def test_serialized_intention_includes_dismissed_at(self):
        serialized = serialize_intention({
            "_id": "intention-123",
            "card_id": "card-123",
            "intention": "작은 선택 하나 고르기",
            "status": "dismissed",
            "created_at": "2026-06-10T12:00:00+00:00",
            "dismissed_at": "2026-06-14T12:00:00+00:00",
        })

        self.assertEqual(serialized["dismissed_at"], "2026-06-14T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
