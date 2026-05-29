"""Tests for xclient CLI configuration behavior."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opentelemetry import trace
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from xclient import cli


def test_chat_argument_parsing_uses_cli_flags() -> None:
    parser = cli.build_parser()

    namespace = parser.parse_args(
        [
            "chat",
            "--base-url",
            "http://localhost:8080/v1",
            "--api-key",
            "xfk_test",
            "--model",
            "bill-qwen3:latest",
            "--message",
            "hello",
            "--stream",
            "--timeout",
            "3.5",
            "--debug",
        ]
    )
    options = cli.resolve_chat_options(namespace, env={})

    assert options.base_url == "http://localhost:8080/v1"
    assert options.api_key == "xfk_test"
    assert options.model == "bill-qwen3:latest"
    assert options.message == "hello"
    assert options.stream is True
    assert options.timeout == 3.5
    assert options.debug is True


def test_chat_options_fall_back_to_environment() -> None:
    parser = cli.build_parser()
    namespace = parser.parse_args(["chat", "--message", "hello"])

    options = cli.resolve_chat_options(
        namespace,
        env={
            "XF_BASE_URL": "http://localhost:8080/v1",
            "XF_API_KEY": "xfk_env",
            "XF_MODEL": "bill-qwen3:latest",
        },
    )

    assert options.base_url == "http://localhost:8080/v1"
    assert options.api_key == "xfk_env"
    assert options.model == "bill-qwen3:latest"
    assert options.message == "hello"
    assert options.stream is False
    assert options.timeout is None


def test_build_outbound_headers_injects_traceparent_inside_span() -> None:
    set_global_textmap(TraceContextTextMapPropagator())
    provider = TracerProvider(sampler=ALWAYS_ON)
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("client"):
        headers = cli._build_outbound_headers("req-123")

    assert headers["X-Request-ID"] == "req-123"
    assert "traceparent" in headers


def test_build_outbound_headers_without_active_span_only_carries_request_id() -> None:
    set_global_textmap(TraceContextTextMapPropagator())
    trace.set_tracer_provider(trace.NoOpTracerProvider())

    headers = cli._build_outbound_headers("req-456")

    assert headers == {"X-Request-ID": "req-456"}
