"""Read-only Gmail and QQ mailbox connectors.

Credentials are kept in the operating-system keyring. Workspace JSON contains only
non-secret connection metadata and candidate/audit records.
"""

from __future__ import annotations

import base64
import email
import hashlib
import imaplib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from typing import Any, Callable, Dict, List, Optional, Protocol

from lifecycle import import_email_signal_candidates
from models import (
    AdvisorProfile,
    ApplicationRecord,
    EmailConnectorAuthorizationStart,
    EmailConnectorStatus,
    EmailSignalSyncResult,
    Target,
    now_iso,
)
from storage import Workspace

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class EmailConnectorError(RuntimeError):
    pass


class CredentialStore(Protocol):
    def get(self, provider: str, workspace: Workspace) -> Optional[Dict[str, Any]]: ...

    def set(self, provider: str, workspace: Workspace, value: Dict[str, Any]) -> None: ...

    def delete(self, provider: str, workspace: Workspace) -> None: ...


class KeyringCredentialStore:
    """Store per-workspace connector secrets in the OS keyring only."""

    def __init__(self, service_name: Optional[str] = None):
        self.service_name = service_name or os.environ.get(
            "EMAIL_CREDENTIAL_SERVICE", "offer-harvester.email"
        )

    def get(self, provider: str, workspace: Workspace) -> Optional[Dict[str, Any]]:
        keyring = self._keyring()
        try:
            raw = keyring.get_password(self.service_name, self._username(provider, workspace))
        except keyring.errors.KeyringError as exc:
            raise EmailConnectorError(
                "No usable OS keyring backend is available for mailbox credentials."
            ) from exc
        return json.loads(raw) if raw else None

    def set(self, provider: str, workspace: Workspace, value: Dict[str, Any]) -> None:
        keyring = self._keyring()
        try:
            keyring.set_password(
                self.service_name,
                self._username(provider, workspace),
                json.dumps(value, ensure_ascii=False),
            )
        except keyring.errors.KeyringError as exc:
            raise EmailConnectorError(
                "No usable OS keyring backend is available for mailbox credentials."
            ) from exc

    def delete(self, provider: str, workspace: Workspace) -> None:
        keyring = self._keyring()
        username = self._username(provider, workspace)
        try:
            keyring.delete_password(self.service_name, username)
        except keyring.errors.PasswordDeleteError:
            return
        except keyring.errors.KeyringError as exc:
            raise EmailConnectorError(
                "No usable OS keyring backend is available for mailbox credentials."
            ) from exc

    @staticmethod
    def _username(provider: str, workspace: Workspace) -> str:
        identity = hashlib.sha256(str(workspace.root).encode("utf-8")).hexdigest()[:20]
        return f"{provider}:{identity}"

    @staticmethod
    def _keyring():
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - depends on optional runtime package
            raise EmailConnectorError(
                "Email connectors require the optional keyring package and an OS secret backend."
            ) from exc
        return keyring


class MemoryCredentialStore:
    """Test-only credential store. Do not use for production or user credentials."""

    def __init__(self):
        self.values: Dict[str, Dict[str, Any]] = {}

    def get(self, provider: str, workspace: Workspace) -> Optional[Dict[str, Any]]:
        return self.values.get(self._key(provider, workspace))

    def set(self, provider: str, workspace: Workspace, value: Dict[str, Any]) -> None:
        self.values[self._key(provider, workspace)] = dict(value)

    def delete(self, provider: str, workspace: Workspace) -> None:
        self.values.pop(self._key(provider, workspace), None)

    @staticmethod
    def _key(provider: str, workspace: Workspace) -> str:
        return f"{provider}:{workspace.root}"


_PENDING_GMAIL_AUTH: Dict[str, Dict[str, Any]] = {}


def gmail_authorization_start(
    workspace: Workspace,
    *,
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> EmailConnectorAuthorizationStart:
    client_id = client_id or os.environ.get("GMAIL_OAUTH_CLIENT_ID", "")
    redirect_uri = redirect_uri or os.environ.get(
        "GMAIL_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/api/email-connectors/gmail/callback",
    )
    if not client_id:
        raise EmailConnectorError("GMAIL_OAUTH_CLIENT_ID is required before connecting Gmail.")

    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = _pkce_challenge(verifier)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    _PENDING_GMAIL_AUTH[state] = {
        "workspace_root": str(workspace.root),
        "verifier": verifier,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "expires_at": expires_at.timestamp(),
    }
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return EmailConnectorAuthorizationStart(
        authorization_url=f"{GMAIL_AUTHORIZE_URL}?{query}",
        redirect_uri=redirect_uri,
        expires_at=expires_at.isoformat(timespec="seconds"),
    )


def gmail_authorization_complete(
    workspace: Workspace,
    *,
    state: str,
    code: str,
    credential_store: CredentialStore,
    client_secret: Optional[str] = None,
    request_json: Optional[Callable[..., Dict[str, Any]]] = None,
) -> EmailConnectorStatus:
    pending = _PENDING_GMAIL_AUTH.pop(state, None)
    if not pending or pending["workspace_root"] != str(workspace.root):
        raise EmailConnectorError(
            "Gmail authorization state is missing or belongs to another workspace."
        )
    if pending["expires_at"] < time.time():
        raise EmailConnectorError("Gmail authorization state expired; start authorization again.")

    client_secret = client_secret or os.environ.get("GMAIL_OAUTH_CLIENT_SECRET", "")
    payload = {
        "code": code,
        "client_id": pending["client_id"],
        "redirect_uri": pending["redirect_uri"],
        "grant_type": "authorization_code",
        "code_verifier": pending["verifier"],
    }
    if client_secret:
        payload["client_secret"] = client_secret
    token = (request_json or _http_json)("POST", GMAIL_TOKEN_URL, data=payload)
    if not token.get("access_token"):
        raise EmailConnectorError("Gmail token exchange did not return an access token.")
    token["expires_at"] = _future_epoch(token.get("expires_in", 3600))
    credential_store.set("gmail", workspace, token)
    _write_connection_metadata(
        workspace,
        "gmail",
        configured=True,
        account_hint="Gmail account connected",
        auth_kind="oauth_pkce",
    )
    return email_connector_status(workspace, "gmail", credential_store)


def configure_qq_imap(
    workspace: Workspace,
    *,
    account: str,
    authorization_code: str,
    host: str = "imap.qq.com",
    credential_store: CredentialStore,
) -> EmailConnectorStatus:
    if not account.strip() or not authorization_code.strip():
        raise EmailConnectorError("QQ account and IMAP authorization code are required.")
    if not host.strip():
        raise EmailConnectorError("QQ IMAP host is required.")
    credential_store.set(
        "qq",
        workspace,
        {
            "account": account.strip(),
            "authorization_code": authorization_code.strip(),
            "host": host.strip(),
        },
    )
    _write_connection_metadata(
        workspace,
        "qq",
        configured=True,
        account_hint=_mask_account(account),
        auth_kind="imap_authorization_code",
    )
    return email_connector_status(workspace, "qq", credential_store)


def email_connector_status(
    workspace: Workspace,
    provider: str,
    credential_store: CredentialStore,
) -> EmailConnectorStatus:
    provider = provider if provider in {"gmail", "qq"} else "unknown"
    if provider == "unknown":
        return EmailConnectorStatus(
            provider="unknown",
            message="Unsupported mailbox provider. Choose Gmail or QQ.",
        )
    try:
        secret = credential_store.get(provider, workspace)
    except EmailConnectorError as exc:
        return EmailConnectorStatus(provider=provider, message=str(exc))
    metadata = workspace.read("email_connections", f"email_{provider}") or {}
    if not secret:
        legacy = bool(os.environ.get("EMAIL_SYNC_READONLY_TOKEN"))
        return EmailConnectorStatus(
            provider=provider,  # type: ignore[arg-type]
            configured=legacy,
            connected=False,
            account_hint=metadata.get("account_hint", ""),
            message=(
                "Legacy read-only sync marker is set, but no real mailbox credential is stored."
                if legacy
                else "Mailbox is not connected. Credentials are stored only in the OS keyring."
            ),
        )
    return EmailConnectorStatus(
        provider=provider,  # type: ignore[arg-type]
        configured=True,
        connected=True,
        account_hint=metadata.get("account_hint", ""),
        message="Read-only mailbox connection is available. Sync still creates candidates only.",
    )


def disconnect_email_connector(
    workspace: Workspace,
    provider: str,
    credential_store: CredentialStore,
) -> EmailConnectorStatus:
    if provider not in {"gmail", "qq"}:
        raise EmailConnectorError("Unsupported mailbox provider.")
    credential_store.delete(provider, workspace)
    _write_connection_metadata(
        workspace,
        provider,
        configured=False,
        account_hint="",
        auth_kind="",
    )
    return email_connector_status(workspace, provider, credential_store)


def sync_email_signal_candidates(
    workspace: Workspace,
    *,
    provider: str,
    targets: List[Target],
    applications: List[ApplicationRecord],
    advisors: List[AdvisorProfile],
    credential_store: CredentialStore,
    max_messages: int = 10,
    query: str = "",
    mailbox_filter: str = "all",
    gmail_fetcher: Optional[Callable[..., List[str]]] = None,
    qq_fetcher: Optional[Callable[..., List[str]]] = None,
) -> EmailSignalSyncResult:
    if provider == "gmail":
        messages = (gmail_fetcher or fetch_gmail_messages)(
            workspace,
            credential_store=credential_store,
            max_messages=max_messages,
            query=query,
        )
    elif provider == "qq":
        messages = (qq_fetcher or fetch_qq_messages)(
            workspace,
            credential_store=credential_store,
            max_messages=max_messages,
            mailbox_filter=mailbox_filter,
        )
    else:
        raise EmailConnectorError("Unsupported mailbox provider.")

    result = import_email_signal_candidates(
        workspace,
        provider,
        "\n\n".join(messages),
        targets,
        applications,
        advisors,
    )
    result.configured = True
    result.scanned_messages = len(messages)
    result.connector_mode = "readonly_connector"
    result.message = (
        f"Read {len(messages)} {provider} message(s) in read-only mode and created "
        f"{len(result.candidates)} candidate signal(s). Confirm each candidate before tracker writes."
    )
    _write_connection_metadata(
        workspace,
        provider,
        configured=True,
        account_hint=(workspace.read("email_connections", f"email_{provider}") or {}).get(
            "account_hint", ""
        ),
        auth_kind=(workspace.read("email_connections", f"email_{provider}") or {}).get(
            "auth_kind", ""
        ),
        last_sync_at=now_iso(),
    )
    return result


def fetch_gmail_messages(
    workspace: Workspace,
    *,
    credential_store: CredentialStore,
    max_messages: int,
    query: str = "",
    request_json: Optional[Callable[..., Dict[str, Any]]] = None,
) -> List[str]:
    token = _gmail_access_token(workspace, credential_store, request_json=request_json)
    requester = request_json or _http_json
    query_params = {"maxResults": str(max_messages)}
    if query.strip():
        query_params["q"] = query.strip()
    listing = requester(
        "GET",
        f"{GMAIL_API_BASE_URL}/messages?{urllib.parse.urlencode(query_params)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    messages = []
    for item in listing.get("messages", [])[:max_messages]:
        message_id = item.get("id", "")
        if not message_id:
            continue
        message = requester(
            "GET",
            f"{GMAIL_API_BASE_URL}/messages/{urllib.parse.quote(message_id)}?format=full",
            headers={"Authorization": f"Bearer {token}"},
        )
        messages.append(_gmail_message_to_raw_text(message))
    return messages


def fetch_qq_messages(
    workspace: Workspace,
    *,
    credential_store: CredentialStore,
    max_messages: int,
    mailbox_filter: str = "all",
    imap_factory: Callable[..., Any] = imaplib.IMAP4_SSL,
) -> List[str]:
    secret = credential_store.get("qq", workspace)
    if not secret:
        raise EmailConnectorError("QQ mailbox is not connected.")
    criteria = "UNSEEN" if mailbox_filter == "unseen" else "ALL"
    client = imap_factory(secret.get("host", "imap.qq.com"), 993)
    try:
        client.login(secret["account"], secret["authorization_code"])
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise EmailConnectorError("Unable to select QQ INBOX in read-only mode.")
        status, data = client.search(None, criteria)
        if status != "OK":
            raise EmailConnectorError("Unable to search QQ mailbox.")
        message_ids = (data[0] or b"").split()[-max_messages:]
        messages = []
        for message_id in reversed(message_ids):
            status, payload = client.fetch(message_id, "(RFC822)")
            if status != "OK" or not payload:
                continue
            raw_bytes = next(
                (
                    item[1]
                    for item in payload
                    if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes)
                ),
                b"",
            )
            if raw_bytes:
                messages.append(_rfc822_to_raw_text(raw_bytes))
        return messages
    finally:
        try:
            client.logout()
        except Exception:
            pass


def _gmail_access_token(
    workspace: Workspace,
    credential_store: CredentialStore,
    *,
    request_json: Optional[Callable[..., Dict[str, Any]]] = None,
) -> str:
    token = credential_store.get("gmail", workspace)
    if not token:
        raise EmailConnectorError("Gmail mailbox is not connected.")
    if token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 90:
        return token["access_token"]
    refresh_token = token.get("refresh_token", "")
    client_id = os.environ.get("GMAIL_OAUTH_CLIENT_ID", "")
    if not refresh_token or not client_id:
        raise EmailConnectorError(
            "Gmail access expired; reconnect Gmail to obtain a refresh token."
        )
    refresh_payload = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    client_secret = os.environ.get("GMAIL_OAUTH_CLIENT_SECRET", "")
    if client_secret:
        refresh_payload["client_secret"] = client_secret
    refreshed = (request_json or _http_json)("POST", GMAIL_TOKEN_URL, data=refresh_payload)
    if not refreshed.get("access_token"):
        raise EmailConnectorError("Gmail token refresh did not return an access token.")
    token.update(refreshed)
    token["expires_at"] = _future_epoch(refreshed.get("expires_in", 3600))
    credential_store.set("gmail", workspace, token)
    return token["access_token"]


def _http_json(
    method: str,
    url: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    encoded = None
    request_headers = dict(headers or {})
    if data is not None:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    request = urllib.request.Request(url, data=encoded, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - depends on live mailbox/provider
        raise EmailConnectorError(f"Mailbox provider request failed: {exc}") from exc


def _gmail_message_to_raw_text(message: Dict[str, Any]) -> str:
    headers = {
        item.get("name", "").lower(): item.get("value", "")
        for item in message.get("payload", {}).get("headers", [])
    }
    body = _gmail_payload_text(message.get("payload", {}))
    return "\n".join(
        [
            f"Subject: {headers.get('subject', 'Untitled message')}",
            f"From: {headers.get('from', '')}",
            f"Date: {headers.get('date', '')}",
            body[:12000],
        ]
    ).strip()


def _gmail_payload_text(payload: Dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {}).get("data", "")
    if mime_type == "text/plain" and body:
        return _decode_base64url(body)
    for part in payload.get("parts", []) or []:
        text = _gmail_payload_text(part)
        if text:
            return text
    if body:
        return _decode_base64url(body)
    return ""


def _rfc822_to_raw_text(raw_bytes: bytes) -> str:
    message = email.message_from_bytes(raw_bytes)
    subject = _decode_header(message.get("Subject", "")) or "Untitled message"
    sender = _decode_header(message.get("From", ""))
    received_at = _decode_header(message.get("Date", ""))
    body = _email_body_text(message)
    return "\n".join(
        [
            f"Subject: {subject}",
            f"From: {sender}",
            f"Date: {received_at}",
            body[:12000],
        ]
    ).strip()


def _email_body_text(message: Any) -> str:
    if message.is_multipart():
        for part in message.walk():
            if (
                part.get_content_type() != "text/plain"
                or part.get_content_disposition() == "attachment"
            ):
                continue
            return _decode_payload(part)
        return ""
    return _decode_payload(message) if message.get_content_type() == "text/plain" else ""


def _decode_payload(part: Any) -> str:
    raw = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _decode_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _decode_base64url(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii")).decode(
        "utf-8", errors="replace"
    )


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _future_epoch(seconds: Any) -> float:
    try:
        return time.time() + int(seconds)
    except (TypeError, ValueError):
        return time.time() + 3600


def _mask_account(account: str) -> str:
    value = account.strip()
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _write_connection_metadata(
    workspace: Workspace,
    provider: str,
    *,
    configured: bool,
    account_hint: str,
    auth_kind: str,
    last_sync_at: str = "",
) -> None:
    workspace.write(
        "email_connections",
        {
            "connection_id": f"email_{provider}",
            "provider": provider,
            "configured": configured,
            "read_only": True,
            "account_hint": account_hint,
            "auth_kind": auth_kind,
            "last_sync_at": last_sync_at,
            "updated_at": now_iso(),
        },
        "connection_id",
    )
