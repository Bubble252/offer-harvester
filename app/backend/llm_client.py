from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def redact_secret(value: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", value)


def load_local_env(path: Path = PROJECT_ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value or key not in os.environ:
            os.environ[key] = value


def llm_configured() -> bool:
    load_local_env()
    return bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_MODEL"))


def api_endpoint(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def request_json(
    endpoint: str, payload: Dict[str, Any], api_key: str, timeout: int
) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = redact_secret(exc.read().decode("utf-8", errors="ignore")[:500])
        raise RuntimeError(f"LLM request failed: HTTP {exc.code} {body}") from exc


def parse_json_text(content: str) -> Dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    return json.loads(content)


def response_output_text(data: Dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                parts.append(content.get("text", ""))
    if parts:
        return "\n".join(parts)
    return data["choices"][0]["message"]["content"]


def llm_json(messages: List[Dict[str, str]], timeout: int = 45) -> Dict[str, Any]:
    load_local_env()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "")
    base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    wire_api = (os.environ.get("OPENAI_WIRE_API") or "chat").lower()
    if not api_key or not model:
        raise RuntimeError("LLM is not configured")

    if wire_api == "responses":
        endpoint = api_endpoint(base_url, "/responses")
        instructions = "\n".join(
            message["content"] for message in messages if message["role"] == "system"
        )
        user_input = "\n\n".join(
            message["content"] for message in messages if message["role"] != "system"
        )
        payload = {
            "model": model,
            "instructions": instructions,
            "input": user_input,
            "temperature": 0.1,
            "text": {"format": {"type": "json_object"}},
        }
        data = request_json(endpoint, payload, api_key, timeout)
        return parse_json_text(response_output_text(data))

    endpoint = api_endpoint(base_url, "/chat/completions")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    data = request_json(endpoint, payload, api_key, timeout)
    content = data["choices"][0]["message"]["content"]
    return parse_json_text(content)


def extract_advisor_profile_with_llm(source_text: str) -> Optional[Dict[str, Any]]:
    if not llm_configured():
        return None
    trimmed = source_text[:12000]
    messages = [
        {
            "role": "system",
            "content": (
                "你是保研硕博申请场景的导师资料结构化抽取器。"
                "只从用户提供的原文中抽取信息，不得补写、猜测或编造。"
                "每个非空字段必须尽量给 evidence 证据句。"
                "输出严格 JSON。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请从以下导师公开资料中抽取结构化字段。"
                "JSON schema: {"
                '"name_zh":"", "name_en":"", "title":"", '
                '"school":"", "college":"", "department":"", '
                '"lab_name":"", "email":"", '
                '"research_directions":[{"value":"", "evidence":"", "confidence":0.0}], '
                '"representative_papers":[{"value":"", "evidence":"", "confidence":0.0}], '
                '"research_projects":[{"value":"", "evidence":"", "confidence":0.0}], '
                '"admission_requirements":[{"value":"", "evidence":"", "confidence":0.0}], '
                '"preferred_student_profile":[{"value":"", "evidence":"", "confidence":0.0}], '
                '"recent_focus":[{"value":"", "evidence":"", "confidence":0.0}], '
                '"recruiting_status":"open|closed|unknown", '
                '"risk_notes":[""], "missing_fields":[""]}'
                "\n\n原文：\n"
                f"{trimmed}"
            ),
        },
    ]
    return llm_json(messages)
