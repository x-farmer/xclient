"""OpenTelemetry tracer initialisation for the xclient CLI.

The CLI uses OTLP (gRPC by default) to ship spans to a local collector. The
helpers in this module own provider construction and shutdown only; concrete
span creation lives in the call sites that wrap OpenAI SDK requests so the
trace shape mirrors the platform plan.

When tracing is disabled in observability config, ``init_tracing`` still
returns a usable :class:`TracerHandle` whose ``tracer`` produces no-op
spans. CLI code can therefore call ``tracer.start_as_current_span`` without
checking whether telemetry is configured.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import NoOpTracerProvider

from xclient.observability.config import (
    DEFAULT_COMPONENT,
    EffectiveObservabilityConfig,
)


_DEFAULT_INSTRUMENTATION_NAME = "xclient"


@dataclass(frozen=True)
class TracerHandle:
    """Handle returned by :func:`init_tracing`.

    Attributes:
        provider: Active tracer provider. Always non-None; falls back to the
            OpenTelemetry no-op provider when tracing is disabled.
        tracer: Default tracer used by CLI call sites. Equivalent to
            ``provider.get_tracer(_DEFAULT_INSTRUMENTATION_NAME)`` but cached
            so call sites do not repeat string literals.
        shutdown: Callable that flushes pending spans and stops the provider.
            Idempotent; calling more than once returns immediately. The
            caller must invoke this before the CLI process exits so spans
            are not lost when the OS reaps the process.
    """

    provider: trace.TracerProvider
    tracer: trace.Tracer
    shutdown: Callable[[float], None]


def init_tracing(
    cfg: EffectiveObservabilityConfig,
    *,
    component: str = DEFAULT_COMPONENT,
    version: str | None = None,
) -> TracerHandle:
    """Constructs the tracer provider and registers it as the global default.

    Args:
        cfg: Resolved observability configuration.
        component: Stable component identifier (matches the Core convention).
        version: xclient build identity. The helper falls back to the same
            package-version lookup used by structured logging.

    Returns:
        A :class:`TracerHandle` whose ``shutdown`` flushes spans before the
        process exits.
    """
    if not cfg.tracing.enabled:
        return _disabled_handle()

    exporter = _build_exporter(cfg)
    resource = _build_resource(cfg, component=component, version=version)
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(cfg.tracing.sample_ratio)),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = provider.get_tracer(_DEFAULT_INSTRUMENTATION_NAME)

    closed = False

    def shutdown(timeout_seconds: float = 5.0) -> None:
        nonlocal closed
        if closed:
            return
        closed = True
        try:
            provider.shutdown()
        except Exception:
            # The CLI prefers swallowing teardown failures over crashing the
            # process; the OpenTelemetry exporter logs errors internally.
            logging.getLogger("xclient").debug("tracer shutdown raised", exc_info=True)

    return TracerHandle(provider=provider, tracer=tracer, shutdown=shutdown)


def _disabled_handle() -> TracerHandle:
    """Returns a handle backed by the OpenTelemetry no-op tracer provider."""
    provider = NoOpTracerProvider()
    trace.set_tracer_provider(provider)
    tracer = provider.get_tracer(_DEFAULT_INSTRUMENTATION_NAME)
    return TracerHandle(provider=provider, tracer=tracer, shutdown=lambda _t=5.0: None)


def _build_exporter(cfg: EffectiveObservabilityConfig):
    """Selects the OTLP exporter implementation that matches ``cfg.tracing``.

    gRPC is the default for the dev stack documented in the observability
    plan; HTTP exists for deployments that cannot reach the collector over
    gRPC. The CLI does not own retry policy; the SDK applies its built-in
    exponential backoff.
    """
    protocol = cfg.tracing.protocol
    endpoint = cfg.tracing.endpoint
    insecure = cfg.tracing.insecure
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as GrpcSpanExporter,
        )

        return GrpcSpanExporter(endpoint=endpoint, insecure=insecure)
    if protocol == "http":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as HttpSpanExporter,
        )

        return HttpSpanExporter(endpoint=endpoint)
    raise ValueError(f"unsupported tracing protocol: {protocol!r}")


def _build_resource(
    cfg: EffectiveObservabilityConfig,
    *,
    component: str,
    version: str | None,
) -> Resource:
    """Builds the OpenTelemetry resource for telemetry produced by xclient."""
    resolved_version = version if version is not None else _read_package_version()
    attributes = {
        "service.name": cfg.service_name,
        "service.version": resolved_version,
        "deployment.environment": cfg.environment,
        "xfarmer.component": component,
    }
    return Resource.create(attributes)


def _read_package_version() -> str:
    """Mirrors the version fallback used by structured logging."""
    try:
        from importlib import metadata

        return metadata.version("xclient")
    except Exception:
        return "dev"
