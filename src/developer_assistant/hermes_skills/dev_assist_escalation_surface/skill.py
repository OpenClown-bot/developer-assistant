"""Hermes custom skill: dev-assist-escalation-surface.

Orchestrator-only skill that surfaces pending escalations to the Founder
through the upstream router and expires stale escalations.  Router
dispatch is dependency-injected for offline testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from developer_assistant.escalations import (
    expire_old_escalations,
    mark_escalation_surfaced,
    read_pending_escalations,
)
from developer_assistant.hermes_skills import load_locale_yaml

logger = logging.getLogger(__name__)

_PACKAGE_DIR = str(Path(__file__).resolve().parent)

RouterDispatch = Callable[[str, str], str]


@dataclass
class SurfaceResult:
    surfaced: int = 0
    errors: list[str] = field(default_factory=list)


class EscalationSurfaceSkill:
    """Surfaces pending escalations to the Founder and expires stale ones.

    Loaded only by the Orchestrator runtime (MULTI-HERMES-CONTRACT.md § 5.1).
    ``surface_pending`` is driven by a 5-second cron trigger;
    ``expire_old`` is driven by a 60-second cron trigger.
    """

    runtime_loadout: str = "orchestrator-only"

    def __init__(
        self,
        db: object,
        router_dispatch: RouterDispatch,
        locale: Optional[dict[str, Any]] = None,
    ) -> None:
        self._db = db
        self._router_dispatch = router_dispatch
        if locale is None:
            locale = load_locale_yaml(_PACKAGE_DIR)
        self._locale = locale

    def surface_pending(self, now_iso: str) -> int:
        """Read pending escalations, format and dispatch each, and mark surfaced.

        Returns the number of escalations successfully surfaced.
        Escalations where the router errors are left pending for
        the next cycle.
        """
        try:
            pending = read_pending_escalations(self._db, limit=10)
        except Exception:
            return 0

        surfaced = 0
        for esc in pending:
            try:
                text = self._format_escalation(esc)
                message_id = self._router_dispatch(
                    text, str(esc["id"])
                )

                mark_escalation_surfaced(
                    self._db,
                    escalation_id=esc["id"],
                    telegram_message_id=message_id,
                )
                surfaced += 1
            except Exception as exc:
                logger.warning(
                    self._locale["errors"]["router_error"].format(
                        error=str(exc)
                    )
                )

        return surfaced

    def expire_old(self, now_iso: str) -> int:
        """Expire escalations older than 7 days.

        Returns the number of expired rows.
        """
        try:
            return expire_old_escalations(self._db, max_age_days=7)
        except Exception:
            return 0

    def _format_escalation(self, esc: Mapping[str, Any]) -> str:
        p = self._locale["prompt"]

        options_json = esc.get("options_json", "[]")
        options = options_json
        if isinstance(options, str):
            try:
                import json
                parsed = json.loads(options)
            except (json.JSONDecodeError, TypeError):
                parsed = []
            options = parsed
        options_list = options if isinstance(options, list) else []

        resolution_hint = p["resolution_hint"].format(id=esc["id"])

        lines = [
            p["header"],
            p["escalation_id"].format(id=esc["id"]),
            p["originating_runtime"].format(
                runtime=esc.get("originating_runtime", "")
            ),
            p["proposed_action"].format(
                action=esc.get("proposed_action", "")
            ),
            p["trigger_kind"].format(
                trigger=esc.get("trigger_kind", "")
            ),
            p["recommended_default"].format(
                recommendation=esc.get("recommended_default", "")
            ),
            p["impact"].format(
                impact=esc.get("impact", "")
            ),
            p["urgency"].format(
                urgency=esc.get("urgency", "low")
            ),
        ]

        context = esc.get("context", "")
        if context:
            lines.append(f"\n{context}")

        if options_list:
            lines.append(
                "\n".join(f"  - {opt}" for opt in options_list)
            )

        lines.append(f"\n{resolution_hint}")
        return "\n".join(lines)