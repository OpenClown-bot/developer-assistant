"""Upstream adapter abstraction package per UPSTREAM-ADAPTER-CONTRACT.md v0.1.0.

Exports:
    UpstreamAdapter — abstract base class
    AdapterRegistry — in-process adapter registry
    TelegramAdapter — v0.1 Telegram adapter
    Router — outbound routing helper
"""

from developer_assistant.upstream_adapters.base import UpstreamAdapter
from developer_assistant.upstream_adapters.registry import AdapterRegistry
from developer_assistant.upstream_adapters.router import Router
from developer_assistant.upstream_adapters.telegram import TelegramAdapter

__all__ = [
    "UpstreamAdapter",
    "AdapterRegistry",
    "TelegramAdapter",
    "Router",
]
