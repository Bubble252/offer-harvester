from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

CommandRunner = Callable[[List[str], int], subprocess.CompletedProcess]


@dataclass(frozen=True)
class LocalRuntimeEndpoint:
    """Configuration for an OpenAI-compatible local model service."""

    base_url: str
    api_key: str = ""
    timeout: int = 10

    def endpoint(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        path = path if path.startswith("/") else f"/{path}"
        if base.endswith(path):
            return base
        if base.endswith("/v1"):
            return base + path
        return base + "/v1" + path


def post_json(
    endpoint: str,
    payload: Dict[str, Any],
    *,
    api_key: str = "",
    timeout: int = 10,
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
        body = exc.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"Local model request failed: HTTP {exc.code} {body}") from exc


def get_json(
    endpoint: str,
    *,
    api_key: str = "",
    timeout: int = 10,
) -> Dict[str, Any]:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"Local model request failed: HTTP {exc.code} {body}") from exc


def check_openai_compatible_service(endpoint: LocalRuntimeEndpoint) -> Dict[str, Any]:
    """Probe a local OpenAI-compatible service without sending user content."""

    if not endpoint.base_url:
        return {"configured": False, "ok": False, "models": [], "error": "base_url is empty"}
    try:
        data = get_json(
            endpoint.endpoint("/models"), api_key=endpoint.api_key, timeout=endpoint.timeout
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return {"configured": True, "ok": False, "models": [], "error": str(exc)}
    models = []
    for item in data.get("data", []):
        model_id = item.get("id")
        if isinstance(model_id, str):
            models.append(model_id)
    return {"configured": True, "ok": True, "models": models, "error": ""}


def default_command_runner(args: List[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def diagnose_hardware(
    *,
    workspace_path: str | Path,
    min_free_gb: float = 30.0,
    runner: CommandRunner = default_command_runner,
) -> Dict[str, Any]:
    """Return a dependency-free hardware report for local model planning."""

    workspace = Path(workspace_path).resolve()
    usage = shutil.disk_usage(workspace)
    free_gb = round(usage.free / 1024**3, 2)
    total_gb = round(usage.total / 1024**3, 2)
    memory = _read_meminfo()
    gpu = _probe_gpu(runner=runner)
    return {
        "workspace_path": str(workspace),
        "disk": {
            "total_gb": total_gb,
            "free_gb": free_gb,
            "min_required_free_gb": min_free_gb,
            "ok_for_model_downloads": free_gb >= min_free_gb,
        },
        "memory": memory,
        "gpu": gpu,
        "recommendation": _hardware_recommendation(
            free_gb=free_gb, min_free_gb=min_free_gb, gpu=gpu
        ),
    }


def _read_meminfo() -> Dict[str, Any]:
    path = Path("/proc/meminfo")
    if not path.exists():
        return {"available_gb": None, "total_gb": None, "swap_free_gb": None}
    values = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0])
    return {
        "total_gb": round(values.get("MemTotal", 0) / 1024**2, 2),
        "available_gb": round(values.get("MemAvailable", 0) / 1024**2, 2),
        "swap_free_gb": round(values.get("SwapFree", 0) / 1024**2, 2),
    }


def _probe_gpu(*, runner: CommandRunner) -> Dict[str, Any]:
    if shutil.which("nvidia-smi") is None:
        return {"available": False, "error": "nvidia-smi not found"}
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = runner(command, 5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}
    if result.returncode != 0:
        return {"available": False, "error": result.stderr.strip() or result.stdout.strip()}
    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    parts = [part.strip() for part in first_line.split(",")]
    if len(parts) < 4:
        return {"available": False, "error": "unexpected nvidia-smi output"}
    try:
        total_mb = int(float(parts[1]))
        used_mb = int(float(parts[2]))
    except ValueError:
        return {"available": False, "error": "unexpected nvidia-smi memory values"}
    return {
        "available": True,
        "name": parts[0],
        "memory_total_mb": total_mb,
        "memory_used_mb": used_mb,
        "memory_free_mb": max(total_mb - used_mb, 0),
        "driver_version": parts[3],
    }


def _hardware_recommendation(
    *,
    free_gb: float,
    min_free_gb: float,
    gpu: Dict[str, Any],
) -> str:
    if free_gb < min_free_gb:
        return "free_disk_first"
    if not gpu.get("available"):
        return "cpu_or_api_only"
    total_mb = int(gpu.get("memory_total_mb") or 0)
    if total_mb < 7680:
        return "small_embedding_and_cpu_ocr_only"
    if total_mb < 16384:
        return "quantized_1_5b_3b_7b_and_small_reranker"
    return "larger_local_models_possible_with_feature_flags"
