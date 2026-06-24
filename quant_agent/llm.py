from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any

from quant_agent.config import LLMConfig

DISALLOWED_REVIEW_TERMS = ["buy order", "sell order", "submit order", "broker order", "market order"]


def generate_llm_review(config: LLMConfig, prompt: str) -> tuple[str | None, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "enabled": config.enabled,
        "provider": config.provider,
        "model": config.model,
        "prompt_version": config.prompt_version,
        "input_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }
    if not config.enabled:
        metadata["status"] = "disabled"
        return None, metadata

    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        metadata["status"] = f"missing_api_key_env:{config.api_key_env}"
        return None, metadata

    endpoint = config.endpoint or "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a quant research reviewer. Produce research commentary only. "
                    "Do not provide broker instructions, order tickets, or live trading authorization."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        metadata["status"] = "request_failed"
        metadata["error"] = str(exc)
        return None, metadata

    text = _extract_text(body)
    if not text:
        metadata["status"] = "empty_response"
        return None, metadata
    lowered = text.lower()
    if any(term in lowered for term in DISALLOWED_REVIEW_TERMS):
        metadata["status"] = "blocked_disallowed_review_terms"
        return None, metadata
    metadata["status"] = "ok"
    metadata["output_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, metadata


def generate_market_narrative(config: LLMConfig, prompt: str) -> tuple[str | None, dict[str, Any]]:
    """Synthesize a daily US market research narrative.

    Mirrors ``generate_llm_review``: offline by default, falls back silently when
    the API key is missing or the request fails, and blocks broker/order style
    output. Used only to turn already-collected news and quant metrics into a
    readable research commentary, never to authorize trades.
    """
    metadata: dict[str, Any] = {
        "enabled": config.enabled,
        "provider": config.provider,
        "model": config.model,
        "prompt_version": f"market_narrative::{config.prompt_version}",
        "input_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }
    if not config.enabled:
        metadata["status"] = "disabled"
        return None, metadata

    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        metadata["status"] = f"missing_api_key_env:{config.api_key_env}"
        return None, metadata

    endpoint = config.endpoint or "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a US equity research analyst. Using ONLY the provided news headlines "
                    "and quantitative metrics, write a concise daily market research briefing in "
                    "Chinese. Clearly separate relatively favorable research candidates from elevated-risk "
                    "names, and always explain the reasoning from the supplied data. Do not invent prices, "
                    "facts, or sources. This is research commentary only: never provide broker instructions, "
                    "order tickets, position sizing directives, or live trading authorization."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        metadata["status"] = "request_failed"
        metadata["error"] = str(exc)
        return None, metadata

    text = _extract_text(body)
    if not text:
        metadata["status"] = "empty_response"
        return None, metadata
    lowered = text.lower()
    if any(term in lowered for term in DISALLOWED_REVIEW_TERMS):
        metadata["status"] = "blocked_disallowed_review_terms"
        return None, metadata
    metadata["status"] = "ok"
    metadata["output_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, metadata


def _extract_text(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "")
    return str(content).strip()
