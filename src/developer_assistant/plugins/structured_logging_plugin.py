"""Hermes plugin entry point for structured logging initialization.

Per HERMES-RUNTIME-CONTRACT.md § 11.3, plugins are Python packages
installed into the Hermes virtualenv.  This plugin:

1. Calls init_runtime_logger() on import/load.
2. Constructs ObservabilityManager.from_env(catalog_parser) and
   calls await manager.start().
3. Wires ObservabilityManager.set_work_item_context into the
   work-item dequeue path.

Importable as a flat module; the install script (TKT-020/021) wires
the path.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from developer_assistant.observability.structured_logger import (
    init_runtime_logger,
    set_manager,
    work_item,
)
from developer_assistant.observability.observability_manager import ObservabilityManager

_manager: Optional[ObservabilityManager] = None


def load() -> None:
    init_runtime_logger()


async def startup(catalog_parser: Any = None) -> ObservabilityManager:
    global _manager
    if _manager is not None:
        return _manager
    if catalog_parser is None:
        catalog_parser = _StubCatalogParser()
    _manager = ObservabilityManager.from_env(catalog_parser)
    await _manager.start()
    set_manager(_manager)
    return _manager


async def shutdown() -> None:
    global _manager
    if _manager is not None:
        await _manager.stop()
        _manager = None


class _StubCatalogParser:
    def get_role_assignment(self, role: str) -> Any:
        return None

    def get_rate_for_model(self, model_id: str) -> tuple[float, float]:
        return (0.0, 0.0)


def dequeue_wrapper(work_item_id: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
    if _manager is not None:
        _manager.set_work_item_context(work_item_id)
    with work_item(work_item_id):
        try:
            return fn(*args, **kwargs)
        finally:
            if _manager is not None:
                _manager.clear_work_item_context()
