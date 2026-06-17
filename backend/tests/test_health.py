import asyncio
import os
import sys
import unittest

os.environ.setdefault("JWT_SECRET", "test-secret-for-health-32bytes")
os.environ.setdefault("APP_VERSION", "test-version")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import httpx

from main import app


class HealthEndpointTests(unittest.TestCase):
    def test_health_check_is_dependency_free_liveness_probe(self):
        async def request_health():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/health")

        response = asyncio.run(request_health())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok",
            "service": "logos_log",
            "version": "test-version",
        })


if __name__ == "__main__":
    unittest.main()
