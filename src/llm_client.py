"""
llm_client.py
-------------
Optional LLM integration for rewriting the weekly management report.

Supports Anthropic Claude and OpenAI. Provider is chosen from:
  * LLM_PROVIDER=anthropic|openai  (optional override)
  * otherwise first available API key (Anthropic preferred)

The analytics numbers always come from the rule-based report passed in
the prompt — the LLM only improves narrative fluency.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 2500


def resolve_provider() -> str | None:
    """Return 'anthropic', 'openai', or None if no usable key is set."""
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if explicit == "anthropic":
        return "anthropic" if has_anthropic else None
    if explicit == "openai":
        return "openai" if has_openai else None
    if has_anthropic:
        return "anthropic"
    if has_openai:
        return "openai"
    return None


def model_for_provider(provider: str) -> str:
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def is_llm_configured() -> bool:
    return resolve_provider() is not None


def llm_status() -> dict:
    """Small status dict for the dashboard UI."""
    provider = resolve_provider()
    if not provider:
        return {"configured": False, "provider": None, "model": None}
    return {
        "configured": True,
        "provider": provider,
        "model": model_for_provider(provider),
    }


def complete(user_prompt: str) -> str:
    """
    Send a prompt to the configured LLM provider and return the text response.
    Raises RuntimeError on configuration or API errors.
    """
    provider = resolve_provider()
    if not provider:
        raise RuntimeError("No LLM API key configured")

    if provider == "anthropic":
        return _complete_anthropic(user_prompt)
    return _complete_openai(user_prompt)


def _max_tokens() -> int:
    raw = os.getenv("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))
    try:
        return max(500, int(raw))
    except ValueError:
        return DEFAULT_MAX_TOKENS


def _complete_anthropic(prompt: str) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package is not installed — run: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=model_for_provider("anthropic"),
        max_tokens=_max_tokens(),
        messages=[{"role": "user", "content": prompt}],
    )
    block = response.content[0]
    text = getattr(block, "text", None)
    if not text:
        raise RuntimeError("Empty response from Anthropic")
    return text.strip()


def _openai_max_tokens_param(model: str, max_tokens: int) -> dict:
    """GPT-5.x models use max_completion_tokens instead of max_tokens."""
    if model.startswith("gpt-5") or model.startswith("o"):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _complete_openai(prompt: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai package is not installed — run: pip install openai"
        ) from exc

    model = model_for_provider("openai")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **_openai_max_tokens_param(model, _max_tokens()),
    )
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("Empty response from OpenAI")
    return text.strip()
