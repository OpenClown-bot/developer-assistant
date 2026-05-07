"""Tests for developer_assistant.model_catalog.probe_omniroute.

Uses stdlib http.server as a stub. No real network, no real API keys.
"""

from __future__ import annotations

import http.server
import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.model_catalog import (
    ProbeResult,
    _probe_identifier,
)

_MAIN_MODEL = "accounts/fireworks/models/glm-5p1"
_ROLE = "executor"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _StubHandler(http.server.BaseHTTPRequestHandler):
    response_code: int = 200
    response_body: dict = {}
    sleep_seconds: float = 0.0

    def do_POST(self) -> None:
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        self.send_response(self.__class__.response_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps(self.__class__.response_body)
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args) -> None:
        pass


class _SuccessHandler(_StubHandler):
    response_code = 200
    response_body = {
        "model": _MAIN_MODEL,
        "choices": [{"message": {"content": "a"}}],
    }


class _AuthFailureHandler(_StubHandler):
    response_code = 401
    response_body = {"error": {"message": "unauthorized"}}


class _NotFoundHandler(_StubHandler):
    response_code = 404
    response_body = {"error": {"message": "model not found"}}


class _MismatchedModelHandler(_StubHandler):
    response_code = 200
    response_body = {
        "model": "different-model-id",
        "choices": [{"message": {"content": "a"}}],
    }


class _MalformedJsonHandler(_StubHandler):
    response_code = 200

    def do_POST(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"this is not json")


class _TimeoutHandler(_StubHandler):
    sleep_seconds = 5.0
    response_code = 200
    response_body = {"model": _MAIN_MODEL}


class TestProbeSuccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), _SuccessHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_success_returns_ok_true(self) -> None:
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.role, _ROLE)
        self.assertEqual(result.identifier, _MAIN_MODEL)
        self.assertIsNone(result.reason)
        self.assertIsNotNone(result.latency_ms)


class TestProbeAuthFailure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), _AuthFailureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_auth_failure_returns_reason(self) -> None:
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "auth_failure")


class TestProbeNotFound(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), _NotFoundHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_not_found_returns_not_resolved(self) -> None:
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "not_resolved")


class TestProbeMismatchedModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), _MismatchedModelHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_mismatched_model_returns_not_resolved(self) -> None:
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "not_resolved")


class TestProbeUnreachable(unittest.TestCase):
    def test_connection_refused_returns_unreachable(self) -> None:
        port = _find_free_port()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", port))
        sock.close()
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unreachable")


class TestProbeTimeout(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), _TimeoutHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_timeout_returns_reason_timeout(self) -> None:
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=0.5,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "timeout")


class TestProbeUnexpectedResponse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), _MalformedJsonHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_malformed_json_returns_unexpected_response(self) -> None:
        result = _probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unexpected_response")


if __name__ == "__main__":
    unittest.main()
