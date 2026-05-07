"""Client-side LLM instrumentation: thin async httpx wrapper.

PRIMARY observability path per RV-SPEC-014 M-001. Wraps the runtime's
HTTP client to OmniRoute / OpenRouter with timing and token extraction.
Calls ObservabilityManager.record_llm_call(...) after each request.

Requires NO OmniRoute cooperation: instrumentation is inside the
runtime's own process.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from developer_assistant.observability.observability_manager import ObservabilityManager


class LLMCallError(Exception):
    pass


class InstrumentedLLMClient:
    def __init__(
        self,
        manager: ObservabilityManager,
        omniroute_base_url: str = "https://omniroute.infinitycore.space:8443/v1",
        openrouter_base_url: str = "https://openrouter.ai/api/v1",
        omniroute_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._manager = manager
        self._omniroute_base_url = omniroute_base_url.rstrip("/")
        self._openrouter_base_url = openrouter_base_url.rstrip("/")
        self._omniroute_api_key = omniroute_api_key
        self._openrouter_api_key = openrouter_api_key
        self._timeout = timeout_seconds

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        routing_path: str = "omniroute_endpoint",
        **kwargs: Any,
    ) -> dict[str, Any]:
        if routing_path == "openrouter_endpoint":
            base_url = self._openrouter_base_url
            api_key = self._openrouter_api_key
        else:
            base_url = self._omniroute_base_url
            api_key = self._omniroute_api_key

        url = base_url + "/v1/chat/completions"
        body = {
            "model": model,
            "messages": messages,
            **kwargs,
        }
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start = time.monotonic()
        status = "success"
        error_class: Optional[str] = None
        tokens_in = 0
        tokens_out = 0
        response_data: Optional[dict[str, Any]] = None

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code >= 500:
                status = "fail"
                error_class = "provider_5xx"
                try:
                    response_data = resp.json()
                except Exception:
                    response_data = None
            elif resp.status_code >= 400:
                status = "fail"
                error_class = f"client_{resp.status_code}"
                try:
                    response_data = resp.json()
                except Exception:
                    response_data = None
            else:
                response_data = resp.json()
                usage = response_data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)

        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            status = "fail"
            error_class = "transport"

        except httpx.ReadTimeout as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            status = "fail"
            error_class = "timeout"

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            status = "fail"
            error_class = type(exc).__name__

        rate_in, rate_out = self._manager._catalog_parser.get_rate_for_model(model)
        cost_usd = (tokens_in * rate_in + tokens_out * rate_out) / 1_000_000 if status == "success" else 0.0

        self._manager.record_llm_call(
            model_id=model,
            routing_path=routing_path,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            status=status,
            error_class=error_class,
        )

        if status == "fail":
            raise LLMCallError(error_class or "unknown")

        return response_data or {}
