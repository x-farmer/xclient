"""Tests for xclient observability logging configuration."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xclient.observability import config as obs_config
from xclient.observability import logging as obs_logging


def _build_cfg(**overrides: object) -> obs_config.EffectiveObservabilityConfig:
    """Builds a default observability config with optional overrides applied."""
    base = obs_config.load_observability_config(env={})
    if not overrides:
        return base
    fields = {
        "service_name": base.service_name,
        "environment": base.environment,
        "logging": base.logging,
        "tracing": base.tracing,
    }
    if "logging" in overrides:
        fields["logging"] = overrides["logging"]
    return obs_config.EffectiveObservabilityConfig(
        service_name=fields["service_name"],
        environment=fields["environment"],
        logging=fields["logging"],
        tracing=fields["tracing"],
    )


def test_configure_logging_emits_json_resource_fields() -> None:
    cfg = _build_cfg()
    buf = io.StringIO()

    logger = obs_logging.configure(cfg, version="0.1.0-test", stream=buf)
    logger.info("client starting", base_url="http://localhost/v1", model="bill-qwen3")

    record = json.loads(buf.getvalue().strip())
    assert record["service"] == "x-farmer-client"
    assert record["component"] == "client"
    assert record["environment"] == "development"
    assert record["version"] == "0.1.0-test"
    assert record["event"] == "client starting"
    assert record["base_url"] == "http://localhost/v1"
    assert record["model"] == "bill-qwen3"
    assert record["level"] == "info"


def test_configure_logging_respects_disabled_logging() -> None:
    disabled_logging = obs_config.EffectiveLoggingConfig(
        enabled=False, level="info", format="json"
    )
    cfg = _build_cfg(logging=disabled_logging)
    buf = io.StringIO()

    logger = obs_logging.configure(cfg, version="0.1.0-test", stream=buf)
    logger.info("should be discarded")

    assert buf.getvalue() == ""


def test_configure_logging_text_format_uses_console_renderer() -> None:
    text_logging = obs_config.EffectiveLoggingConfig(
        enabled=True, level="info", format="text"
    )
    cfg = _build_cfg(logging=text_logging)
    buf = io.StringIO()

    logger = obs_logging.configure(cfg, version="0.1.0-test", stream=buf)
    logger.info("client starting", model="bill-qwen3")

    output = buf.getvalue()
    assert output != ""
    assert "client starting" in output
    assert "model" in output


def test_configure_logging_resets_root_handlers() -> None:
    cfg = _build_cfg()
    first = io.StringIO()
    second = io.StringIO()

    obs_logging.configure(cfg, version="t", stream=first)
    obs_logging.configure(cfg, version="t", stream=second)

    root_handlers = logging.getLogger().handlers
    assert len(root_handlers) == 1
