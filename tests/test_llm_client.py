import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from llm_client import api_endpoint, redact_secret, response_output_text  # noqa: E402


def test_redact_secret_masks_api_keys():
    text = "Incorrect API key provided: " + "sk-" + "abcdefghijklmnopqrstuvwxyz123456"

    assert redact_secret(text) == "Incorrect API key provided: sk-***"


def test_api_endpoint_adds_v1_once():
    assert api_endpoint("https://example.com", "/responses") == "https://example.com/v1/responses"
    assert (
        api_endpoint("https://example.com/v1", "/responses") == "https://example.com/v1/responses"
    )


def test_response_output_text_supports_responses_shape():
    data = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": '{"ok": true}'},
                ]
            }
        ]
    }

    assert response_output_text(data) == '{"ok": true}'
