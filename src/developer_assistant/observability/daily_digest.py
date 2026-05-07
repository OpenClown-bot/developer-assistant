"""Daily digest renderer and delivery module.

Implements OBSERVABILITY-CONTRACT.md v0.1.1 § 8 (FR-OBS-05).

Public API:
  render_digest(window_start, window_end) -> str
  write_digest(window_start, window_end, dest_dir) -> Path
  deliver_digest_via_telegram(path) -> None

Queries operational.db using observability_store helpers.
Degrades gracefully if tables are missing (TKT-031 not yet merged):
emits "No data available" for that section, does not crash.

Stdlib only.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from developer_assistant.observability.telegram_utils import paginate_text
from pathlib import Path
from typing import Any, Optional, Protocol

_DEFAULT_DB_PATH = "/srv/devassist/state/operational.db"
_DEFAULT_DEST_DIR = "/var/log/dev-assist"
_RECOVERY_PLAYBOOK_LINK = "docs/operations/RECOVERY-PLAYBOOK.md"


class DigestDeliveryError(Exception):
    """Raised when Telegram delivery of the daily digest fails."""


class TelegramClient(Protocol):
    def send_message(self, chat_key: str, text: str) -> None: ...


def _open_db_readonly(db_path: str) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&nolock=1", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def _query_work_items_completed(
    conn: sqlite3.Connection,
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "work_items"):
        return []
    start_iso = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        cur = conn.execute(
            """SELECT runtime, COUNT(*) as cnt
               FROM work_items
               WHERE status = 'completed'
                 AND completed_at >= ? AND completed_at < ?
               GROUP BY runtime
               ORDER BY runtime""",
            (start_iso, end_iso),
        )
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def _query_escalations(
    conn: sqlite3.Connection,
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "escalations"):
        return []
    start_iso = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        cur = conn.execute(
            """SELECT created_at as ts_iso, trigger_kind as rule,
                      status as disposition
               FROM escalations
               WHERE created_at >= ? AND created_at < ?
               ORDER BY created_at DESC""",
            (start_iso, end_iso),
        )
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def _query_errors_summary(
    conn: sqlite3.Connection,
    window_start: datetime,
    window_end: datetime,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    if not _table_exists(conn, "errors"):
        return [], None
    start_iso = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        cur = conn.execute(
            """SELECT runtime, COUNT(*) as cnt
               FROM errors
               WHERE ts >= ? AND ts < ?
               GROUP BY runtime
               ORDER BY runtime""",
            (start_iso, end_iso),
        )
        by_runtime = [dict(r) for r in cur.fetchall()]

        top_cur = conn.execute(
            """SELECT error_class, COUNT(*) as cnt
               FROM errors
               WHERE ts >= ? AND ts < ?
               GROUP BY error_class
               ORDER BY cnt DESC
               LIMIT 1""",
            (start_iso, end_iso),
        )
        top_row = top_cur.fetchone()
        top_error_class = top_row["error_class"] if top_row else None
        return by_runtime, top_error_class
    except sqlite3.OperationalError:
        return [], None


def _query_llm_costs(
    conn: sqlite3.Connection,
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "llm_calls"):
        return []
    start_iso = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        cur = conn.execute(
            """SELECT runtime, model,
                      SUM(tokens_in) as tokens_in,
                      SUM(tokens_out) as tokens_out,
                      SUM(cost_usd) as cost_usd
               FROM llm_calls
               WHERE ts >= ? AND ts < ?
               GROUP BY runtime, model
               ORDER BY runtime, model""",
            (start_iso, end_iso),
        )
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def _count_runtimes_up_down() -> tuple[int, int]:
    up = 0
    down = 0
    roles = ["orchestrator", "planner", "architect", "executor", "reviewer"]
    for role in roles:
        try:
            import subprocess
            result = subprocess.run(
                ["systemctl", "is-active", f"devassist-{role}.service"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip() == "active":
                up += 1
            else:
                down += 1
        except Exception:
            down += 1
    return up, down


def _human_tokens(n: int) -> str:
    if n >= 1000000:
        return f"{n / 1000000:.1f}M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def render_digest(
    window_start: datetime,
    window_end: datetime,
    db_path: str = _DEFAULT_DB_PATH,
) -> str:
    """Render a Markdown daily digest for the given time window.

    Returns Markdown matching OBSERVABILITY-CONTRACT.md § 8 layout.
    Degrades gracefully if tables are missing.
    """
    lines: list[str] = []

    date_str = window_start.strftime("%Y-%m-%d")
    up, down = _count_runtimes_up_down()
    lines.append(f"# Daily Digest — {date_str}")
    lines.append(f"**Runtimes:** {up} up, {down} down")
    lines.append(f"**Window:** [{window_start.isoformat()} — {window_end.isoformat()})")
    lines.append("")

    conn = _open_db_readonly(db_path)
    try:
        work_items = _query_work_items_completed(conn, window_start, window_end)
        if work_items:
            lines.append("## Work Items Completed")
            lines.append("")
            lines.append("| Runtime | Count |")
            lines.append("|---------|-------|")
            for wi in work_items:
                lines.append(f"| {wi['runtime']} | {wi['cnt']} |")
            lines.append("")
        else:
            lines.append("## Work Items Completed")
            lines.append("")
            lines.append("No data available")
            lines.append("")

        errors_by_runtime, top_error_class = _query_errors_summary(conn, window_start, window_end)
        has_errors = bool(errors_by_runtime)
        if errors_by_runtime:
            lines.append("## Errors")
            lines.append("")
            lines.append("| Runtime | Count |")
            lines.append("|---------|-------|")
            for e in errors_by_runtime:
                lines.append(f"| {e['runtime']} | {e['cnt']} |")
            if top_error_class:
                lines.append(f"\n**Top error class:** {top_error_class}")
            lines.append("")
        else:
            lines.append("## Errors")
            lines.append("")
            lines.append("No data available")
            lines.append("")

        escalations = _query_escalations(conn, window_start, window_end)
        if escalations:
            lines.append("## Escalations")
            lines.append("")
            lines.append("| Time | Rule | Disposition |")
            lines.append("|------|------|-------------|")
            for esc in escalations:
                ts = esc.get("ts_iso", "")
                rule = esc.get("rule", "")
                disp = esc.get("disposition", "")
                lines.append(f"| {ts} | {rule} | {disp} |")
            lines.append("")
        else:
            lines.append("## Escalations")
            lines.append("")
            lines.append("No data available")
            lines.append("")

        llm_costs = _query_llm_costs(conn, window_start, window_end)
        if llm_costs:
            lines.append("## LLM Cost (by role, model)")
            lines.append("")
            lines.append("| Role | Model | Tokens In | Tokens Out | Cost USD |")
            lines.append("|------|-------|-----------|------------|----------|")
            for lc in llm_costs:
                tin = _human_tokens(int(lc.get("tokens_in", 0)))
                tout = _human_tokens(int(lc.get("tokens_out", 0)))
                cost = float(lc.get("cost_usd", 0))
                lines.append(f"| {lc['runtime']} | {lc['model']} | {tin} | {tout} | ${cost:.2f} |")
            lines.append("")
        else:
            lines.append("## LLM Cost (by role, model)")
            lines.append("")
            lines.append("No data available")
            lines.append("")
    finally:
        conn.close()

    if has_errors:
        lines.append(f"See {_RECOVERY_PLAYBOOK_LINK} for error recovery procedures.")
        lines.append("")

    return "\n".join(lines)


def write_digest(
    window_start: datetime,
    window_end: datetime,
    dest_dir: str = _DEFAULT_DEST_DIR,
    db_path: str = _DEFAULT_DB_PATH,
) -> Path:
    """Render the digest and write it to disk.

    Filename: daily-digest-YYYYMMDD.md where YYYYMMDD comes from
    window_start in VPS local time.
    Idempotent overwrite.
    Returns the Path of the written file.
    """
    content = render_digest(window_start, window_end, db_path=db_path)
    date_str = window_start.strftime("%Y%m%d")
    filename = f"daily-digest-{date_str}.md"
    dest_path = Path(dest_dir) / filename

    os.makedirs(dest_dir, exist_ok=True)
    dest_path.write_text(content, encoding="utf-8")
    return dest_path


def deliver_digest_via_telegram(
    path: Path,
    telegram_client: Optional[TelegramClient] = None,
    chat_key: str = "chat:founder",
) -> None:
    """Read the rendered digest file and send it via Telegram.

    On failure raises DigestDeliveryError.
    The on-disk file is preserved either way.
    """
    content = path.read_text(encoding="utf-8")

    if telegram_client is None:
        telegram_client = _get_default_telegram_client()

    try:
        _send_paginated(telegram_client, chat_key, content)
    except Exception as e:
        raise DigestDeliveryError(
            f"Failed to deliver digest via Telegram: {e}"
        ) from e


def _send_paginated(
    client: TelegramClient,
    chat_key: str,
    text: str,
    max_len: int = 4096,
) -> None:
    for part in paginate_text(text, max_len):
        client.send_message(chat_key, part)


def _get_default_telegram_client() -> TelegramClient:
    from developer_assistant.telegram_adapter import TelegramSender
    from developer_assistant.hermes_telegram_transport import HermesTelegramGatewayBinding

    try:
        binding = HermesTelegramGatewayBinding.from_env()
        return _TelegramClientWrapper(binding)
    except Exception:
        raise DigestDeliveryError(
            "No Telegram client available and none was injected"
        )


class _TelegramClientWrapper:
    def __init__(self, binding: Any) -> None:
        self._binding = binding

    def send_message(self, chat_key: str, text: str) -> None:
        self._binding.send_to_chat(chat_key, text)


def main() -> None:
    """CLI entry point: python -m developer_assistant.observability.daily_digest --previous-day"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate daily digest")
    parser.add_argument(
        "--previous-day", action="store_true",
        help="Use the previous calendar day (VPS local time) as the window",
    )
    parser.add_argument(
        "--db-path", default=_DEFAULT_DB_PATH,
        help="Path to operational.db",
    )
    parser.add_argument(
        "--dest-dir", default=_DEFAULT_DEST_DIR,
        help="Directory to write digest file",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if args.previous_day:
        window_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
        window_end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    else:
        window_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        window_end = now

    path = write_digest(window_start, window_end, dest_dir=args.dest_dir, db_path=args.db_path)
    print(f"Digest written to {path}")


if __name__ == "__main__":
    main()
