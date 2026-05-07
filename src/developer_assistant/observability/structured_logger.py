"""Structured JSON-line logging with work_item_id contextvar propagation.

Implements OBSERVABILITY-CONTRACT.md v0.1.1 § 4 (FR-OBS-01) and
§ 5 (FR-OBS-02).  Every log line is a single JSON object carrying
the mandatory fields: ts_iso, level, runtime_role, work_item_id,
model, tokens_in, tokens_out, latency_ms, event, message.

Public API:
  get_logger(name)              – return a logger with JSON formatter
  work_item(work_item_id)       – context manager for work_item_id
  instrument_llm_call(model_id) – decorator for LLM call functions
  init_runtime_logger()         – one-time root-logger init
  dispatch_in_thread(fn, ...)   – contextvars-aware thread helper

Extra-field convention:
  Callers pass extra={"event": "some.event", "_extra_payload": {key: val}}
  to include additional fields in the JSON log line.  Fields in
  _extra_payload that match mandatory field names override defaults;
  other fields are appended as-is.  Do NOT place structured data
  directly in extra={} as Python logging reserves certain attribute
  names and will silently drop them.

Note on runtime_role default:
  When DEVASSIST_RUNTIME_ROLE is unset this module defaults to "unknown",
  while ObservabilityManager.from_env() defaults to "executor".  This
  intentional discrepancy means a JSON log line and a SQLite row may
  disagree on runtime_role when the env var is missing; "unknown" is
  preferred here because it accurately signals misconfiguration.
"""

from __future__ import annotations

import contextvars
import datetime
import functools
import inspect
import json
import logging
import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional, TypeVar

_WORK_ITEM_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_devassist_work_item_id", default=None
)

_RUNTIME_ROLE_ENV = "DEVASSIST_RUNTIME_ROLE"
_LOGGER_PREFIX = "devassist"

_RUNTIME_ROLE_WARNED: bool = False
_COST_WARNED: bool = False
_INIT_DONE: bool = False

_MANAGER: Any = None

_MANDATORY_FIELDS = (
    "ts_iso",
    "level",
    "runtime_role",
    "work_item_id",
    "model",
    "tokens_in",
    "tokens_out",
    "latency_ms",
    "event",
    "message",
)


def _get_runtime_role() -> str:
    global _RUNTIME_ROLE_WARNED
    role = os.environ.get(_RUNTIME_ROLE_ENV)
    if role:
        return role
    if not _RUNTIME_ROLE_WARNED:
        _RUNTIME_ROLE_WARNED = True
        _bare_logger = logging.getLogger(f"{_LOGGER_PREFIX}.structured")
        _bare_logger.warning(
            "runtime_role env var %s is unset",
            _RUNTIME_ROLE_ENV,
            extra={"event": "runtime_role_missing"},
        )
    return "unknown"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        ts_iso = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

        level = record.levelname.lower()
        if level == "warning":
            level = "warn"
        elif level == "critical":
            level = "fatal"

        base: dict[str, Any] = {
            "ts_iso": ts_iso,
            "level": level,
            "runtime_role": _get_runtime_role(),
            "work_item_id": _WORK_ITEM_ID.get(),
            "model": None,
            "tokens_in": None,
            "tokens_out": None,
            "latency_ms": None,
            "event": getattr(record, "event", None) or record.getMessage(),
            "message": record.getMessage(),
        }

        extra = getattr(record, "_extra_payload", None)
        if extra and isinstance(extra, dict):
            for k, v in extra.items():
                if k not in base:
                    base[k] = v
                elif k in _MANDATORY_FIELDS:
                    base[k] = v

        return json.dumps(base, default=str, ensure_ascii=False)


class _JsonLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(_JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except Exception:
            self.handleError(record)


def init_runtime_logger() -> None:
    global _INIT_DONE
    if _INIT_DONE:
        return
    _INIT_DONE = True
    root = logging.getLogger(_LOGGER_PREFIX)
    root.setLevel(logging.DEBUG)
    handler = _JsonLogHandler()
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    if not name.startswith(_LOGGER_PREFIX):
        full_name = f"{_LOGGER_PREFIX}.{name}"
    else:
        full_name = name
    logger = logging.getLogger(full_name)
    return logger


@contextmanager
def work_item(work_item_id: str):
    token = _WORK_ITEM_ID.set(work_item_id)
    try:
        yield
    finally:
        _WORK_ITEM_ID.reset(token)


def dispatch_in_thread(fn: Callable, *args: Any, **kwargs: Any) -> Any:
    result_box: list[Any] = [None]
    exc_box: list[Optional[BaseException]] = [None]

    def _runner() -> None:
        try:
            result_box[0] = fn(*args, **kwargs)
        except BaseException as exc:
            exc_box[0] = exc

    ctx = contextvars.copy_context()
    t = threading.Thread(target=ctx.run, args=(_runner,))
    t.start()
    t.join()
    if exc_box[0] is not None:
        raise exc_box[0]
    return result_box[0]


def _extract_tokens(response: Any) -> tuple[Optional[int], Optional[int]]:
    if isinstance(response, dict):
        usage = response.get("usage")
        if isinstance(usage, dict):
            return usage.get("prompt_tokens"), usage.get("completion_tokens")
        if "tokens_in" in response and "tokens_out" in response:
            return response["tokens_in"], response["tokens_out"]
    usage_obj = getattr(response, "usage", None)
    if usage_obj is not None:
        return getattr(usage_obj, "prompt_tokens", None), getattr(
            usage_obj, "completion_tokens", None
        )
    return None, None


def _compute_cost(model_id: str, tokens_in: Optional[int], tokens_out: Optional[int]) -> float:
    global _COST_WARNED
    if _MANAGER is not None and hasattr(_MANAGER, "_catalog_parser"):
        try:
            rate_in, rate_out = _MANAGER._catalog_parser.get_rate_for_model(model_id)
            ti = tokens_in or 0
            to = tokens_out or 0
            return (ti * rate_in + to * rate_out) / 1_000_000
        except Exception:
            pass
    if not _COST_WARNED:
        _COST_WARNED = True
        logger = get_logger("structured")
        logger.warning(
            "ObservabilityManager not available; cost_usd defaults to 0.0",
            extra={"event": "cost_computation_unavailable"},
        )
    return 0.0


F = TypeVar("F", bound=Callable)


def instrument_llm_call(model_id: str) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                logger = get_logger("structured.llm")
                logger.info(
                    "llm call start",
                    extra={
                        "event": "llm.call.start",
                        "_extra_payload": {
                            "model": model_id,
                        },
                    },
                )
                start = time.monotonic()
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    latency_ms = int((time.monotonic() - start) * 1000)
                    logger.error(
                        "llm call failed",
                        extra={
                            "event": "llm.call.fail",
                            "_extra_payload": {
                                "model": model_id,
                                "latency_ms": latency_ms,
                                "error_class": type(exc).__name__,
                            },
                        },
                    )
                    raise
                latency_ms = int((time.monotonic() - start) * 1000)
                tokens_in, tokens_out = _extract_tokens(result)
                cost_usd = _compute_cost(model_id, tokens_in, tokens_out)
                logger.info(
                    "llm call complete",
                    extra={
                        "event": "llm.call.complete",
                        "_extra_payload": {
                            "model": model_id,
                            "tokens_in": tokens_in,
                            "tokens_out": tokens_out,
                            "latency_ms": latency_ms,
                            "cost_usd": cost_usd,
                        },
                    },
                )
                return result

            return async_wrapper  # type: ignore[return-value]

        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                logger = get_logger("structured.llm")
                logger.info(
                    "llm call start",
                    extra={
                        "event": "llm.call.start",
                        "_extra_payload": {
                            "model": model_id,
                        },
                    },
                )
                start = time.monotonic()
                try:
                    result = fn(*args, **kwargs)
                except Exception as exc:
                    latency_ms = int((time.monotonic() - start) * 1000)
                    logger.error(
                        "llm call failed",
                        extra={
                            "event": "llm.call.fail",
                            "_extra_payload": {
                                "model": model_id,
                                "latency_ms": latency_ms,
                                "error_class": type(exc).__name__,
                            },
                        },
                    )
                    raise
                latency_ms = int((time.monotonic() - start) * 1000)
                tokens_in, tokens_out = _extract_tokens(result)
                cost_usd = _compute_cost(model_id, tokens_in, tokens_out)
                logger.info(
                    "llm call complete",
                    extra={
                        "event": "llm.call.complete",
                        "_extra_payload": {
                            "model": model_id,
                            "tokens_in": tokens_in,
                            "tokens_out": tokens_out,
                            "latency_ms": latency_ms,
                            "cost_usd": cost_usd,
                        },
                    },
                )
                return result

            return sync_wrapper  # type: ignore[return-value]

    return decorator


def set_manager(manager: Any) -> None:
    global _MANAGER
    _MANAGER = manager
