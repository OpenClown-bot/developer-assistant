"""Tests for developer_assistant.founder_identity.

Uses stdlib unittest and in-memory sqlite. No real tokens, PATs,
production hostnames, or bash subprocesses.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant import state_store
from developer_assistant.founder_identity import (
    bind_founder_identity,
    list_founder_bindings,
    lookup_founder_by_upstream_identity,
    revoke_founder_binding,
)


class TestBindFounderIdentity(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_insert_returns_id(self) -> None:
        binding_id = bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
            display_name="Founder",
        )
        self.assertIsInstance(binding_id, int)
        self.assertGreater(binding_id, 0)

    def test_idempotent_no_duplicate(self) -> None:
        id1 = bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        id2 = bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        self.assertEqual(id1, id2)
        bindings = list_founder_bindings(self.conn)
        self.assertEqual(len(bindings), 1)

    def test_different_adapter_allows_rebind(self) -> None:
        id1 = bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        id2 = bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="openclaw",
            upstream_user_id="oc-user-001",
        )
        self.assertNotEqual(id1, id2)
        bindings = list_founder_bindings(self.conn)
        self.assertEqual(len(bindings), 2)

    def test_display_name_optional(self) -> None:
        bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u999999",
        )
        founder_id = lookup_founder_by_upstream_identity(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u999999",
        )
        self.assertIsNotNone(founder_id)
        self.assertEqual(founder_id, "founder-001")


class TestLookupFounderByUpstreamIdentity(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_found_returns_founder_id(self) -> None:
        bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
            display_name="Founder",
        )
        founder_id = lookup_founder_by_upstream_identity(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        self.assertIsNotNone(founder_id)
        self.assertEqual(founder_id, "founder-001")

    def test_not_found_returns_none(self) -> None:
        founder_id = lookup_founder_by_upstream_identity(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u-no-such",
        )
        self.assertIsNone(founder_id)

    def test_revoked_binding_not_found(self) -> None:
        bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        revoke_founder_binding(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        founder_id = lookup_founder_by_upstream_identity(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        self.assertIsNone(founder_id)


class TestRevokeFounderBinding(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_revoke_returns_true(self) -> None:
        bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        result = revoke_founder_binding(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        self.assertTrue(result)
        founder_id = lookup_founder_by_upstream_identity(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        self.assertIsNone(founder_id)

    def test_revoke_nonexistent_returns_false(self) -> None:
        result = revoke_founder_binding(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u-no-such",
        )
        self.assertFalse(result)

    def test_revoke_already_revoked_returns_false(self) -> None:
        bind_founder_identity(
            self.conn,
            founder_id="founder-001",
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        revoke_founder_binding(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        result = revoke_founder_binding(
            self.conn,
            adapter_id="telegram",
            upstream_user_id="u123456",
        )
        self.assertFalse(result)


class TestListFounderBindings(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_list_all(self) -> None:
        bind_founder_identity(self.conn, founder_id="f-001", adapter_id="telegram", upstream_user_id="u1")
        bind_founder_identity(self.conn, founder_id="f-001", adapter_id="openclaw", upstream_user_id="u2")
        bindings = list_founder_bindings(self.conn)
        self.assertEqual(len(bindings), 2)

    def test_filter_by_founder_id(self) -> None:
        bind_founder_identity(self.conn, founder_id="f-001", adapter_id="telegram", upstream_user_id="u1")
        bind_founder_identity(self.conn, founder_id="f-002", adapter_id="telegram", upstream_user_id="u2")
        bindings = list_founder_bindings(self.conn, founder_id="f-001")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0]["founder_id"], "f-001")


if __name__ == "__main__":
    unittest.main()
