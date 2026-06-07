"""Environment-driven observability configuration for the xclient CLI.

The xclient CLI does not own a config file. All observability knobs are read
from environment variables prefixed ``XF_OBS_`` so the CLI behaves
predictably in CI, container, and one-off shell invocations. This module is
the single boundary that turns environment text into a validated dataclass
the rest of xclient can rely on.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


DEFAULT_COMPONENT = "client"
"""Stable platform component identifier for the xclient CLI."""

_DEFAULT_SERVICE_NAME = "x-farmer-client"
_DEFAULT_ENVIRONMENT = "development"

_DEFAULT_LOG_LEVEL = "info"
_DEFAULT_LOG_FORMAT = "json"

_DEFAULT_TRACING_EXPORTER = "otlp"
_DEFAULT_TRACING_ENDPOINT = "localhost:4317"
_DEFAULT_TRACING_PROTOCOL = "grpc"
_DEFAULT_TRACING_SAMPLE_RATIO = 1.0

_ALLOWED_LOG_LEVELS = frozenset({"debug", "info", "warn", "error"})
_ALLOWED_LOG_FORMATS = frozenset({"json", "text"})
_ALLOWED_TRACING_EXPORTERS = frozenset({"otlp", "none"})
_ALLOWED_TRACING_PROTOCOLS = frozenset({"grpc", "http"})


class ObservabilityConfigError(ValueError):
    """Raised when an XF_OBS_* environment variable cannot be interpreted.

    The exception message identifies the offending environment variable so
    operators can fix the value without inspecting xclient source. Callers
    should treat this as a startup error and propagate it to the CLI exit
    boundary, where it will be reported on stderr.
    """


@dataclass(frozen=True)
class EffectiveLoggingConfig:
    """Validated logging settings consumed by the structured logger.

    Attributes:
        enabled: True when structured logging should be emitted at all.
        level: One of ``debug``, ``info``, ``warn``, ``error``.
        format: ``json`` for production telemetry, ``text`` for human reading.
    """

    enabled: bool
    level: str
    format: str


@dataclass(frozen=True)
class EffectiveTracingConfig:
    """Validated tracing settings consumed by the OpenTelemetry initializer.

    Attributes:
        enabled: True when spans should be created and exported.
        exporter: ``otlp`` or ``none``. ``none`` forces ``enabled=False``.
        endpoint: OTLP collector endpoint host:port (gRPC) or URL (HTTP).
        protocol: ``grpc`` or ``http``.
        insecure: True when the OTLP transport must skip TLS (dev only).
        sample_ratio: Head-based sampling ratio in the closed interval [0, 1].
        auth_token: OTLP ingestion bearer token. When non-empty it is sent as an
            ``Authorization: Bearer <token>`` header so a collector enforcing
            bearer-token auth accepts the spans; an empty string sends no header,
            keeping collectors without auth working. The value is a shared secret
            and must never be logged.
    """

    enabled: bool
    exporter: str
    endpoint: str
    protocol: str
    insecure: bool
    sample_ratio: float
    auth_token: str = ""


@dataclass(frozen=True)
class EffectiveObservabilityConfig:
    """Resolved observability configuration for one xclient invocation.

    The configuration is environment-derived and immutable for the lifetime
    of the CLI process. Logger and tracer constructors should accept this
    contract so unit tests do not have to manipulate global environment
    variables to assert behaviour.

    Attributes:
        service_name: OpenTelemetry ``service.name`` resource attribute.
        environment: Deployment environment label (for example, ``dev``).
        logging: Resolved structured logging settings.
        tracing: Resolved tracing exporter settings.
    """

    service_name: str
    environment: str
    logging: EffectiveLoggingConfig
    tracing: EffectiveTracingConfig


def load_observability_config(
    env: Mapping[str, str],
    *,
    component: str = DEFAULT_COMPONENT,
) -> EffectiveObservabilityConfig:
    """Loads the observability configuration from environment variables.

    Args:
        env: Environment mapping. Tests pass a literal dict to stay
            independent from the process environment.
        component: Platform component identifier used to default the
            ``service_name`` to ``x-farmer-<component>`` when
            ``XF_OBS_SERVICE_NAME`` is not set.

    Returns:
        The validated observability configuration.

    Raises:
        ObservabilityConfigError: A recognised XF_OBS_* variable is set to a
            value outside the allowed enum or numeric range.
    """
    component = component.strip()
    if not component:
        raise ObservabilityConfigError("component must be a non-empty identifier")

    service_name = (env.get("XF_OBS_SERVICE_NAME") or "").strip() or f"x-farmer-{component}"
    if service_name == "x-farmer-":  # only possible if component is whitespace
        raise ObservabilityConfigError("XF_OBS_SERVICE_NAME could not be defaulted")

    environment = (env.get("XF_OBS_ENVIRONMENT") or "").strip() or _DEFAULT_ENVIRONMENT

    logging = EffectiveLoggingConfig(
        enabled=_resolve_bool(env, "XF_OBS_LOGGING_ENABLED", default=True),
        level=_resolve_enum(
            env,
            "XF_OBS_LOGGING_LEVEL",
            default=_DEFAULT_LOG_LEVEL,
            allowed=_ALLOWED_LOG_LEVELS,
            lowercase=True,
        ),
        format=_resolve_enum(
            env,
            "XF_OBS_LOGGING_FORMAT",
            default=_DEFAULT_LOG_FORMAT,
            allowed=_ALLOWED_LOG_FORMATS,
            lowercase=True,
        ),
    )

    exporter = _resolve_enum(
        env,
        "XF_OBS_TRACING_EXPORTER",
        default=_DEFAULT_TRACING_EXPORTER,
        allowed=_ALLOWED_TRACING_EXPORTERS,
        lowercase=True,
    )
    protocol = _resolve_enum(
        env,
        "XF_OBS_TRACING_PROTOCOL",
        default=_DEFAULT_TRACING_PROTOCOL,
        allowed=_ALLOWED_TRACING_PROTOCOLS,
        lowercase=True,
    )
    endpoint = (env.get("XF_OBS_TRACING_ENDPOINT") or "").strip() or _DEFAULT_TRACING_ENDPOINT
    insecure = _resolve_bool(env, "XF_OBS_TRACING_INSECURE", default=True)
    sample_ratio = _resolve_float(
        env,
        "XF_OBS_TRACING_SAMPLE_RATIO",
        default=_DEFAULT_TRACING_SAMPLE_RATIO,
        minimum=0.0,
        maximum=1.0,
    )
    # OTLP ingestion bearer token. Stored verbatim (no enum/range validation)
    # because the collector compares the whole bearer value; an empty string
    # disables the Authorization header. Treated as a secret: never logged or
    # echoed back in errors.
    auth_token = (env.get("XF_OBS_TRACING_AUTH_TOKEN") or "").strip()
    # Tracing is opt-in: it defaults to disabled so a plain CLI invocation never
    # tries to reach a collector. Operators must set XF_OBS_TRACING_ENABLED to a
    # truthy value (and provide an endpoint) to export spans.
    tracing_enabled = _resolve_bool(env, "XF_OBS_TRACING_ENABLED", default=False)
    if exporter == "none":
        tracing_enabled = False
    if tracing_enabled and not endpoint:
        raise ObservabilityConfigError(
            "XF_OBS_TRACING_ENDPOINT must be set when tracing is enabled"
        )

    tracing = EffectiveTracingConfig(
        enabled=tracing_enabled,
        exporter=exporter,
        endpoint=endpoint,
        protocol=protocol,
        insecure=insecure,
        sample_ratio=sample_ratio,
        auth_token=auth_token,
    )

    return EffectiveObservabilityConfig(
        service_name=service_name,
        environment=environment,
        logging=logging,
        tracing=tracing,
    )


def _resolve_bool(env: Mapping[str, str], key: str, *, default: bool) -> bool:
    """Returns the boolean value for ``key`` or ``default`` when unset.

    Recognised true values are ``1``, ``true``, ``yes``, ``on`` (case
    insensitive). Recognised false values are ``0``, ``false``, ``no``,
    ``off``. Any other non-empty value raises ObservabilityConfigError so
    silent misinterpretation is impossible.
    """
    raw = env.get(key)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value == "":
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ObservabilityConfigError(f"{key}={raw!r} is not a recognised boolean")


def _resolve_enum(
    env: Mapping[str, str],
    key: str,
    *,
    default: str,
    allowed: frozenset[str],
    lowercase: bool,
) -> str:
    """Returns the enum value for ``key`` or ``default`` when unset.

    The value is matched after stripping whitespace and, when ``lowercase``
    is True, lowercasing. Values outside ``allowed`` raise
    ObservabilityConfigError with the full set of allowed values listed.
    """
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    candidate = raw.strip()
    if lowercase:
        candidate = candidate.lower()
    if candidate not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ObservabilityConfigError(
            f"{key}={raw!r} is invalid (expected one of: {allowed_text})"
        )
    return candidate


def _resolve_float(
    env: Mapping[str, str],
    key: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    """Returns the float value for ``key`` or ``default`` when unset.

    Values outside the closed interval ``[minimum, maximum]`` or which fail
    to parse raise ObservabilityConfigError so head-based sampling decisions
    remain meaningful for OpenTelemetry's ratio sampler.
    """
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ObservabilityConfigError(f"{key}={raw!r} is not a valid float") from exc
    if value < minimum or value > maximum:
        raise ObservabilityConfigError(
            f"{key}={raw!r} is out of range [{minimum}, {maximum}]"
        )
    return value
