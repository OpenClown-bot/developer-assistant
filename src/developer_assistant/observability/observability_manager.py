"""ObservabilityManager: owns store writes, health endpoint, and logger context.

Implements OBSERVABILITY-CONTRACT.md v0.1.1 § 14.
Instantiated once per Hermes runtime at startup. Owns the
observability_store write path, the per-runtime health-endpoint lifecycle,
and the structured-logging context (work_item_id propagation).
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Optional, Protocol

from developer_assistant.observability.health_endpoint import HealthEndpoint
from developer_assistant.smoke_inject import (
    DEFAULT_MARKER_FILE_PATH,
    DEFAULT_REPO_ROOT,
)
from developer_assistant.state.observability_store import (
    ensure_wal_mode,
    record_error as _store_record_error,
    record_llm_call as _store_record_llm_call,
)

_HEALTH_PORT_DEFAULTS: dict[str, int] = {
    "orchestrator": 8181,
    "business-planner": 8182,
    "architect": 8183,
    "executor": 8184,
    "reviewer": 8185,
}


class CatalogParserProtocol(Protocol):
    def get_role_assignment(self, role: str) -> Any: ...


    def get_rate_for_model(self, model_id: str) -> tuple[float, float]:
        """Return (rate_in_per_1m_usd, rate_out_per_1m_usd) for a model."""
        ...


class ObservabilityManager:
    def __init__(
        self,
        runtime_role: str,
        operational_db_path: str,
        health_endpoint_port: int,
        catalog_parser: CatalogParserProtocol,
        repo_root: Optional[str] = None,
        marker_file_path: str = DEFAULT_MARKER_FILE_PATH,
        loaded_skills: Optional[frozenset[str]] = None,
    ) -> None:
        self._runtime_role = runtime_role
        self._db_path = operational_db_path
        self._health_port = health_endpoint_port
        self._catalog_parser = catalog_parser
        self._db: Optional[sqlite3.Connection] = None
        self._health: Optional[HealthEndpoint] = None
        self._work_item_id: Optional[str] = None
        self._current_model: Optional[str] = None
        self._started = False
        self._repo_root = repo_root or os.environ.get(
            "DEVASSIST_REPO_ROOT", DEFAULT_REPO_ROOT,
        )
        self._marker_file_path = marker_file_path
        self._loaded_skills = loaded_skills

    @classmethod
    def from_env(cls, catalog_parser: CatalogParserProtocol) -> "ObservabilityManager":
        role = os.environ.get("DEVASSIST_RUNTIME_ROLE", "executor")
        db_path = os.environ.get(
            "DEVASSIST_OPERATIONAL_DB", "/srv/devassist/state/operational.db"
        )
        port_str = os.environ.get("DEVASSIST_HEALTH_PORT", "")
        if port_str:
            port = int(port_str)
        else:
            port = _HEALTH_PORT_DEFAULTS.get(role, 8184)
        repo_root = os.environ.get("DEVASSIST_REPO_ROOT", DEFAULT_REPO_ROOT)
        marker = os.environ.get(
            "DEVASSIST_SMOKE_MODE_MARKER_PATH", DEFAULT_MARKER_FILE_PATH,
        )
        return cls(
            role, db_path, port, catalog_parser,
            repo_root=repo_root, marker_file_path=marker,
        )

    async def start(self) -> None:
        if self._started:
            return
        self._db = sqlite3.connect(self._db_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        ensure_wal_mode(self._db)

        self._health = HealthEndpoint(
            self._runtime_role,
            self._health_port,
            self._db_path,
            repo_root=self._repo_root,
            marker_file_path=self._marker_file_path,
            loaded_skills=self._loaded_skills,
        )
        await self._health.start()
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        if self._health is not None:
            await self._health.stop()
            self._health = None
        if self._db is not None:
            self._db.close()
            self._db = None
        self._started = False

    def set_work_item_context(self, work_item_id: Optional[str]) -> None:
        self._work_item_id = work_item_id
        if self._health is not None:
            self._health.set_current_work_item(work_item_id)

    def clear_work_item_context(self) -> None:
        self._work_item_id = None
        if self._health is not None:
            self._health.set_current_work_item(None)
            self._health.set_current_model(None)

    def record_llm_call(
        self,
        model_id: str,
        routing_path: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        cost_usd: float,
        status: str,
        error_class: Optional[str] = None,
    ) -> None:
        if self._db is None:
            return
        try:
            rate_in, rate_out = 0.0, 0.0
            try:
                rate_in, rate_out = self._catalog_parser.get_rate_for_model(model_id)
            except Exception:
                pass
            _store_record_llm_call(
                self._db,
                role=self._runtime_role,
                work_item_id=self._work_item_id,
                model_id=model_id,
                routing_path=routing_path,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                rate_in_per_1m_usd=rate_in,
                rate_out_per_1m_usd=rate_out,
                cost_usd=cost_usd,
                status=status,
                error_class=error_class,
            )
            self._current_model = model_id
            if self._health is not None:
                self._health.set_current_model(model_id)
        except Exception:
            pass

    def record_error(
        self,
        kind: str,
        message: str,
        stack: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        if self._db is None:
            return
        try:
            _store_record_error(
                self._db,
                role=self._runtime_role,
                kind=kind,
                message=message,
                work_item_id=self._work_item_id,
                stack=stack,
                context=context,
            )
        except Exception:
            pass
