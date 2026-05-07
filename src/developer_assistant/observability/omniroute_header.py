"""OmniRoute header injector: adds X-DEVASSIST-Work-Item-Id to outbound HTTP.

When the work_item_id contextvar is set (inside a structured_logger.work_item
block), this module injects the header into outbound LLM HTTP requests.
OmniRoute middleware (TKT-031) reads this header.

Usage as httpx event hook::

    client = httpx.AsyncClient(event_hooks={"request": [inject_work_item_header]})

Usage as standalone wrapper::

    headers = build_headers_with_work_item(existing_headers)
"""

from __future__ import annotations

from typing import Any, MutableMapping

from developer_assistant.observability.structured_logger import _WORK_ITEM_ID

_HEADER_NAME = "X-DEVASSIST-Work-Item-Id"


def inject_work_item_header(request: Any) -> None:
    """Sync httpx request event hook; valid for both sync and async clients."""
    wid = _WORK_ITEM_ID.get()
    if wid is not None:
        request.headers[_HEADER_NAME] = wid


def build_headers_with_work_item(
    headers: MutableMapping[str, str],
) -> MutableMapping[str, str]:
    """Return headers dict with X-DEVASSIST-Work-Item-Id added when contextvar is set."""
    wid = _WORK_ITEM_ID.get()
    if wid is not None:
        headers[_HEADER_NAME] = wid
    return headers
