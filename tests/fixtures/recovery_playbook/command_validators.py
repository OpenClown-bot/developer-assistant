"""Per-command-kind validators for the Recovery Playbook invariant harness (TKT-030).

Reference data is extracted from architecture artifacts at module load time so
the harness stays in sync with doc updates.  All validators return (level, msg)
tuples where level is 'OK', 'WARNING', or 'FAILURE'.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple

Level = str
Msg = str
Verdict = Tuple[Level, Msg]

REPO_ROOT = Path(__file__).resolve().parents[3]

SYSTEMD_UNITS: Set[str] = {
    "devassist.target",
    "devassist-orchestrator.service",
    "devassist-planner.service",
    "devassist-architect.service",
    "devassist-executor.service",
    "devassist-reviewer.service",
    "omniroute.service",
    "devassist-web.service",
}

PORT_ROLE_MAP: Dict[int, str] = {
    8180: "web",
    8181: "orchestrator",
    8182: "planner",
    8183: "architect",
    8184: "executor",
    8185: "reviewer",
    20128: "omniroute",
}

SQL_TABLES: Dict[str, Set[str]] = {
    "project_bindings": {
        "chat_key", "repo_url", "repo_owner_name", "workspace_path",
        "phase", "updated_at",
    },
    "scheduled_progress": {
        "project_key", "last_report_at", "next_report_at",
        "interval_minutes", "updated_at",
    },
    "hermes_runs": {
        "run_id", "project_key", "role", "task_type", "status",
        "idempotency_key", "in_flight_meta", "updated_at",
    },
    "_schema_meta": {"key", "value"},
    "work_items": {
        "id", "created_at", "updated_at", "target_role", "kind",
        "payload_json", "priority", "status", "claimed_by_runtime",
        "claimed_at", "claim_lease_until", "completed_at", "result_json",
        "attempt_count", "max_attempts", "originating_run_id",
    },
    "escalations": {
        "id", "created_at", "updated_at", "originating_runtime",
        "originating_work_item_id", "trigger_kind", "context",
        "proposed_action", "options_json", "recommended_default",
        "impact", "urgency", "durable_artifact_target", "status",
        "surfaced_at", "resolved_at", "founder_response",
        "telegram_message_id",
    },
    "errors": {
        "err_id", "ts", "runtime", "work_item_id", "error_class",
        "message", "context_json",
    },
    "llm_calls": {
        "call_id", "ts", "runtime", "work_item_id", "model",
        "routing_path", "tokens_in", "tokens_out", "latency_ms",
        "rate_in_per_1m_usd", "rate_out_per_1m_usd", "cost_usd",
        "status", "error_class",
    },
    "llm_calls_daily": {
        "day", "runtime", "model", "routing_path", "call_count",
        "call_count_success", "call_count_fail", "tokens_in_total",
        "tokens_out_total", "cost_usd_total", "latency_ms_p50",
        "latency_ms_p95",
    },
}

ROLES = {"orchestrator", "planner", "architect", "executor", "reviewer"}

SCRIPT_NAMES_IN_REPO: Set[str] = set()
_scripts_dir = REPO_ROOT / "scripts"
if _scripts_dir.is_dir():
    for _p in _scripts_dir.iterdir():
        if _p.suffix == ".sh":
            SCRIPT_NAMES_IN_REPO.add(_p.name)

_CLI_MODULE = REPO_ROOT / "src" / "developer_assistant" / "cli" / "dev_assist_cli.py"
CLI_SUBCOMMANDS: Set[str] = set()
if _CLI_MODULE.is_file():
    _src = _CLI_MODULE.read_text(encoding="utf-8")
    for _m in re.finditer(r'add_parser\(\s*["\'](\w+)', _src):
        CLI_SUBCOMMANDS.add(_m.group(1))

_FENCED_RE = re.compile(r'```[^\n]*\n(.*?)```', re.DOTALL)
_INLINE_RE = re.compile(r'`([^`\n]+)`')
_SHELL_COMMAND_RE = re.compile(
    r'^(?:sudo\s+(?:-u\s+\w+\s+)?)?'
    r'(\S+)'
)

_PLACEHOLDER_RE = re.compile(r'<[^>]+>')

_SECTION_RE = re.compile(r'^##\s+(\d+)\.', re.MULTILINE)


def _expand_role_templates(text: str) -> List[str]:
    if "<<role>>" in text:
        return [text.replace("<<role>>", r) for r in ROLES]
    if "<role>" in text:
        return [text.replace("<role>", r) for r in ROLES]
    return [text]


def _is_template_only(raw: str) -> bool:
    placeholders = _PLACEHOLDER_RE.findall(raw)
    template_only_names = {"<unit>", "<command>"}
    return any(p in template_only_names for p in placeholders)


def _expand_port_templates(text: str) -> List[str]:
    if "<n>" not in text:
        return [text]
    out = []
    for n in range(1, 6):
        out.append(text.replace("<n>", str(n)))
    return out


def parse_playbook(md_text: str) -> List[Dict]:
    sections = list(_SECTION_RE.finditer(md_text))
    section_map: List[Tuple[int, str]] = []
    for m in sections:
        section_map.append((m.start(), m.group(1)))

    def _section_for(pos: int) -> str:
        for i in range(len(section_map) - 1, -1, -1):
            if section_map[i][0] <= pos:
                return f"\u00a7{section_map[i][1]}"
        return "\u00a70"

    commands: List[Dict] = []
    seen_raw: Set[str] = set()

    def _add(raw: str, section: str, source: str) -> None:
        key = (raw.strip(), section)
        if key in seen_raw:
            return
        seen_raw.add(key)
        commands.append({"raw": raw.strip(), "section": section, "source": source})

    for m in _FENCED_RE.finditer(md_text):
        block = m.group(1).strip()
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sm = _SHELL_COMMAND_RE.match(line)
            if sm:
                if _is_template_only(line):
                    continue
                sec = _section_for(m.start())
                for role_expanded in _expand_role_templates(line):
                    for port_expanded in _expand_port_templates(role_expanded):
                        _add(port_expanded, sec, "fenced")

    for m in _INLINE_RE.finditer(md_text):
        span = m.group(1).strip()
        if any(c in span for c in "=|{}"):
            continue
        sm = _SHELL_COMMAND_RE.match(span)
        if not sm:
            continue
        bin_name = sm.group(1)
        known_bins = {
            "dev-assist-cli", "systemctl", "journalctl", "curl", "sqlite3",
            "free", "df", "top", "find", "timedatectl", "chmod", "chown",
            "ls", "mkdir", "gzip", "hermes", "python",
        }
        if bin_name not in known_bins and not span.startswith("scripts/"):
            continue
        if _is_template_only(span):
            continue
        sec = _section_for(m.start())
        for role_expanded in _expand_role_templates(span):
            for port_expanded in _expand_port_templates(role_expanded):
                _add(port_expanded, sec, "inline")

    return commands


def classify_command(raw: str) -> str:
    stripped = re.sub(r'^sudo\s+(?:-u\s+\w+\s+)?', '', raw.strip())
    sm = _SHELL_COMMAND_RE.match(stripped)
    if not sm:
        return "OTHER"
    bin_name = sm.group(1)
    mapping = {
        "dev-assist-cli": "dev-assist-cli",
        "systemctl": "systemctl",
        "journalctl": "journalctl",
        "curl": "curl",
        "sqlite3": "sqlite3",
        "free": "free",
        "df": "df",
        "top": "top",
        "find": "find",
        "timedatectl": "timedatectl",
        "chmod": "chmod",
        "chown": "chown",
        "ls": "ls",
        "mkdir": "mkdir",
        "gzip": "gzip",
        "hermes": "hermes",
        "python": "python",
    }
    if bin_name in mapping:
        return mapping[bin_name]
    if raw.strip().startswith("scripts/"):
        return "scripts"
    return "OTHER"


def validate_dev_assist_cli(raw: str) -> Verdict:
    m = re.search(r'dev-assist-cli\s+(\S+)', raw)
    if not m:
        return ("WARNING", f"cannot extract subcommand from: {raw}")
    subcommand = m.group(1)
    if subcommand.startswith("-"):
        return ("WARNING", f"dev-assist-cli flag-only invocation: {raw}")
    if not _CLI_MODULE.is_file():
        return ("WARNING",
                f"dev-assist-cli module not yet landed (TKT-027); "
                f"cannot verify subcommand '{subcommand}'")
    if subcommand in CLI_SUBCOMMANDS:
        return ("OK", f"dev-assist-cli {subcommand} resolved")
    return ("FAILURE",
            f"dev-assist-cli subcommand '{subcommand}' not in argparse "
            f"(found: {sorted(CLI_SUBCOMMANDS)})")


KNOWN_PLAYBOOK_INCONSISTENCIES = {}


def _check_known_inconsistency(unit: str) -> Verdict | None:
    if unit in KNOWN_PLAYBOOK_INCONSISTENCIES:
        correct, note = KNOWN_PLAYBOOK_INCONSISTENCIES[unit]
        return ("FAILURE",
                f"unit '{unit}' inconsistent with architecture artifacts: "
                f"should be '{correct}'. {note}")
    return None


def validate_systemctl(raw: str) -> Verdict:
    m = re.search(r'systemctl\s+\S+\s+(\S+)', raw)
    if not m:
        return ("WARNING", f"cannot extract unit from systemctl: {raw}")
    unit = m.group(1).rstrip(";").rstrip("&&")
    if unit in SYSTEMD_UNITS:
        return ("OK", f"systemctl unit '{unit}' valid")
    if unit.startswith("devassist-") and unit.endswith(".service"):
        role_part = unit[len("devassist-"):-len(".service")]
        if role_part in ROLES:
            return ("OK", f"systemctl unit '{unit}' valid (expanded from template)")
    known = _check_known_inconsistency(unit)
    if known is not None:
        return known
    return ("FAILURE",
            f"systemctl unit '{unit}' not in SELF-DEPLOYMENT-CONTRACT.md \u00a75 "
            f"(valid: {sorted(SYSTEMD_UNITS)})")


def validate_journalctl(raw: str) -> Verdict:
    m = re.search(r'journalctl.*-u\s+(\S+)', raw)
    if not m:
        return ("OK", f"journalctl without -u flag: {raw}")
    unit = m.group(1).strip('"').strip("'")
    if unit in SYSTEMD_UNITS:
        return ("OK", f"journalctl unit '{unit}' valid")
    if unit.startswith("devassist-") and unit.endswith(".service"):
        role_part = unit[len("devassist-"):-len(".service")]
        if role_part in ROLES:
            return ("OK", f"journalctl unit '{unit}' valid (expanded from template)")
    known = _check_known_inconsistency(unit)
    if known is not None:
        return known
    return ("FAILURE",
            f"journalctl unit '{unit}' not in SELF-DEPLOYMENT-CONTRACT.md \u00a75")


def validate_curl(raw: str) -> Verdict:
    m = re.search(r'127\.0\.0\.1:(\d+)', raw)
    if not m:
        return ("OK", f"curl without localhost port: {raw}")
    port = int(m.group(1))
    if port in PORT_ROLE_MAP:
        return ("OK", f"curl port {port} valid (={PORT_ROLE_MAP[port]})")
    return ("FAILURE",
            f"curl port {port} not in SELF-DEPLOYMENT-CONTRACT.md \u00a75.2 "
            f"(valid: {sorted(PORT_ROLE_MAP.keys())})")


def _extract_sql_from_sqlite3(raw: str) -> str:
    m = re.search(r"sqlite3\s+\S+\s+'(.+)'", raw, re.DOTALL)
    if not m:
        m = re.search(r'sqlite3\s+\S+\s+"(.+)"', raw, re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_tables_and_columns(sql: str) -> List[Tuple[str, Set[str]]]:
    results: List[Tuple[str, Set[str]]] = []
    for table_name in SQL_TABLES:
        if re.search(r'\b' + re.escape(table_name) + r'\b', sql, re.IGNORECASE):
            cols: Set[str] = set()
            for col in SQL_TABLES[table_name]:
                if re.search(r'\b' + re.escape(col) + r'\b', sql):
                    cols.add(col)
            results.append((table_name, cols))
    return results


def _extract_from_clause_tables(sql: str) -> List[str]:
    tables: List[str] = []
    from_pattern = re.compile(
        r'\bFROM\s+([a-z_]\w*)', re.IGNORECASE)
    for m in from_pattern.finditer(sql):
        tables.append(m.group(1))
    join_pattern = re.compile(
        r'\bJOIN\s+([a-z_]\w*)', re.IGNORECASE)
    for m in join_pattern.finditer(sql):
        tables.append(m.group(1))
    into_pattern = re.compile(
        r'\bINTO\s+([a-z_]\w*)', re.IGNORECASE)
    for m in into_pattern.finditer(sql):
        tables.append(m.group(1))
    update_pattern = re.compile(
        r'\bUPDATE\s+([a-z_]\w*)', re.IGNORECASE)
    for m in update_pattern.finditer(sql):
        tables.append(m.group(1))
    return tables


def validate_sqlite3(raw: str) -> Verdict:
    sql = _extract_sql_from_sqlite3(raw)
    if not sql:
        if "PRAGMA" in raw and "quick_check" in raw:
            return ("OK", "PRAGMA quick_check — no table/column reference to validate")
        return ("WARNING", f"cannot extract SQL from sqlite3 invocation: {raw}")

    if not sqlite3.complete_statement(sql):
        return ("WARNING", f"SQL does not parse as complete statement: {sql[:60]}")

    from_tables = _extract_from_clause_tables(sql)
    for tname in from_tables:
        if tname.lower() not in {t.lower() for t in SQL_TABLES}:
            return ("FAILURE",
                    f"SQL references table '{tname}' not in "
                    f"OPERATIONAL-STATE-STORE.md \u00a73 "
                    f"(valid: {sorted(SQL_TABLES.keys())})")

    table_refs = _extract_tables_and_columns(sql)
    for table_name, referenced_cols in table_refs:
        if table_name not in SQL_TABLES:
            return ("FAILURE",
                    f"SQL references table '{table_name}' not in "
                    f"OPERATIONAL-STATE-STORE.md \u00a73")
        valid_cols = SQL_TABLES[table_name]
        unknown = referenced_cols - valid_cols
        if unknown:
            return ("FAILURE",
                    f"SQL references unknown column(s) {unknown} in table "
                    f"'{table_name}' (valid: {sorted(valid_cols)})")

    return ("OK", f"sqlite3 SQL validated: {sql[:60]}")


def validate_script(raw: str) -> Verdict:
    m = re.search(r'(?:scripts/|/scripts/)(\S+\.sh)', raw)
    if not m:
        return ("WARNING", f"cannot extract script name from: {raw}")
    script_name = m.group(1)
    if script_name in SCRIPT_NAMES_IN_REPO:
        return ("OK", f"script '{script_name}' exists in repo")
    return ("WARNING",
            f"script '{script_name}' not yet in repo/scripts/ "
            f"(TKT-020 may not have landed)")


def validate_command(cmd: Dict) -> Verdict:
    raw = cmd["raw"]
    kind = classify_command(raw)
    dispatch = {
        "dev-assist-cli": validate_dev_assist_cli,
        "systemctl": validate_systemctl,
        "journalctl": validate_journalctl,
        "curl": validate_curl,
        "sqlite3": validate_sqlite3,
        "scripts": validate_script,
    }
    validator = dispatch.get(kind)
    if validator:
        return validator(raw)
    return ("OK", f"{kind} command (no deep validation): {raw[:60]}")
