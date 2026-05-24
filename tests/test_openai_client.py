"""Tests for the OpenAI SDK construction boundary."""

from pathlib import Path
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xclient import openai_client


def test_create_openai_client_passes_selected_settings() -> None:
    with mock.patch("xclient.openai_client._load_openai_client_class") as load_openai:
        openai_class = load_openai.return_value
        client = openai_client.create_openai_client(
            base_url="http://localhost:8080/v1",
            api_key="xfk_test",
            timeout=5.0,
        )

    openai_class.assert_called_once_with(
        api_key="xfk_test",
        base_url="http://localhost:8080/v1",
        timeout=5.0,
    )
    assert client is openai_class.return_value


def test_create_openai_client_omits_timeout_when_unset() -> None:
    with mock.patch("xclient.openai_client._load_openai_client_class") as load_openai:
        openai_class = load_openai.return_value
        openai_client.create_openai_client(
            base_url="http://localhost:8080/v1",
            api_key="xfk_test",
            timeout=None,
        )

    openai_class.assert_called_once_with(
        api_key="xfk_test",
        base_url="http://localhost:8080/v1",
    )
