import datetime
import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.intention_loop import (  # noqa: E402
    DUE_AFTER_DAYS,
    STATUS_DISMISSED,
    STATUS_OPEN,
    STATUS_REFLECTED,
    compute_intention_stats,
    due_intentions,
    is_intention_due,
    review_available_at,
)


class IntentionLoopTests(unittest.TestCase):
    def test_due_intentions_returns_old_open_items_only(self):
        now = datetime.datetime(2026, 6, 14, 12, 0, 0)

        def made(days_ago, status=STATUS_OPEN):
            return {
                "status": status,
                "created_at": (now - datetime.timedelta(days=days_ago)).isoformat(),
            }

        due = due_intentions([
            made(7),
            made(DUE_AFTER_DAYS),
            made(1),
            made(7, STATUS_REFLECTED),
            made(7, STATUS_DISMISSED),
        ], now=now)

        self.assertEqual(len(due), 2)
        self.assertTrue(all(item["status"] == STATUS_OPEN for item in due))
        self.assertLessEqual(due[0]["created_at"], due[1]["created_at"])

    def test_review_available_at_and_due_flag_share_same_threshold(self):
        created_at = "2026-06-10T12:00:00+00:00"
        before_due = datetime.datetime(2026, 6, 13, 11, 59, tzinfo=datetime.UTC)
        after_due = datetime.datetime(2026, 6, 13, 12, 0, tzinfo=datetime.UTC)

        self.assertEqual(review_available_at(created_at), "2026-06-13T12:00:00+00:00")
        self.assertFalse(is_intention_due({"status": STATUS_OPEN, "created_at": created_at}, now=before_due))
        self.assertTrue(is_intention_due({"status": STATUS_OPEN, "created_at": created_at}, now=after_due))
        self.assertFalse(is_intention_due({"status": STATUS_REFLECTED, "created_at": created_at}, now=after_due))

    def test_stats_exclude_dismissed_from_follow_through_denominator(self):
        now = datetime.datetime(2026, 6, 14, 12, 0, tzinfo=datetime.UTC)
        stats = compute_intention_stats([
            {
                "status": STATUS_REFLECTED,
                "helpfulness": 5,
                "created_at": "2026-06-01T12:00:00+00:00",
            },
            {
                "status": STATUS_REFLECTED,
                "helpfulness": 3,
                "created_at": "2026-06-02T12:00:00+00:00",
            },
            {
                "status": STATUS_OPEN,
                "created_at": "2026-06-10T12:00:00+00:00",
            },
            {
                "status": STATUS_OPEN,
                "created_at": "2026-06-13T12:00:00+00:00",
            },
            {
                "status": STATUS_DISMISSED,
                "created_at": "2026-06-01T12:00:00+00:00",
            },
        ], now=now)

        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["open"], 2)
        self.assertEqual(stats["reflected"], 2)
        self.assertEqual(stats["dismissed"], 1)
        self.assertEqual(stats["due_count"], 1)
        self.assertEqual(stats["next_review_available_at"], "2026-06-16T12:00:00+00:00")
        self.assertAlmostEqual(stats["follow_through_rate"], 1 / 2)
        self.assertEqual(stats["helpfulness_avg"], 4.0)
        self.assertEqual(stats["helpfulness_dist"][5], 1)
        self.assertEqual(stats["helpfulness_dist"][3], 1)

    def test_empty_stats_are_gentle(self):
        stats = compute_intention_stats([])

        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["due_count"], 0)
        self.assertIsNone(stats["next_review_available_at"])
        self.assertIsNone(stats["follow_through_rate"])
        self.assertIsNone(stats["helpfulness_avg"])


if __name__ == "__main__":
    unittest.main()
