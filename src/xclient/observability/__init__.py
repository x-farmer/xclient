"""Observability primitives for the xclient CLI.

This package holds the configuration, structured logger, and tracing helpers
used by xclient to emit structured logs and propagate trace context to
upstream services. CLI adapters consume these primitives so the boundary
between command parsing and telemetry stays explicit.
"""

from xclient.observability.config import (
    DEFAULT_COMPONENT,
    EffectiveLoggingConfig,
    EffectiveObservabilityConfig,
    EffectiveTracingConfig,
    ObservabilityConfigError,
    load_observability_config,
)
from xclient.observability.logging import configure as configure_logging
from xclient.observability.tracing import TracerHandle, init_tracing

__all__ = (
    "DEFAULT_COMPONENT",
    "EffectiveLoggingConfig",
    "EffectiveObservabilityConfig",
    "EffectiveTracingConfig",
    "ObservabilityConfigError",
    "TracerHandle",
    "configure_logging",
    "init_tracing",
    "load_observability_config",
)
