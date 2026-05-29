"""Structured logging primitives for the xclient CLI.

The CLI uses ``structlog`` to emit JSON log records on stderr so the
``stdout`` channel stays exclusively for OpenAI-compatible assistant content
and tooling output. All log records share a stable set of resource fields
(service, component, environment, version) and accept additional
context-bound fields contributed by future trace context processors.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
import logging
import sys
from typing import TextIO

import structlog

from xclient.observability.config import (
    DEFAULT_COMPONENT,
    EffectiveObservabilityConfig,
)


_LEVEL_MAP: Mapping[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}


def configure(
    cfg: EffectiveObservabilityConfig,
    *,
    component: str = DEFAULT_COMPONENT,
    version: str | None = None,
    stream: TextIO | None = None,
) -> structlog.stdlib.BoundLogger:
    """Configures structlog and returns the root xclient logger.

    Args:
        cfg: Resolved observability configuration.
        component: Stable component name used to populate the ``component``
            field on every record.
        version: Build identity for the running xclient process. Tests pass
            an explicit value; the CLI lets the helper read the installed
            package version through importlib.metadata.
        stream: Output stream for log records. Defaults to ``sys.stderr``
            so assistant content on stdout is never mixed with telemetry.

    Returns:
        The xclient root logger bound to baseline resource fields.
    """
    out_stream = stream if stream is not None else sys.stderr
    level = _LEVEL_MAP.get(cfg.logging.level, logging.INFO)

    if not cfg.logging.enabled:
        _configure_disabled()
        return structlog.get_logger("xclient")

    _configure_stdlib(out_stream, level)
    _configure_structlog(cfg, component=component, version=version)

    return structlog.get_logger("xclient")


def _configure_stdlib(stream: TextIO, level: int) -> None:
    """Resets the stdlib logging root handler so structlog has a clean target.

    Existing handlers (for example, from imported libraries) are removed so
    test runs and short-lived CLI invocations do not duplicate records on
    repeat configure calls.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def _configure_disabled() -> None:
    """Routes structlog to a discard sink when observability logging is off.

    The xclient CLI must remain non-crashing even when an operator opts out
    of structured telemetry, so we still configure structlog but with a
    null logger factory.
    """
    structlog.configure(
        processors=[],
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.ReturnLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _configure_structlog(
    cfg: EffectiveObservabilityConfig,
    *,
    component: str,
    version: str | None,
) -> None:
    """Installs the JSON/text renderer with baseline resource processors.

    Trace context injection is added by a separate observability step; this
    function reserves room in the processor chain by including the merge
    function for contextvars, which already supports binding additional
    trace fields without further reconfiguration.
    """
    resolved_version = version if version is not None else _read_package_version()
    resource_fields: MutableMapping[str, str] = {
        "service": cfg.service_name,
        "component": component,
        "environment": cfg.environment,
        "version": resolved_version,
    }
    renderer: structlog.types.Processor
    if cfg.logging.format == "text":
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="time"),
        _make_resource_processor(resource_fields),
        renderer,
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_LEVEL_MAP.get(cfg.logging.level, logging.INFO)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _make_resource_processor(
    resource_fields: Mapping[str, str],
) -> structlog.types.Processor:
    """Returns a structlog processor that copies static resource fields."""

    def processor(_logger: object, _name: str, event_dict: MutableMapping[str, object]) -> MutableMapping[str, object]:
        for key, value in resource_fields.items():
            event_dict.setdefault(key, value)
        return event_dict

    return processor


def _read_package_version() -> str:
    """Reads the xclient package version recorded by the build system.

    Falls back to ``"dev"`` when the package is being executed from a
    source tree without metadata so the logger still has a non-empty value
    to publish.
    """
    try:
        from importlib import metadata

        return metadata.version("xclient")
    except Exception:
        # importlib.metadata can raise PackageNotFoundError or surface in
        # test runs that do not install the package; observability must
        # never break the CLI, so we fall back without inspecting the
        # specific error type.
        return "dev"
