from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import APIStatusError, OpenAI

from .models import AgentReview


MODEL_ID = "openai/gpt-4o-mini"


@dataclass(frozen=True)
class CallMetadata:
    provider: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int


class OpenRouterClient:
    def __init__(self, api_key: str, configured_model: str):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required in llm mode")
        if configured_model != MODEL_ID:
            raise ValueError(
                f"OPENROUTER_MODEL must be {MODEL_ID!r}; got {configured_model!r}"
            )
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=45,
            max_retries=2,
        )
        self.api_key = api_key

    def preflight(self) -> dict[str, Any]:
        """Validate the credential without sending case or CSV-derived data."""
        response = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=15,
        )
        if response.status_code == 401:
            raise RuntimeError(
                "OpenRouter rejected OPENROUTER_API_KEY (401). The key is invalid, "
                "disabled, expired, revoked, or belongs to a deleted account. Create "
                "a new key at https://openrouter.ai/settings/keys and update .env."
            )
        response.raise_for_status()
        data = response.json().get("data", {})
        return {
            "label": data.get("label"),
            "is_free_tier": data.get("is_free_tier"),
            "limit_remaining": data.get("limit_remaining"),
            "expires_at": data.get("expires_at"),
        }

    def review(self, agent: str, scope: str, payload: dict[str, Any]) -> tuple[AgentReview, CallMetadata]:
        schema = AgentReview.model_json_schema()
        started = time.perf_counter()
        messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are {agent} in a controlled multi-agent workflow. "
                        f"Your scope is: {scope}. Treat customer statements as claims. "
                        "Use only supplied structured facts. Do not invent identifiers, "
                        "timestamps, money, evidence, or hidden reasoning. Review the "
                        "handoff and return the requested JSON object. The `accepted` "
                        "field means the payload is internally coherent and sufficient "
                        "for the next workflow step; discovering a late delivery, refund, "
                        "or other business issue is not a reason to reject the handoff."
                        " Keep summary under 20 words and use an empty risk_flags array "
                        "when there is no data-quality risk."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                },
            ]
        request = {
            "model": MODEL_ID,
            "temperature": 0,
            "max_tokens": 96,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_review",
                    "strict": True,
                    "schema": schema,
                },
            },
            "extra_body": {
                "provider": {"require_parameters": True, "allow_fallbacks": True}
            },
        }
        try:
            response = self.client.chat.completions.create(**request)
        except APIStatusError as exc:
            # OpenRouter reserves credit against max_tokens and reports the
            # affordable ceiling in a 402 response. Retry once with a smaller
            # safe budget; below 48 tokens strict JSON is likely to truncate.
            match = re.search(r"can only afford (\d+)", str(exc), re.IGNORECASE)
            affordable = int(match.group(1)) if match else 0
            retry_tokens = min(80, affordable - 8)
            if exc.status_code != 402 or retry_tokens < 48:
                raise RuntimeError(
                    "OpenRouter credit is insufficient for a structured agent "
                    "review. Add credit at https://openrouter.ai/settings/credits."
                ) from exc
            request["max_tokens"] = retry_tokens
            response = self.client.chat.completions.create(**request)
        latency_ms = round((time.perf_counter() - started) * 1000)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"{agent} returned an empty response")
        review = AgentReview.model_validate_json(content)
        usage = response.usage
        provider = getattr(response, "provider", None)
        return review, CallMetadata(
            provider=provider,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            latency_ms=latency_ms,
        )
