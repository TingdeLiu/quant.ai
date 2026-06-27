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


ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"


def generate_chat_reply(
    config: LLMConfig, system: str, messages: list[dict[str, str]]
) -> tuple[str | None, dict[str, Any]]:
    """Multi-turn research chat reply grounded in the supplied market context.

    Prefers Anthropic/Claude — set ``ANTHROPIC_API_KEY`` and it just works, with no
    config change. Falls back to an OpenAI-compatible endpoint only when ``llm`` is
    explicitly enabled and that key is present (so a stray ``OPENAI_API_KEY`` never
    triggers surprise calls). Returns ``(None, metadata)`` when no provider is
    reachable so the caller can serve a deterministic offline answer instead.

    ``messages`` is the running conversation as ``[{"role": "user"|"assistant",
    "content": str}, ...]``. Research commentary only — order-ticket style output is
    blocked, mirroring the other helpers in this module.
    """
    provider = (config.provider or "").lower()
    metadata: dict[str, Any] = {"prompt_version": f"chat::{config.prompt_version}"}

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key and ("anthropic" in provider or "claude" in provider):
        anthropic_key = os.environ.get(config.api_key_env)

    if anthropic_key:
        model = config.model if config.model.lower().startswith("claude") else DEFAULT_ANTHROPIC_MODEL
        metadata.update({"provider": "anthropic", "model": model})
        text, status = _anthropic_chat(model, system, messages, anthropic_key)
        return _guard_chat(text, status, metadata)

    if config.enabled and "anthropic" not in provider:
        openai_key = os.environ.get(config.api_key_env)
        if openai_key:
            metadata.update({"provider": config.provider, "model": config.model})
            text, status = _openai_chat(config.model, system, messages, openai_key, config.endpoint)
            return _guard_chat(text, status, metadata)

    metadata["status"] = "no_api_key"
    return None, metadata


def _guard_chat(
    text: str | None, status: str, metadata: dict[str, Any]
) -> tuple[str | None, dict[str, Any]]:
    if text is None:
        metadata["status"] = status
        return None, metadata
    if any(term in text.lower() for term in DISALLOWED_REVIEW_TERMS):
        metadata["status"] = "blocked_disallowed_review_terms"
        return None, metadata
    metadata["status"] = "ok"
    return text, metadata


def _anthropic_chat(
    model: str, system: str, messages: list[dict[str, str]], api_key: str
) -> tuple[str | None, str]:
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
    }
    request = urllib.request.Request(
        ANTHROPIC_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None, "request_failed"
    text = _extract_anthropic_text(body)
    return (text, "ok") if text else (None, "empty_response")


def _openai_chat(
    model: str, system: str, messages: list[dict[str, str]], api_key: str, endpoint: str | None
) -> tuple[str | None, str]:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in messages],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        endpoint or "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None, "request_failed"
    text = _extract_text(body)
    return (text, "ok") if text else (None, "empty_response")


def _extract_text(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "")
    return str(content).strip()


def _extract_anthropic_text(body: dict[str, Any]) -> str:
    blocks = body.get("content")
    if not isinstance(blocks, list):
        return ""
    parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "".join(parts).strip()
