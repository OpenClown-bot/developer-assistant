"""Hermes custom skill: dev-assist-progress-report.

Orchestrator-only skill that periodically checks project progress,
gathers PR status, formats a Russian-localized report, and dispatches
it through the upstream router.  GitHub and router interactions are
dependency-injected for offline testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from developer_assistant.hermes_skills import load_locale_yaml
from developer_assistant.progress_scheduling import is_report_due, mark_report_sent
from developer_assistant.state_store import list_project_bindings

logger = logging.getLogger(__name__)

_PACKAGE_DIR = str(Path(__file__).resolve().parent)

PRFetcher = Callable[[str, str], list[dict[str, str]]]
RouterDispatch = Callable[[str, str], str]


@dataclass
class TickResult:
    projects_checked: int = 0
    reports_sent: int = 0
    projects_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class ProgressReportSkill:
    """Periodic progress-report driver.

    Loaded only by the Orchestrator runtime (MULTI-HERMES-CONTRACT.md § 5.1).
    Default per-project report interval is 60 min (ARCH-001 § 7).
    """

    runtime_loadout: str = "orchestrator-only"

    def __init__(
        self,
        db: object,
        pr_fetcher: PRFetcher,
        router_dispatch: RouterDispatch,
        locale: Optional[dict[str, Any]] = None,
    ) -> None:
        self._db = db
        self._pr_fetcher = pr_fetcher
        self._router_dispatch = router_dispatch
        if locale is None:
            locale = load_locale_yaml(_PACKAGE_DIR)
        self._locale = locale

    def tick(self, now_iso: str) -> TickResult:
        """Check all active projects and send reports for those that are due.

        On success dispatches the report via the upstream router and
        calls ``mark_report_sent``.  If the GitHub client raises, the
        project is skipped with a structured log entry — no partial
        report is emitted.
        """
        result = TickResult()

        try:
            bindings = list_project_bindings(self._db)
        except Exception:
            return result

        for binding in bindings:
            project_key = binding["chat_key"]
            result.projects_checked += 1

            if not is_report_due(self._db, project_key, now_iso):
                result.projects_skipped += 1
                continue

            try:
                prs = self._pr_fetcher(
                    binding.get("repo_owner_name", ""),
                    binding.get("repo_url", ""),
                )
            except Exception:
                msg = self._locale["errors"]["github_unreachable"].format(
                    project=project_key
                )
                logger.warning(msg)
                result.errors.append(msg)
                result.projects_skipped += 1
                continue

            report_text = self._format_report(binding, prs)
            message_id = self._router_dispatch(
                report_text, project_key
            )

            mark_report_sent(self._db, project_key, now_iso)
            result.reports_sent += 1

        return result

    def _format_report(
        self,
        binding: Mapping[str, Any],
        prs: list[dict[str, str]],
    ) -> str:
        locale = self._locale["report"]

        project_name = binding.get("workspace_path") or binding.get(
            "repo_url", binding["chat_key"]
        )
        lines = [locale["header"]]
        lines.append(
            locale["project_name"].format(project_name=project_name)
        )

        if prs:
            lines.append(locale["pr_list_header"])
            for pr in prs:
                lines.append(
                    locale["pr_item"].format(
                        title=pr.get("title", ""),
                        status=pr.get("status", "unknown"),
                    )
                )
        else:
            lines.append(locale["no_prs"])

        last_completed = binding.get("last_completed")
        if last_completed:
            lines.append(
                locale["last_completed"].format(summary=last_completed)
            )
        else:
            lines.append(locale["no_completed"])

        blocked = binding.get("blocked_items")
        if blocked:
            lines.append(locale["blocked_header"])
            if isinstance(blocked, list):
                for item in blocked:
                    lines.append(
                        locale["blocked_item"].format(item=item)
                    )
            else:
                lines.append(
                    locale["blocked_item"].format(item=str(blocked))
                )
        else:
            if not prs and not last_completed:
                lines.append(locale["no_progress"])

        lines.append(locale["footer"].format(interval="60"))
        return "\n".join(lines)