"""In-process adapter registry per UPSTREAM-ADAPTER-CONTRACT.md §5.

Maps adapter_id to adapter implementation.
v0.1 has exactly one entry: 'telegram'.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Tuple

from developer_assistant.upstream_adapters.base import UpstreamAdapter

logger = logging.getLogger(__name__)


class AdapterNotFoundError(Exception):
    """Raised when get() is called with an unregistered adapter_id."""

    def __init__(self, adapter_id: str) -> None:
        self.adapter_id = adapter_id
        super().__init__(f"Adapter not registered: {adapter_id!r}")


class DuplicateAdapterError(Exception):
    """Raised when register() is called with an already-registered adapter_id."""

    def __init__(self, adapter_id: str) -> None:
        self.adapter_id = adapter_id
        super().__init__(f"Adapter already registered: {adapter_id!r}")


class AdapterRegistry:
    """In-process registry that maps adapter_id to UpstreamAdapter impl.

    Registration order is preserved for iter_adapters().
    """

    def __init__(self) -> None:
        self._adapters: list[Tuple[str, UpstreamAdapter]] = []
        self._ids: set[str] = set()

    def register(self, adapter_id: str, impl: UpstreamAdapter) -> None:
        """Register an adapter implementation under the given adapter_id.

        Raises:
            DuplicateAdapterError: if adapter_id is already registered.
        """
        if adapter_id in self._ids:
            raise DuplicateAdapterError(adapter_id)
        self._ids.add(adapter_id)
        self._adapters.append((adapter_id, impl))
        logger.info("adapter_registered", extra={"adapter_id": adapter_id})

    def get(self, adapter_id: str) -> UpstreamAdapter:
        """Look up an adapter by adapter_id.

        Raises:
            AdapterNotFoundError: if adapter_id is not registered.
        """
        for aid, impl in self._adapters:
            if aid == adapter_id:
                return impl
        raise AdapterNotFoundError(adapter_id)

    def iter_adapters(self) -> Iterator[Tuple[str, UpstreamAdapter]]:
        """Yield (adapter_id, impl) pairs in registration order."""
        yield from self._adapters

    def has(self, adapter_id: str) -> bool:
        """Return True if adapter_id is registered."""
        return adapter_id in self._ids
