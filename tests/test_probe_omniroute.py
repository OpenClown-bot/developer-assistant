"""Tests for developer_assistant.model_catalog.probe_identifier and probe_omniroute.

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
    probe_identifier,
    probe_omniroute,
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

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len else ""
        try:
            req_data = json.loads(post_body)
            requested_model = req_data.get("model", _MAIN_MODEL)
        except (json.JSONDecodeError, KeyError):
            requested_model = _MAIN_MODEL
        resp_body = json.dumps({
            "model": requested_model,
            "choices": [{"message": {"content": "a"}}],
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(resp_body.encode("utf-8"))


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
    sleep_seconds = 1.0
    response_code = 200
    response_body = {"model": _MAIN_MODEL}


def _start_server(handler_class: type) -> tuple[http.server.HTTPServer, int, threading.Thread]:
    port = _find_free_port()
    server = http.server.HTTPServer(("127.0.0.1", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


def _stop_server(server: http.server.HTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5.0)
    time.sleep(0.05)


class TestProbeSuccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.port, cls.thread = _start_server(_SuccessHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_success_returns_ok_true(self) -> None:
        result = probe_identifier(
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
        cls.server, cls.port, cls.thread = _start_server(_AuthFailureHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_auth_failure_returns_reason(self) -> None:
        result = probe_identifier(
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
        cls.server, cls.port, cls.thread = _start_server(_NotFoundHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_not_found_returns_not_resolved(self) -> None:
        result = probe_identifier(
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
        cls.server, cls.port, cls.thread = _start_server(_MismatchedModelHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_mismatched_model_returns_not_resolved(self) -> None:
        result = probe_identifier(
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
        result = probe_identifier(
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
        cls.server, cls.port, cls.thread = _start_server(_TimeoutHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_timeout_returns_reason_timeout(self) -> None:
        result = probe_identifier(
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
        cls.server, cls.port, cls.thread = _start_server(_MalformedJsonHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_malformed_json_returns_unexpected_response(self) -> None:
        result = probe_identifier(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            _MAIN_MODEL,
            timeout_seconds=5.0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unexpected_response")


class TestProbeOmnirouteReturnShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.port, cls.thread = _start_server(_SuccessHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def test_non_exhaustive_returns_single_element_list(self) -> None:
        results = probe_omniroute(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            timeout_seconds=5.0,
            exhaustive=False,
        )
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].identifier, _MAIN_MODEL)

    def test_exhaustive_returns_main_plus_fallbacks(self) -> None:
        results = probe_omniroute(
            "http://127.0.0.1:{p}".format(p=self.port),
            _ROLE,
            timeout_seconds=5.0,
            exhaustive=True,
        )
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].identifier, _MAIN_MODEL)
        for r in results:
            self.assertTrue(r.ok)


if __name__ == "__main__":
    unittest.main()
