from __future__ import annotations

import os
import threading
from typing import Callable, Optional

_ENABLED = os.environ.get("DEV_ASSIST_ADVISORY_NARRATIVE_ENABLED", "true").lower() in ("true", "1", "yes")
_TIMEOUT = int(os.environ.get("DEV_ASSIST_ADVISORY_NARRATIVE_TIMEOUT_SECONDS", "10"))


def generate_advisory_narrative(
    rule_id: str,
    cite: str,
    context: str,
    proposed_action: str,
    dispatcher: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    if not _ENABLED:
        return None
    if dispatcher is None:
        return None
    prompt = (
        f"Правило эскалации: {rule_id}\n"
        f"Обоснование: {cite}\n"
        f"Контекст: {context}\n"
        f"Планируемое действие: {proposed_action}\n"
        "Напиши краткий叙事 на русском языке для основателя, объясняющий,"
        " почему это действие было заблокировано и что нужно решить."
    )
    result: list[Optional[str]] = [None]
    error: list[Optional[Exception]] = [None]

    def _call() -> None:
        try:
            result[0] = dispatcher(prompt)
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=_TIMEOUT)
    if t.is_alive() or error[0] is not None:
        return None
    return result[0]
