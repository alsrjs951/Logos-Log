import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException

from services.origin_security import enforce_trusted_origin, is_trusted_origin


class FakeRequest:
    def __init__(self, headers=None, scheme="https"):
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}
        self.method = "POST"
        self.url = SimpleNamespace(scheme=scheme, path="/api/auth/refresh")


class OriginSecurityTests(unittest.TestCase):
    def test_allows_configured_cors_origin(self):
        request = FakeRequest({
            "origin": "https://app.example.com",
            "host": "api.example.com",
        })
        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "",
            "CSRF_REQUIRE_ORIGIN": "true",
        }, clear=False):
            enforce_trusted_origin(request)

    def test_allows_extra_csrf_trusted_origin(self):
        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "https://admin.example.com",
        }, clear=False):
            self.assertTrue(is_trusted_origin("https://admin.example.com"))

    def test_rejects_untrusted_origin(self):
        request = FakeRequest({
            "origin": "https://evil.example.com",
            "host": "api.example.com",
        })
        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "",
            "CSRF_REQUIRE_ORIGIN": "true",
        }, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                enforce_trusted_origin(request)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_uses_referer_when_origin_is_missing(self):
        request = FakeRequest({
            "referer": "https://app.example.com/settings",
            "host": "api.example.com",
        })
        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "",
            "CSRF_REQUIRE_ORIGIN": "true",
        }, clear=False):
            enforce_trusted_origin(request)

    def test_allows_same_origin_request(self):
        request = FakeRequest({
            "origin": "https://api.example.com",
            "host": "api.example.com",
        })
        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "",
            "CSRF_REQUIRE_ORIGIN": "true",
        }, clear=False):
            enforce_trusted_origin(request)

    def test_rejects_missing_origin_by_default(self):
        request = FakeRequest({"host": "api.example.com"})
        with patch.dict(os.environ, {"CSRF_REQUIRE_ORIGIN": "true"}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                enforce_trusted_origin(request)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_can_allow_missing_origin_for_non_browser_clients(self):
        request = FakeRequest({"host": "api.example.com"})
        with patch.dict(os.environ, {"CSRF_REQUIRE_ORIGIN": "false"}, clear=False):
            enforce_trusted_origin(request)


if __name__ == "__main__":
    unittest.main()
