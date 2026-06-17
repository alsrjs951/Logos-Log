import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.rate_limit import FixedWindowRateLimiter


class MutableClock:
    def __init__(self, value=0.0):
        self.value = value

    def __call__(self):
        return self.value


class RateLimitTests(unittest.TestCase):
    def test_allows_until_limit_then_blocks(self):
        clock = MutableClock()
        limiter = FixedWindowRateLimiter(now_func=clock)

        self.assertTrue(limiter.check("auth:127.0.0.1", limit=2, window_seconds=60).allowed)
        self.assertTrue(limiter.check("auth:127.0.0.1", limit=2, window_seconds=60).allowed)
        blocked = limiter.check("auth:127.0.0.1", limit=2, window_seconds=60)

        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.count, 3)
        self.assertEqual(blocked.retry_after, 60)

    def test_resets_after_window(self):
        clock = MutableClock()
        limiter = FixedWindowRateLimiter(now_func=clock)

        self.assertTrue(limiter.check("llm:user", limit=1, window_seconds=10).allowed)
        self.assertFalse(limiter.check("llm:user", limit=1, window_seconds=10).allowed)

        clock.value = 11
        reset = limiter.check("llm:user", limit=1, window_seconds=10)

        self.assertTrue(reset.allowed)
        self.assertEqual(reset.count, 1)


if __name__ == "__main__":
    unittest.main()
