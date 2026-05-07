"""Shared Telegram message utilities.

Provides paginate_text() — a line-boundary-aware text splitter used by both
the /status command handler and the daily-digest delivery module.
"""

from __future__ import annotations


def paginate_text(text: str, max_len: int = 4096) -> list[str]:
    """Split text at line boundaries when it exceeds max_len.

    Each part is prefixed with "(part N/M)\\n" when there are multiple parts.
    When the text fits in a single message, returns [text] with no prefix.
    """
    if len(text) <= max_len:
        return [text]

    line_parts = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in line_parts:
        added_len = len(line) + 1
        if current_len + added_len > max_len and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = added_len
        else:
            current.append(line)
            current_len += added_len

    if current:
        chunks.append("\n".join(current))

    total = len(chunks)
    result: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        prefix = f"(part {i}/{total})\n"
        result.append(prefix + chunk)
    return result
