"""Command-line entry point for x-farmer OpenAI-compatible Gateway testing."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
import sys
from typing import TextIO

from xclient import openai_client
from xclient.observability import (
    DEFAULT_COMPONENT as _OBS_COMPONENT,
    EffectiveObservabilityConfig,
    ObservabilityConfigError,
    configure_logging,
    load_observability_config,
)

_ENV_BASE_URL = "XF_BASE_URL"
_ENV_API_KEY = "XF_API_KEY"
_ENV_MODEL = "XF_MODEL"


@dataclass(frozen=True)
class ChatOptions:
    """Resolved options for one chat completion request.

    Values are selected from CLI flags first and environment variables second.
    `api_key` is intentionally excluded from debug output because it is a user
    credential.
    """

    base_url: str
    api_key: str
    model: str
    message: str
    stream: bool
    timeout: float | None
    debug: bool


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI parser for the `xclient` executable."""
    parser = argparse.ArgumentParser(
        prog="xclient",
        description="Thin OpenAI SDK client for testing x-farmer API Gateway.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser(
        "chat",
        help="Send one OpenAI-compatible chat completion request.",
    )
    chat_parser.add_argument(
        "--base-url",
        help=f"Gateway base URL. Defaults to ${_ENV_BASE_URL}.",
    )
    chat_parser.add_argument(
        "--api-key",
        help=f"API Token. Defaults to ${_ENV_API_KEY}.",
    )
    chat_parser.add_argument(
        "--model",
        help=f"Public model name. Defaults to ${_ENV_MODEL}.",
    )
    chat_parser.add_argument(
        "--message",
        required=True,
        help="User message to send as a single chat completion prompt.",
    )
    chat_parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable OpenAI SDK streaming chat completions.",
    )
    chat_parser.add_argument(
        "--timeout",
        type=float,
        help="SDK request timeout in seconds.",
    )
    chat_parser.add_argument(
        "--debug",
        action="store_true",
        help="Print selected non-secret options and SDK exception details.",
    )
    chat_parser.set_defaults(handler=_handle_chat)
    return parser


def resolve_chat_options(
    namespace: argparse.Namespace,
    env: Mapping[str, str],
) -> ChatOptions:
    """Resolves CLI and environment values into one chat request contract.

    Args:
        namespace: Parsed arguments for the `chat` subcommand.
        env: Environment mapping used for fallback values.

    Raises:
        ValueError: A required non-message option is missing after environment
            fallback.
    """
    base_url = namespace.base_url or env.get(_ENV_BASE_URL)
    api_key = namespace.api_key or env.get(_ENV_API_KEY)
    model = namespace.model or env.get(_ENV_MODEL)

    missing = [
        flag
        for flag, value in (
            ("--base-url or XF_BASE_URL", base_url),
            ("--api-key or XF_API_KEY", api_key),
            ("--model or XF_MODEL", model),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"missing required option: {', '.join(missing)}")

    return ChatOptions(
        base_url=base_url,
        api_key=api_key,
        model=model,
        message=namespace.message,
        stream=namespace.stream,
        timeout=namespace.timeout,
        debug=namespace.debug,
    )


def run_chat(
    options: ChatOptions,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    env: Mapping[str, str] | None = None,
) -> int:
    """Runs one OpenAI SDK chat completion request and prints assistant output.

    Success means the official SDK call completed. SDK exceptions are reported
    clearly without interpreting raw response bodies or OpenAI protocol details.

    Args:
        options: Resolved chat request options.
        stdout: Stream that receives assistant content.
        stderr: Stream that receives diagnostics and SDK errors.
        env: Optional environment mapping for observability config. Tests pass
            a literal dict; the CLI passes ``os.environ``.
    """
    try:
        observability = load_observability_config(
            env if env is not None else os.environ,
            component=_OBS_COMPONENT,
        )
    except ObservabilityConfigError as error:
        print(f"observability config error: {error}", file=stderr)
        return 2

    logger = configure_logging(observability, component=_OBS_COMPONENT, stream=stderr)
    logger.info(
        "client starting",
        base_url=options.base_url,
        model=options.model,
        stream=options.stream,
    )

    if options.debug:
        _print_debug_selection(options, observability=observability, stderr=stderr)

    try:
        client = openai_client.create_openai_client(
            base_url=options.base_url,
            api_key=options.api_key,
            timeout=options.timeout,
        )
        completion = openai_client.create_chat_completion(
            client,
            model=options.model,
            message=options.message,
            stream=options.stream,
        )
        if options.stream:
            _print_streaming_completion(completion, stdout=stdout)
        else:
            _print_completion(completion, stdout=stdout)
    except Exception as error:
        # This CLI boundary reports SDK failures without interpreting protocol
        # details, while still allowing unexpected application bugs to surface.
        if _is_missing_openai_dependency(error) or openai_client.is_openai_sdk_exception(error):
            _print_sdk_error(error, debug=options.debug, stderr=stderr)
            return 1
        raise

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the `xclient` CLI and returns a process exit code."""
    parser = build_parser()
    namespace = parser.parse_args(argv)
    return namespace.handler(namespace, parser)


def _handle_chat(namespace: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        options = resolve_chat_options(namespace, os.environ)
    except ValueError as error:
        parser.error(str(error))
    return run_chat(options)


def _print_debug_selection(
    options: ChatOptions,
    *,
    observability: EffectiveObservabilityConfig,
    stderr: TextIO,
) -> None:
    """Writes non-secret debug lines for the resolved chat and observability config.

    The function deliberately omits ``api_key`` and any other credential
    material so the diagnostic output never leaks secrets into terminals,
    pipes, or CI logs.
    """
    print(f"debug: base_url={options.base_url}", file=stderr)
    print(f"debug: model={options.model}", file=stderr)
    print(f"debug: stream={options.stream}", file=stderr)
    print(f"debug: obs.service_name={observability.service_name}", file=stderr)
    print(f"debug: obs.environment={observability.environment}", file=stderr)
    print(f"debug: obs.logging.enabled={observability.logging.enabled}", file=stderr)
    print(f"debug: obs.logging.level={observability.logging.level}", file=stderr)
    print(f"debug: obs.logging.format={observability.logging.format}", file=stderr)
    print(f"debug: obs.tracing.enabled={observability.tracing.enabled}", file=stderr)
    print(f"debug: obs.tracing.exporter={observability.tracing.exporter}", file=stderr)
    print(f"debug: obs.tracing.endpoint={observability.tracing.endpoint}", file=stderr)
    print(f"debug: obs.tracing.protocol={observability.tracing.protocol}", file=stderr)
    print(f"debug: obs.tracing.sample_ratio={observability.tracing.sample_ratio}", file=stderr)


def _print_sdk_error(
    error: BaseException,
    *,
    debug: bool,
    stderr: TextIO,
) -> None:
    if debug:
        print(f"debug: sdk_exception_type={type(error).__name__}", file=stderr)
        print(f"debug: sdk_exception_message={error}", file=stderr)
        return

    print(f"OpenAI SDK error ({type(error).__name__}): {error}", file=stderr)


def _is_missing_openai_dependency(error: BaseException) -> bool:
    return isinstance(error, ModuleNotFoundError) and error.name == "openai"


def _print_completion(completion: object, *, stdout: TextIO) -> None:
    choices = getattr(completion, "choices", ())
    for choice in choices:
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if content:
            stdout.write(content)
            break
    stdout.write("\n")


def _print_streaming_completion(completion: object, *, stdout: TextIO) -> None:
    for chunk in completion:
        choices = getattr(chunk, "choices", ())
        for choice in choices:
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None)
            if content:
                stdout.write(content)
                stdout.flush()
    stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
