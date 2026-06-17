import os
import sys
import unittest

os.environ.setdefault("JWT_SECRET", "test-secret-for-db-indexes-32bytes")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from db import ensure_intentions_open_hash_unique_index, secondary_index_specs  # noqa: E402


class FakeCollection:
    def __init__(self):
        self.calls = []

    def create_index(self, keys, **kwargs):
        self.calls.append((keys, kwargs))


class FakeDatabase:
    def __init__(self):
        self.journals = FakeCollection()
        self.value_cards = FakeCollection()
        self.chat_messages = FakeCollection()
        self.intentions = FakeCollection()


class DbIndexTests(unittest.TestCase):
    def test_open_intention_hash_index_is_unique_and_partial(self):
        database = FakeDatabase()

        ensure_intentions_open_hash_unique_index(database)

        keys, options = database.intentions.calls[0]
        self.assertEqual(keys, [("user_id", 1), ("card_id", 1), ("intention_hash", 1)])
        self.assertEqual(options["name"], "intentions_open_hash_unique")
        self.assertTrue(options["unique"])
        self.assertEqual(options["partialFilterExpression"], {
            "status": "open",
            "intention_hash": {"$type": "string"},
        })

    def test_secondary_indexes_include_user_scoped_chat_history_lookup(self):
        database = FakeDatabase()

        specs = [
            (keys, name)
            for _collection, keys, name in secondary_index_specs(database)
        ]

        self.assertIn(
            (
                [("user_id", 1), ("journal_id", 1), ("created_at", 1)],
                "chat_messages_user_journal_created_at",
            ),
            specs,
        )


if __name__ == "__main__":
    unittest.main()
