import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from llm_client import redact_secret  # noqa: E402


def test_redact_secret_masks_api_keys():
    text = "Incorrect API key provided: " + "sk-" + "abcdefghijklmnopqrstuvwxyz123456"

    assert redact_secret(text) == "Incorrect API key provided: sk-***"
