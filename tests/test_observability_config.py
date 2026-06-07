"""Tests for xclient observability configuration loading."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xclient.observability import config as obs_config


def test_load_observability_config_applies_defaults() -> None:
    effective = obs_config.load_observability_config(env={})

    assert effective.service_name == "x-farmer-client"
    assert effective.environment == "development"
    assert effective.logging.enabled is True
    assert effective.logging.level == "info"
    assert effective.logging.format == "json"
    # Tracing is opt-in, so an unconfigured environment leaves it disabled even
    # though the exporter/endpoint defaults are still resolved.
    assert effective.tracing.enabled is False
    assert effective.tracing.exporter == "otlp"
    assert effective.tracing.endpoint == "localhost:4317"
    assert effective.tracing.protocol == "grpc"
    assert effective.tracing.insecure is True
    assert effective.tracing.sample_ratio == 1.0
    assert effective.tracing.auth_token == ""


def test_load_observability_config_respects_overrides() -> None:
    effective = obs_config.load_observability_config(
        env={
            "XF_OBS_SERVICE_NAME": "x-farmer-shadow",
            "XF_OBS_ENVIRONMENT": "staging",
            "XF_OBS_LOGGING_ENABLED": "false",
            "XF_OBS_LOGGING_LEVEL": "debug",
            "XF_OBS_LOGGING_FORMAT": "text",
            "XF_OBS_TRACING_ENABLED": "true",
            "XF_OBS_TRACING_EXPORTER": "otlp",
            "XF_OBS_TRACING_ENDPOINT": "collector.svc:4318",
            "XF_OBS_TRACING_PROTOCOL": "http",
            "XF_OBS_TRACING_INSECURE": "no",
            "XF_OBS_TRACING_SAMPLE_RATIO": "0.25",
        }
    )

    assert effective.service_name == "x-farmer-shadow"
    assert effective.environment == "staging"
    assert effective.logging.enabled is False
    assert effective.logging.level == "debug"
    assert effective.logging.format == "text"
    # Explicit XF_OBS_TRACING_ENABLED=true opts back in over the disabled default.
    assert effective.tracing.enabled is True
    assert effective.tracing.exporter == "otlp"
    assert effective.tracing.endpoint == "collector.svc:4318"
    assert effective.tracing.protocol == "http"
    assert effective.tracing.insecure is False
    assert effective.tracing.sample_ratio == 0.25


def test_load_observability_config_none_exporter_disables_tracing() -> None:
    effective = obs_config.load_observability_config(
        env={"XF_OBS_TRACING_EXPORTER": "none"}
    )

    assert effective.tracing.enabled is False


def test_load_observability_config_rejects_invalid_level() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(env={"XF_OBS_LOGGING_LEVEL": "trace"})


def test_load_observability_config_rejects_invalid_format() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(env={"XF_OBS_LOGGING_FORMAT": "logfmt"})


def test_load_observability_config_rejects_invalid_exporter() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(env={"XF_OBS_TRACING_EXPORTER": "jaeger"})


def test_load_observability_config_rejects_invalid_protocol() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(env={"XF_OBS_TRACING_PROTOCOL": "thrift"})


def test_load_observability_config_rejects_invalid_sample_ratio() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(
            env={"XF_OBS_TRACING_SAMPLE_RATIO": "2"}
        )


def test_load_observability_config_rejects_unparseable_sample_ratio() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(env={"XF_OBS_TRACING_SAMPLE_RATIO": "abc"})


def test_load_observability_config_rejects_invalid_boolean() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(
            env={"XF_OBS_LOGGING_ENABLED": "maybe"}
        )


def test_load_observability_config_component_override() -> None:
    effective = obs_config.load_observability_config(env={}, component="worker")

    assert effective.service_name == "x-farmer-worker"


def test_load_observability_config_empty_component_rejected() -> None:
    with pytest.raises(obs_config.ObservabilityConfigError):
        obs_config.load_observability_config(env={}, component="  ")


def test_load_observability_config_reads_and_trims_auth_token() -> None:
    effective = obs_config.load_observability_config(
        env={"XF_OBS_TRACING_AUTH_TOKEN": "  ingest-token  "}
    )

    assert effective.tracing.auth_token == "ingest-token"
