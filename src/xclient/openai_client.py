"""OpenAI SDK boundary used by the xclient CLI.

This module is intentionally thin: it constructs the official OpenAI SDK client
and calls the SDK's chat completions API without inspecting raw HTTP responses
or reimplementing OpenAI protocol behavior.
"""

from __future__ import annotations

from typing import Any


def create_openai_client(
    *,
    base_url: str,
    api_key: str,
    timeout: float | None,
) -> Any:
    """Constructs an OpenAI SDK client for the selected Gateway endpoint.

    The caller owns selecting configuration from CLI flags or environment
    variables. This wrapper exists so tests can verify SDK construction without
    making network calls or depending on OpenAI SDK internals.
    """
    openai_class = _load_openai_client_class()
    kwargs: dict[str, object] = {
        "api_key": api_key,
        "base_url": base_url,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return openai_class(**kwargs)


def create_chat_completion(
    client: Any,
    *,
    model: str,
    message: str,
    stream: bool,
) -> object:
    """Delegates chat completion creation to the official OpenAI SDK.

    The SDK is the compatibility boundary for request construction, protocol
    handling, response parsing, and streaming iteration.
    """
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message}],
        stream=stream,
    )


def is_openai_sdk_exception(error: BaseException) -> bool:
    """Reports whether `error` is an exception raised by the OpenAI SDK."""
    try:
        import openai
    except ModuleNotFoundError:
        return False
    return isinstance(error, openai.OpenAIError)


def _load_openai_client_class() -> type[Any]:
    """Imports the official OpenAI SDK only when a request is executed."""
    from openai import OpenAI

    return OpenAI
