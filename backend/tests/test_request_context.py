import asyncio
import contextlib
import io
import json
import os
import sys
import unittest

os.environ.setdefault("JWT_SECRET", "test-secret-for-request-context-32bytes")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import httpx

from main import app


class RequestContextTests(unittest.TestCase):
    def test_request_id_header_and_log_are_emitted(self):
        out = io.StringIO()

        async def request_root():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/", headers={"X-Request-ID": "req-abc-123"})

        with contextlib.redirect_stdout(out):
            response = asyncio.run(request_root())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-request-id"), "req-abc-123")

        log_lines = [line for line in out.getvalue().splitlines() if line.strip()]
        request_log = json.loads(log_lines[-1])
        self.assertEqual(request_log["event"], "request_completed")
        self.assertEqual(request_log["request_id"], "req-abc-123")
        self.assertEqual(request_log["path"], "/")


if __name__ == "__main__":
    unittest.main()
