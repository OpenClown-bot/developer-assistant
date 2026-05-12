"""TKT-041 v0.1.1 AUDIT-003 — /health smoke-extended-fields tests.

Asserts the HealthEndpoint /health response:
  * exposes loaded_skills / prompt_path / prompt_sha256 when the smoke-mode
    marker is present (AC-2 + AC-4 i)
  * exposes the same fields when ?internal=1 is set (Executor-chosen
    gating mechanism per § 8 risk bullet 1)
  * leaves the fields null when neither gate is active (production posture)
  * computes prompt_sha256 fresh on each request (post-boot tamper detection,
    AC-4 i closing sentence)
"""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.observability.health_endpoint import HealthEndpoint
from developer_assistant.smoke_inject import ROLE_LOADOUT_FALLBACK


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http_get(host: str, port: int, path: str) -> tuple[int, dict]:
    conn = http.client.HTTPConnection(host, port, timeout=3)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        status = resp.status
    finally:
        conn.close()
    try:
        return status, json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return status, {"raw": raw}


class TestHealthExtendedFieldsAsyncRoundtrip(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = self._tmp.name
        prompts_dir = os.path.join(self.repo_root, "docs", "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        self.prompt_path_abs = os.path.join(prompts_dir, "planner.md")
        Path(self.prompt_path_abs).write_text(
            "# Planner role prompt (smoke test fixture)\n", encoding="utf-8", newline="",
        )
        self.expected_sha = hashlib.sha256(
            Path(self.prompt_path_abs).read_bytes(),
        ).hexdigest()
        self.marker = os.path.join(self._tmp.name, "smoke-mode.flag")
        self.db = os.path.join(self._tmp.name, "operational.db")
        Path(self.db).touch()
        self.port = _free_port()

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def _start_endpoint(self) -> HealthEndpoint:
        ep = HealthEndpoint(
            "business-planner", self.port, self.db,
            repo_root=self.repo_root, marker_file_path=self.marker,
        )
        await ep.start()
        return ep

    async def test_marker_absent_extended_fields_null(self):
        ep = await self._start_endpoint()
        try:
            await asyncio.sleep(0.05)
            status, body = await asyncio.get_event_loop().run_in_executor(
                None, _http_get, "127.0.0.1", self.port, "/health",
            )
        finally:
            await ep.stop()
        self.assertEqual(status, 200)
        self.assertIsNone(body["loaded_skills"])
        self.assertIsNone(body["prompt_path"])
        self.assertIsNone(body["prompt_sha256"])

    async def test_marker_present_exposes_fields(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        ep = await self._start_endpoint()
        try:
            await asyncio.sleep(0.05)
            status, body = await asyncio.get_event_loop().run_in_executor(
                None, _http_get, "127.0.0.1", self.port, "/health",
            )
        finally:
            await ep.stop()
        self.assertEqual(status, 200)
        self.assertEqual(body["prompt_path"], "docs/prompts/planner.md")
        self.assertEqual(body["prompt_sha256"], self.expected_sha)
        self.assertIsInstance(body["loaded_skills"], list)
        self.assertEqual(
            set(body["loaded_skills"]),
            set(ROLE_LOADOUT_FALLBACK["planner"]),
        )

    async def test_internal_query_param_exposes_fields_without_marker(self):
        ep = await self._start_endpoint()
        try:
            await asyncio.sleep(0.05)
            status, body = await asyncio.get_event_loop().run_in_executor(
                None, _http_get, "127.0.0.1", self.port, "/health?internal=1",
            )
        finally:
            await ep.stop()
        self.assertEqual(status, 200)
        self.assertEqual(body["prompt_sha256"], self.expected_sha)
        self.assertEqual(body["prompt_path"], "docs/prompts/planner.md")

    async def test_prompt_sha256_recomputed_post_tamper(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        ep = await self._start_endpoint()
        try:
            await asyncio.sleep(0.05)
            _, body1 = await asyncio.get_event_loop().run_in_executor(
                None, _http_get, "127.0.0.1", self.port, "/health",
            )
            # Tamper the prompt file after boot.
            Path(self.prompt_path_abs).write_text("# Tampered\n", encoding="utf-8", newline="")
            new_sha = hashlib.sha256(b"# Tampered\n").hexdigest()
            _, body2 = await asyncio.get_event_loop().run_in_executor(
                None, _http_get, "127.0.0.1", self.port, "/health",
            )
        finally:
            await ep.stop()
        self.assertEqual(body1["prompt_sha256"], self.expected_sha)
        self.assertEqual(body2["prompt_sha256"], new_sha)
        self.assertNotEqual(body1["prompt_sha256"], body2["prompt_sha256"])


if __name__ == "__main__":
    unittest.main()
