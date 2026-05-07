"""Model-catalog enforcement helper for developer-assistant.

Parses MODEL-CATALOG.md v0.1.1 § 4.1 at import time to produce the single
source-of-truth RoleAssignment mapping.  Provides verification, probing,
and escalation helpers consumed by the install script and runtime-check.

No real tokens, PATs, or production hostnames appear in this module.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RoleAssignment:
    main: str
    fallbacks: list[str]


@dataclass
class ProbeResult:
    ok: bool
    role: str
    identifier: str
    reason: Optional[str]
    latency_ms: Optional[float]


class CatalogViolation(Exception):
    pass


class UnknownRole(Exception):
    pass


class CatalogParseError(Exception):
    pass


_ROLE_NAME_MAP: dict[str, str] = {
    "Orchestrator": "orchestrator",
    "Business Planner": "planner",
    "Architect": "architect",
    "Executor": "executor",
    "Reviewer": "reviewer",
}

_EXPECTED_TABLE_COLUMNS = 5

_PREFIX = "accounts/fireworks/models/"


def _strip_backticks(s: str) -> str:
    return s.strip().strip("`").strip()


def _find_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "architecture" / "MODEL-CATALOG.md"


def _parse_catalog_table(text: str) -> dict[str, RoleAssignment]:
    if "Auxiliary classifier" in text:
        raise CatalogParseError(
            "v0.1.0-style auxiliary classifier table detected; "
            "schema mismatch — v0.1.1 has no auxiliary classifier set"
        )

    section_41_pattern = re.compile(r"###\s*4\.1\s")
    section_41_match = section_41_pattern.search(text)
    if section_41_match is None:
        raise CatalogParseError(
            "MODEL-CATALOG.md § 4.1 per-role assignment table not found"
        )

    after_section = text[section_41_match.end():]

    next_section_pattern = re.compile(r"\n###\s")
    next_section_match = next_section_pattern.search(after_section)
    section_text = (
        after_section[:next_section_match.start()] if next_section_match else after_section
    )

    lines = section_text.splitlines()
    table_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)

    if len(table_lines) < 3:
        raise CatalogParseError(
            "MODEL-CATALOG.md § 4.1 table has fewer than 3 rows "
            "(header + separator + at least one data row required)"
        )

    header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
    if len(header_cells) != _EXPECTED_TABLE_COLUMNS:
        raise CatalogParseError(
            "MODEL-CATALOG.md § 4.1 table has {actual} columns, "
            "expected {expected}".format(
                actual=len(header_cells), expected=_EXPECTED_TABLE_COLUMNS
            )
        )

    separator = table_lines[1]
    if not re.match(r"^\|[\s\-:|]+\|$", separator):
        raise CatalogParseError(
            "MODEL-CATALOG.md § 4.1 table separator row is malformed"
        )

    catalog: dict[str, RoleAssignment] = {}
    for row_line in table_lines[2:]:
        cells = [_strip_backticks(c) for c in row_line.strip("|").split("|")]
        if len(cells) != _EXPECTED_TABLE_COLUMNS:
            raise CatalogParseError(
                "MODEL-CATALOG.md § 4.1 data row has {actual} cells, "
                "expected {expected}: {row}".format(
                    actual=len(cells), expected=_EXPECTED_TABLE_COLUMNS, row=row_line
                )
            )
        catalog_role, main, fb1, fb2, fb3 = cells
        code_role = _ROLE_NAME_MAP.get(catalog_role)
        if code_role is None:
            raise CatalogParseError(
                "Unknown catalog role '{r}' in MODEL-CATALOG.md § 4.1".format(
                    r=catalog_role
                )
            )
        catalog[code_role] = RoleAssignment(
            main=main,
            fallbacks=[fb1, fb2, fb3],
        )

    expected_roles = set(_ROLE_NAME_MAP.values())
    found_roles = set(catalog.keys())
    if found_roles != expected_roles:
        missing = expected_roles - found_roles
        if missing:
            raise CatalogParseError(
                "MODEL-CATALOG.md § 4.1 is missing roles: {m}".format(
                    m=", ".join(sorted(missing))
                )
            )

    return catalog


def _load_catalog() -> dict[str, RoleAssignment]:
    catalog_path = _find_catalog_path()
    if not catalog_path.exists():
        raise CatalogParseError(
            "MODEL-CATALOG.md not found at {p}".format(p=catalog_path)
        )
    text = catalog_path.read_text(encoding="utf-8")
    return _parse_catalog_table(text)


_CATALOG: dict[str, RoleAssignment] = _load_catalog()


def get_role_assignment(role: str) -> RoleAssignment:
    assignment = _CATALOG.get(role)
    if assignment is None:
        valid = sorted(_CATALOG.keys())
        raise UnknownRole(
            "Unknown role '{r}'. Valid roles: {v}".format(r=role, v=", ".join(valid))
        )
    return assignment


def verify_runtime_config(role: str, config: dict) -> None:
    assignment = get_role_assignment(role)
    agent = config.get("agent", {})
    config_main = agent.get("model", "")
    config_fallbacks = agent.get("fallback_models", [])

    if config_main != assignment.main:
        raise CatalogViolation(
            "Role '{r}': config agent.model '{cm}' does not match "
            "catalog main '{am}'".format(r=role, cm=config_main, am=assignment.main)
        )

    for fm in config_fallbacks:
        if fm not in assignment.fallbacks:
            raise CatalogViolation(
                "Role '{r}': config fallback_models contains '{fm}' "
                "which is not in the catalog fallbacks".format(r=role, fm=fm)
            )

    for i, fm in enumerate(config_fallbacks):
        if fm != assignment.fallbacks[i]:
            raise CatalogViolation(
                "Role '{r}': config fallback_models is not a prefix of "
                "the canonical fallbacks — at position {i} config has "
                "'{cf}' but catalog has '{af}'".format(
                    r=role, i=i, cf=fm, af=assignment.fallbacks[i]
                )
            )


def _probe_identifier(
    omniroute_base_url: str,
    role: str,
    identifier: str,
    timeout_seconds: float = 10.0,
) -> ProbeResult:
    url = omniroute_base_url.rstrip("/") + "/v1/chat/completions"
    body = json.dumps({
        "model": identifier,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout_seconds)
        elapsed_ms = (time.monotonic() - start) * 1000.0
        resp_body = resp.read().decode("utf-8")
        data = json.loads(resp_body)
        resp_model = data.get("model", "")
        if resp_model == identifier:
            return ProbeResult(
                ok=True,
                role=role,
                identifier=identifier,
                reason=None,
                latency_ms=elapsed_ms,
            )
        return ProbeResult(
            ok=False,
            role=role,
            identifier=identifier,
            reason="not_resolved",
            latency_ms=elapsed_ms,
        )
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        if exc.code in (401, 403):
            reason = "auth_failure"
        elif exc.code == 404:
            reason = "not_resolved"
        else:
            reason = "unexpected_response"
        return ProbeResult(
            ok=False,
            role=role,
            identifier=identifier,
            reason=reason,
            latency_ms=elapsed_ms,
        )
    except urllib.error.URLError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        reason_str = str(getattr(exc, "reason", ""))
        if isinstance(reason_str, str) and "ConnectionRefusedError" in reason_str:
            return ProbeResult(
                ok=False,
                role=role,
                identifier=identifier,
                reason="unreachable",
                latency_ms=elapsed_ms,
            )
        return ProbeResult(
            ok=False,
            role=role,
            identifier=identifier,
            reason="unreachable",
            latency_ms=elapsed_ms,
        )
    except TimeoutError:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return ProbeResult(
            ok=False,
            role=role,
            identifier=identifier,
            reason="timeout",
            latency_ms=elapsed_ms,
        )
    except Exception:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return ProbeResult(
            ok=False,
            role=role,
            identifier=identifier,
            reason="unexpected_response",
            latency_ms=elapsed_ms,
        )


def probe_omniroute(
    omniroute_base_url: str,
    role: str,
    timeout_seconds: float = 10.0,
) -> ProbeResult:
    assignment = get_role_assignment(role)
    return _probe_identifier(
        omniroute_base_url, role, assignment.main, timeout_seconds
    )


def paid_third_party_external_service_not_yet_supported_error(
    role: str,
    identifier: str,
    reason: str,
) -> None:
    raise CatalogViolation(
        "paid:third_party_external_service_not_yet_supported — "
        "role={r}, identifier={id}, reason={reason}".format(
            r=role, id=identifier, reason=reason
        )
    )
