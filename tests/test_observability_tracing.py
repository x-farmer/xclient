"""Tests for xclient OpenTelemetry tracer initialisation."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xclient.observability import config as obs_config
from xclient.observability import tracing as obs_tracing


def _build_cfg(**overrides: object) -> obs_config.EffectiveObservabilityConfig:
    base = obs_config.load_observability_config(env={})
    tracing_cfg = overrides.get("tracing", base.tracing)
    return obs_config.EffectiveObservabilityConfig(
        service_name=base.service_name,
        environment=base.environment,
        logging=base.logging,
        tracing=tracing_cfg,
    )


def test_init_tracing_disabled_returns_noop_provider() -> None:
    disabled = obs_config.EffectiveTracingConfig(
        enabled=False,
        exporter="none",
        endpoint="localhost:4317",
        protocol="grpc",
        insecure=True,
        sample_ratio=1.0,
    )
    cfg = _build_cfg(tracing=disabled)

    handle = obs_tracing.init_tracing(cfg, version="0.1.0-test")
    try:
        span = handle.tracer.start_span("op")
        ctx = span.get_span_context()
        assert ctx.is_valid is False or ctx.trace_id == 0
        span.end()
    finally:
        handle.shutdown(1.0)


def test_init_tracing_shutdown_is_idempotent() -> None:
    disabled = obs_config.EffectiveTracingConfig(
        enabled=False,
        exporter="none",
        endpoint="localhost:4317",
        protocol="grpc",
        insecure=True,
        sample_ratio=1.0,
    )
    cfg = _build_cfg(tracing=disabled)
    handle = obs_tracing.init_tracing(cfg, version="0.1.0-test")
    handle.shutdown(1.0)
    handle.shutdown(1.0)


def test_init_tracing_enabled_builds_sdk_provider() -> None:
    enabled = obs_config.EffectiveTracingConfig(
        enabled=True,
        exporter="otlp",
        endpoint="localhost:4317",
        protocol="grpc",
        insecure=True,
        sample_ratio=1.0,
    )
    cfg = _build_cfg(tracing=enabled)

    handle = obs_tracing.init_tracing(cfg, version="0.1.0-test")
    try:
        with handle.tracer.start_as_current_span("op") as span:
            ctx = span.get_span_context()
            assert ctx.is_valid
            assert ctx.trace_id != 0
    finally:
        handle.shutdown(1.0)
