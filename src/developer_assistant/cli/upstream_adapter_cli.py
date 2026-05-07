"""Dev-only CLI for local contract testing of the upstream-adapter scaffolding.

Not exposed in production. Allows exercising the five adapter operations
against an in-memory SQLite store without a running Hermes runtime.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from developer_assistant.state_store import open_store
from developer_assistant.upstream_adapters.base import (
    ApprovalPromptInput,
    BindFounderIdentityInput,
    GetOrCreateSessionInput,
    InboundMessageInput,
    OutboundMessageInput,
)
from developer_assistant.upstream_adapters.registry import AdapterRegistry
from developer_assistant.upstream_adapters.router import OutboundIntent, Router
from developer_assistant.upstream_adapters.telegram import TelegramAdapter


def _cmd_register(args: argparse.Namespace) -> int:
    conn = open_store(":memory:")
    registry = AdapterRegistry()
    adapter = TelegramAdapter(conn)
    registry.register("telegram", adapter)
    print("Registered adapter: telegram")
    return 0


def _cmd_inbound(args: argparse.Namespace) -> int:
    conn = open_store(":memory:")
    adapter = TelegramAdapter(conn)
    if args.bind_user:
        from developer_assistant.founder_identity import bind_founder_identity

        bind_founder_identity(
            conn,
            founder_id="founder-1",
            adapter_id="telegram",
            upstream_user_id=args.user_id,
        )
    inp = InboundMessageInput(
        adapter_id="telegram",
        upstream_user_id=args.user_id,
        upstream_chat_id=args.chat_id,
        message_text=args.text,
        message_id="cli-msg-1",
        received_at="2026-05-07T00:00:00Z",
    )
    result = adapter.inbound_message(inp)
    print(json.dumps(result.__dict__, default=str, ensure_ascii=False, indent=2))
    return 0


def _cmd_outbound(args: argparse.Namespace) -> int:
    conn = open_store(":memory:")
    adapter = TelegramAdapter(conn)
    inp = OutboundMessageInput(
        adapter_id="telegram",
        founder_id=args.founder_id,
        session_id=args.session_id,
        message_text=args.text,
        purpose=args.purpose,
    )
    try:
        result = adapter.outbound_message(inp)
        print(json.dumps(result.__dict__, default=str, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_approval(args: argparse.Namespace) -> int:
    conn = open_store(":memory:")
    adapter = TelegramAdapter(conn)
    inp = ApprovalPromptInput(
        escalation_id=args.escalation_id,
        adapter_id="telegram",
        founder_id=args.founder_id,
        session_id=args.session_id,
        prompt_text=args.text,
        originating_runtime=args.runtime,
        proposed_action=args.action,
        trigger_kind=args.trigger,
        recommended_default=args.default,
        impact=args.impact,
        urgency=args.urgency,
    )
    try:
        result = adapter.outbound_approval_prompt(inp)
        print(json.dumps(result.__dict__, default=str, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dev-only CLI for upstream-adapter contract testing"
    )
    sub = parser.add_subparsers(dest="command")

    p_reg = sub.add_parser("register", help="Register telegram adapter")
    p_reg.set_defaults(func=_cmd_register)

    p_in = sub.add_parser("inbound", help="Simulate inbound message")
    p_in.add_argument("--user-id", default="tg-user-1")
    p_in.add_argument("--chat-id", default="chat:proj-alpha")
    p_in.add_argument("--text", default="hello")
    p_in.add_argument("--bind-user", action="store_true")
    p_in.set_defaults(func=_cmd_inbound)

    p_out = sub.add_parser("outbound", help="Simulate outbound message")
    p_out.add_argument("--founder-id", default="founder-1")
    p_out.add_argument("--session-id", default="tg-chat:proj-alpha")
    p_out.add_argument("--text", default="Привет!")
    p_out.add_argument("--purpose", default="general_message")
    p_out.set_defaults(func=_cmd_outbound)

    p_ap = sub.add_parser("approval", help="Simulate approval prompt")
    p_ap.add_argument("--escalation-id", type=int, default=1)
    p_ap.add_argument("--founder-id", default="founder-1")
    p_ap.add_argument("--session-id", default="tg-chat:proj-alpha")
    p_ap.add_argument("--text", default="Approve deployment?")
    p_ap.add_argument("--runtime", default="executor")
    p_ap.add_argument("--action", default="deploy to production")
    p_ap.add_argument("--trigger", default="deterministic_rule:deploy:start_units_unprompted")
    p_ap.add_argument("--default", default="deny")
    p_ap.add_argument("--impact", default="Production deployment")
    p_ap.add_argument("--urgency", default="high")
    p_ap.set_defaults(func=_cmd_approval)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
