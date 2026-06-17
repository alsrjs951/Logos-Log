import asyncio
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-for-journal-access-32bytes")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from api.chat import get_chat_history_endpoint  # noqa: E402
from api.journals import delete_journal  # noqa: E402
from bson import ObjectId  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from services.rag_service import RAGService  # noqa: E402


class FakeDeleteResult:
    deleted_count = 1


class FakeJournalCollection:
    def __init__(self, docs):
        self.docs = docs
        self.find_queries = []
        self.delete_queries = []

    def find_one(self, query, projection=None):
        self.find_queries.append(query)
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    def delete_one(self, query):
        self.delete_queries.append(query)
        return FakeDeleteResult()


class FakeChatMessagesCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.delete_queries = []
        self.find_queries = []
        self.update_queries = []

    def delete_many(self, query):
        self.delete_queries.append(query)
        return FakeDeleteResult()

    def find(self, query):
        self.find_queries.append(query)
        return FakeCursor([
            doc for doc in self.docs
            if all(doc.get(key) == value for key, value in query.items())
        ])

    def update_one(self, query, update):
        self.update_queries.append((query, update))
        return FakeDeleteResult()


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_args):
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeDb:
    def __init__(self, journal_docs=None, chat_docs=None):
        self.journals = FakeJournalCollection(journal_docs or [])
        self.chat_messages = FakeChatMessagesCollection(chat_docs or [])


class FakeRagService:
    def __init__(self, history):
        self.history = history
        self.history_calls = []

    def get_chat_history(self, journal_id, user_id=None):
        self.history_calls.append((journal_id, user_id))
        return self.history

    async def _translate_and_summarize_paper(self, content):
        return {
            "content_ko": f"번역: {content}",
            "summary_ko": "요약",
        }


class JournalAccessTests(unittest.TestCase):
    def test_delete_journal_scopes_lookup_and_cascade_to_current_user(self):
        journal_id = ObjectId()
        db = FakeDb([
            {
                "_id": journal_id,
                "user_id": "user-123",
                "title": "일기",
            }
        ])

        with patch("api.journals.get_db", return_value=db):
            response = asyncio.run(delete_journal(str(journal_id), {"id": "user-123"}))

        self.assertEqual(response["status"], "success")
        self.assertEqual(db.journals.find_queries[0], {"_id": journal_id, "user_id": "user-123"})
        self.assertEqual(db.journals.delete_queries[0], {"_id": journal_id, "user_id": "user-123"})
        self.assertEqual(db.chat_messages.delete_queries[0], {
            "journal_id": str(journal_id),
            "user_id": "user-123",
        })

    def test_delete_journal_returns_404_without_deleting_other_users_journal(self):
        journal_id = ObjectId()
        db = FakeDb([
            {
                "_id": journal_id,
                "user_id": "other-user",
                "title": "다른 사용자 일기",
            }
        ])

        with patch("api.journals.get_db", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(delete_journal(str(journal_id), {"id": "user-123"}))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(db.journals.find_queries[0], {"_id": journal_id, "user_id": "user-123"})
        self.assertEqual(db.journals.delete_queries, [])
        self.assertEqual(db.chat_messages.delete_queries, [])

    def test_rag_chat_history_filters_by_user_when_available(self):
        db = FakeDb(chat_docs=[
            {
                "_id": ObjectId(),
                "journal_id": "journal-1",
                "user_id": "user-123",
                "role": "user",
                "content": "안녕하세요",
            },
            {
                "_id": ObjectId(),
                "journal_id": "journal-1",
                "user_id": "other-user",
                "role": "user",
                "content": "다른 사용자",
            },
        ])
        service = RAGService.__new__(RAGService)

        with patch("services.rag_service.get_db", return_value=db):
            history = service.get_chat_history("journal-1", user_id="user-123")

        self.assertEqual(db.chat_messages.find_queries[0], {
            "journal_id": "journal-1",
            "user_id": "user-123",
        })
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "안녕하세요")

    def test_chat_history_translation_cache_update_is_user_scoped(self):
        journal_id = ObjectId()
        message_id = ObjectId()
        db = FakeDb(
            journal_docs=[{"_id": journal_id, "user_id": "user-123"}],
            chat_docs=[],
        )
        rag_service = FakeRagService([
            {
                "_id": message_id,
                "journal_id": str(journal_id),
                "user_id": "user-123",
                "role": "assistant",
                "content": "답변",
                "sources": [{"content": "source text"}],
            }
        ])

        with (
            patch("api.chat.get_db", return_value=db),
            patch("api.chat.get_rag_service", return_value=rag_service),
        ):
            history = asyncio.run(get_chat_history_endpoint(str(journal_id), {"id": "user-123"}))

        self.assertEqual(rag_service.history_calls, [(str(journal_id), "user-123")])
        self.assertEqual(history[0]["sources"][0]["content_ko"], "번역: source text")
        self.assertEqual(db.chat_messages.update_queries[0][0], {
            "_id": message_id,
            "journal_id": str(journal_id),
            "user_id": "user-123",
        })


if __name__ == "__main__":
    unittest.main()
