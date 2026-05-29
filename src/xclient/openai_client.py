"""OpenAI SDK boundary used by the xclient CLI.

This module is intentionally thin: it constructs the official OpenAI SDK client
and calls the SDK's chat completions API without inspecting raw HTTP responses
or reimplementing OpenAI protocol behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def create_openai_client(
    *,
    base_url: str,
    api_key: str,
    timeout: float | None,
    default_headers: Mapping[str, str] | None = None,
) -> Any:
    """Constructs an OpenAI SDK client for the selected Gateway endpoint.

    The caller owns selecting configuration from CLI flags or environment
    variables. This wrapper exists so tests can verify SDK construction without
    making network calls or depending on OpenAI SDK internals.

    Args:
        base_url: Gateway base URL such as ``http://localhost:30352/v1``.
        api_key: Public API Token used to authenticate the request.
        timeout: Optional request timeout in seconds.
        default_headers: Optional headers added to every HTTP request the SDK
            sends. The CLI uses this to inject ``X-Request-ID`` (and later
            ``traceparent``) so platform observability can correlate logs
            and traces from the client through the gateway. Headers carrying
            secrets must never be passed here; the credential lives in
            ``api_key``.
    """
    openai_class = _load_openai_client_class()
    kwargs: dict[str, object] = {
        "api_key": api_key,
        "base_url": base_url,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    if default_headers:
        kwargs["default_headers"] = dict(default_headers)
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
