"""Scoped authentication guard for external Skill/DSH plugin calls."""

from __future__ import annotations

import hmac
import os
from typing import Iterable

from fastapi import HTTPException, Request

TOKEN_HEADER = "X-Offer-Harvester-Plugin-Token"
SCOPE_HEADER = "X-Offer-Harvester-Plugin-Scopes"
PRIVACY_HEADER = "X-Offer-Harvester-Privacy-Mode"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def require_plugin_scope(request: Request, required_scope: str) -> None:
    """Allow local development or enforce a configured static scoped token."""

    auth_mode = os.environ.get("OFFER_HARVESTER_PLUGIN_AUTH_MODE", "local").strip().lower()
    client_host = getattr(getattr(request, "client", None), "host", "")
    is_local = client_host in LOCAL_HOSTS
    if auth_mode == "disabled":
        return
    if auth_mode == "local" and is_local:
        return
    if auth_mode not in {"local", "token"}:
        raise HTTPException(status_code=500, detail="Invalid plugin authentication mode")

    configured = os.environ.get("OFFER_HARVESTER_PLUGIN_TOKEN", "")
    supplied = request.headers.get(TOKEN_HEADER, "")
    if not configured or not supplied or not hmac.compare_digest(configured, supplied):
        raise HTTPException(
            status_code=401, detail="Valid Offer Harvester plugin token is required"
        )

    scopes = _configured_scopes()
    if required_scope not in scopes:
        raise HTTPException(status_code=403, detail=f"Plugin token lacks scope: {required_scope}")

    requested = _header_scopes(request.headers.get(SCOPE_HEADER, ""))
    if requested and required_scope not in requested:
        raise HTTPException(
            status_code=403, detail=f"Request does not declare scope: {required_scope}"
        )

    privacy_mode = request.headers.get(PRIVACY_HEADER, "metadata_only").strip().lower()
    if privacy_mode == "private" and not _bool_env("OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE"):
        raise HTTPException(
            status_code=403,
            detail="Remote private-data plugin calls are disabled by server policy",
        )


def _configured_scopes() -> set[str]:
    raw = os.environ.get(
        "OFFER_HARVESTER_PLUGIN_SCOPES",
        "skill:run,material:audit,advisor:report,policy:read",
    )
    return {item.strip() for item in raw.split(",") if item.strip()}


def _header_scopes(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _bool_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def documented_plugin_scopes() -> Iterable[str]:
    return sorted(_configured_scopes())
