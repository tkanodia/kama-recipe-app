"""Provider-agnostic LLM client.

Switch between OpenAI and Anthropic by setting LLM_PROVIDER and LLM_MODEL
in the environment.  All application code should call ``llm_chat`` instead
of importing provider SDKs directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import structlog

from app.core.circuit_breaker import llm_breaker
from app.core.config import get_settings

log = structlog.get_logger()

_SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic"})

# Maps every known model slug to its provider.  When a caller passes a
# model_override, the provider is looked up here so the frontend only needs
# to send a single slug.
MODEL_REGISTRY: dict[str, str] = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "claude-opus-4-20250514": "anthropic",
    "claude-sonnet-4-20250514": "anthropic",
}

AVAILABLE_MODELS: list[dict[str, str]] = [
    {"slug": "gpt-4o", "label": "GPT-4o", "provider": "openai"},
    {"slug": "gpt-4o-mini", "label": "GPT-4o Mini", "provider": "openai"},
    {"slug": "claude-opus-4-20250514", "label": "Claude Opus 4", "provider": "anthropic"},
    {"slug": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4", "provider": "anthropic"},
]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Normalised response returned by every provider adapter."""

    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMConfigError(RuntimeError):
    """Raised when provider configuration is missing or invalid."""


def _resolve_provider_and_model(
    model_override: str | None,
) -> tuple[str, str]:
    """Return (provider, model) — using override when given, else env config."""
    settings = get_settings()

    if model_override:
        provider = MODEL_REGISTRY.get(model_override)
        if provider is None:
            raise LLMConfigError(
                f"Unknown model {model_override!r}. "
                f"Known models: {sorted(MODEL_REGISTRY)}."
            )
        return provider, model_override

    provider = settings.llm_provider.lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise LLMConfigError(
            f"Unsupported LLM_PROVIDER={provider!r}. "
            f"Must be one of {sorted(_SUPPORTED_PROVIDERS)}."
        )
    return provider, settings.resolved_llm_model


async def llm_chat(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    json_mode: bool = False,
    model_override: str | None = None,
) -> LLMResponse:
    """Send a chat completion request through the configured LLM provider.

    Parameters
    ----------
    messages:
        OpenAI-style message dicts (``{"role": ..., "content": ...}``).
        For Anthropic, the adapter strips the system message and passes it
        separately.
    max_tokens:
        Upper bound on generated tokens.
    temperature:
        Sampling temperature.
    json_mode:
        When *True*, ask the model to return valid JSON (OpenAI
        ``response_format``, Anthropic prefill hint).
    model_override:
        Specific model slug (e.g. ``"gpt-4o-mini"``).  When provided, the
        provider is inferred from ``MODEL_REGISTRY`` and the env-level
        ``LLM_PROVIDER`` / ``LLM_MODEL`` settings are ignored.
    """
    provider, model = _resolve_provider_and_model(model_override)

    if llm_breaker.is_open():
        raise RuntimeError("LLM circuit breaker is open — refusing call")

    log.debug("llm_chat_dispatch", provider=provider, model=model)

    try:
        if provider == "openai":
            response = await _openai_chat(
                messages, model=model, max_tokens=max_tokens,
                temperature=temperature, json_mode=json_mode,
            )
        else:
            response = await _anthropic_chat(
                messages, model=model, max_tokens=max_tokens,
                temperature=temperature, json_mode=json_mode,
            )

        llm_breaker.record_success()
        return response

    except (LLMConfigError, RuntimeError):
        raise
    except Exception as exc:
        llm_breaker.record_failure()
        log.error("llm_chat_failed", provider=provider, model=model, error=str(exc))
        raise


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------

async def _openai_chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> LLMResponse:
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMConfigError(
            "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    choice = response.choices[0]

    usage: dict[str, int] = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }

    return LLMResponse(
        text=choice.message.content or "",
        model=response.model,
        usage=usage,
    )


async def _anthropic_chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> LLMResponse:
    from anthropic import AsyncAnthropic

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMConfigError(
            "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Anthropic expects a separate ``system`` param, not a system message in
    # the messages list.
    system_text: str | None = None
    filtered: list[dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            filtered.append(msg)

    # Nudge the model toward JSON when requested.
    if json_mode and filtered and filtered[-1]["role"] == "user":
        filtered[-1] = {
            **filtered[-1],
            "content": filtered[-1]["content"] + "\n\nRespond with valid JSON only.",
        }

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": filtered,
    }
    if system_text:
        kwargs["system"] = system_text

    response = await client.messages.create(**kwargs)

    text = response.content[0].text if response.content else ""

    usage = {
        "prompt_tokens": response.usage.input_tokens,
        "completion_tokens": response.usage.output_tokens,
    }

    return LLMResponse(text=text, model=response.model, usage=usage)


# ---------------------------------------------------------------------------
# Streaming adapters
# ---------------------------------------------------------------------------

async def llm_chat_stream(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    json_mode: bool = False,
    model_override: str | None = None,
) -> AsyncIterator[str]:
    """Stream chat completion tokens as they arrive."""
    provider, model = _resolve_provider_and_model(model_override)

    if llm_breaker.is_open():
        raise RuntimeError("LLM circuit breaker is open — refusing call")

    log.debug("llm_chat_stream_dispatch", provider=provider, model=model)

    try:
        if provider == "openai":
            async for chunk in _openai_chat_stream(
                messages, model=model, max_tokens=max_tokens,
                temperature=temperature, json_mode=json_mode,
            ):
                yield chunk
        else:
            async for chunk in _anthropic_chat_stream(
                messages, model=model, max_tokens=max_tokens,
                temperature=temperature, json_mode=json_mode,
            ):
                yield chunk

        llm_breaker.record_success()
    except (LLMConfigError, RuntimeError):
        raise
    except Exception as exc:
        llm_breaker.record_failure()
        log.error("llm_chat_stream_failed", provider=provider, model=model, error=str(exc))
        raise


async def _openai_chat_stream(
    messages: list[dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> AsyncIterator[str]:
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMConfigError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    stream = await client.chat.completions.create(**kwargs)
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


async def _anthropic_chat_stream(
    messages: list[dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> AsyncIterator[str]:
    from anthropic import AsyncAnthropic

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMConfigError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    system_text: str | None = None
    filtered: list[dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            filtered.append(msg)

    if json_mode and filtered and filtered[-1]["role"] == "user":
        filtered[-1] = {
            **filtered[-1],
            "content": filtered[-1]["content"] + "\n\nRespond with valid JSON only.",
        }

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": filtered,
    }
    if system_text:
        kwargs["system"] = system_text

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text
