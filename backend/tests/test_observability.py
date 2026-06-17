import contextlib
import io
import json
import os
import pathlib
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.observability import (
    log_event,
    normalize_request_id,
    reset_request_id,
    safe_hash,
    sanitized_log_fields,
    set_request_id,
)


class ObservabilityTests(unittest.TestCase):
    def test_log_event_includes_request_id(self):
        token = set_request_id("req-test-1")
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                log_event("unit_test_event", answer=42)
        finally:
            reset_request_id(token)

        payload = json.loads(out.getvalue())
        self.assertEqual(payload["event"], "unit_test_event")
        self.assertEqual(payload["request_id"], "req-test-1")
        self.assertEqual(payload["answer"], 42)

    def test_normalize_request_id_sanitizes_or_generates(self):
        self.assertEqual(normalize_request_id(" abc/def "), "abcdef")
        self.assertNotEqual(normalize_request_id(""), "")

    def test_safe_hash_is_stable_and_short(self):
        self.assertEqual(safe_hash("same"), safe_hash("same"))
        self.assertEqual(len(safe_hash("same")), 12)

    def test_sensitive_log_fields_are_hashed_centrally(self):
        fields = sanitized_log_fields({
            "user_id": "user-123",
            "email": "person@example.com",
            "journal_id": "journal-123",
            "intention_id": "intention-123",
            "card_id": "card-123",
            "document_id": "public-doc-123",
        })

        self.assertNotIn("user_id", fields)
        self.assertNotIn("email", fields)
        self.assertNotIn("journal_id", fields)
        self.assertNotIn("intention_id", fields)
        self.assertNotIn("card_id", fields)
        self.assertEqual(fields["user_hash"], safe_hash("user-123"))
        self.assertEqual(fields["email_hash"], safe_hash("person@example.com"))
        self.assertEqual(fields["journal_hash"], safe_hash("journal-123"))
        self.assertEqual(fields["intention_id_hash"], safe_hash("intention-123"))
        self.assertEqual(fields["card_hash"], safe_hash("card-123"))
        self.assertEqual(fields["document_id"], "public-doc-123")

    def test_log_event_drops_raw_sensitive_fields(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            log_event("sensitive_unit_test_event", user_id="user-123", journal_id="journal-123")

        payload = json.loads(out.getvalue())
        self.assertNotIn("user_id", payload)
        self.assertNotIn("journal_id", payload)
        self.assertEqual(payload["user_hash"], safe_hash("user-123"))
        self.assertEqual(payload["journal_hash"], safe_hash("journal-123"))

    def test_sensitive_ids_are_not_logged_raw(self):
        backend_dir = pathlib.Path(BACKEND_DIR)
        checked_files = [
            *backend_dir.joinpath("api").glob("*.py"),
            *backend_dir.joinpath("services").glob("*.py"),
        ]
        source = "\n".join(path.read_text() for path in checked_files)

        self.assertNotIn("journal_id=journal_id", source)
        self.assertNotIn("intention_id=intention_id", source)


if __name__ == "__main__":
    unittest.main()
