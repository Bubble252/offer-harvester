import json
import sys
import time
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import main as backend_main  # noqa: E402
from email_connectors import (  # noqa: E402
    KeyringCredentialStore,
    MemoryCredentialStore,
    configure_qq_imap,
    email_connector_status,
    fetch_qq_messages,
    gmail_authorization_complete,
    gmail_authorization_start,
    sync_email_signal_candidates,
)
from models import (  # noqa: E402
    ApplicationRecord,
    BrowserEvidenceCaptureRequest,
    Target,
)
from storage import Workspace  # noqa: E402


def test_gmail_oauth_pkce_exchanges_token_into_credential_store(tmp_path):
    workspace = Workspace(str(tmp_path))
    credentials = MemoryCredentialStore()
    started = gmail_authorization_start(
        workspace,
        client_id="client-id",
        redirect_uri="http://127.0.0.1:8000/api/email-connectors/gmail/callback",
    )
    parsed = urllib.parse.urlparse(started.authorization_url)
    query = urllib.parse.parse_qs(parsed.query)
    assert query["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert query["code_challenge_method"] == ["S256"]

    status = gmail_authorization_complete(
        workspace,
        state=query["state"][0],
        code="synthetic-code",
        credential_store=credentials,
        request_json=lambda *_args, **_kwargs: {
            "access_token": "synthetic-access-token",
            "refresh_token": "synthetic-refresh-token",
            "expires_in": 3600,
        },
    )

    assert status.connected
    assert credentials.get("gmail", workspace)["refresh_token"] == "synthetic-refresh-token"
    serialized_workspace = json.dumps(workspace.list("email_connections"), ensure_ascii=False)
    assert "synthetic-access-token" not in serialized_workspace
    assert "synthetic-refresh-token" not in serialized_workspace


def test_readonly_gmail_sync_creates_candidates_without_tracker_write(tmp_path):
    workspace = Workspace(str(tmp_path))
    credentials = MemoryCredentialStore()
    credentials.set(
        "gmail",
        workspace,
        {"access_token": "synthetic", "expires_at": time.time() + 600},
    )
    target = Target(name="某大学李四教授课题组", school="某大学")
    application = ApplicationRecord(target_id=target.target_id, status="contacted")

    result = sync_email_signal_candidates(
        workspace,
        provider="gmail",
        targets=[target],
        applications=[application],
        advisors=[],
        credential_store=credentials,
        gmail_fetcher=lambda *_args, **_kwargs: [
            """Subject: 某大学李四教授课题组 面试通知
From: lisi@example.edu
Date: 2026-08-27
请参加预推免面试，并准备成绩单。
"""
        ],
    )

    assert result.read_only
    assert result.connector_mode == "readonly_connector"
    assert result.scanned_messages == 1
    assert result.candidates[0].status == "needs_user_confirmation"
    assert application.status == "contacted"


def test_qq_imap_fetches_latest_messages_in_readonly_mode(tmp_path):
    workspace = Workspace(str(tmp_path))
    credentials = MemoryCredentialStore()
    configure_qq_imap(
        workspace,
        account="demo@qq.com",
        authorization_code="synthetic-authorization-code",
        credential_store=credentials,
    )

    class FakeImap:
        def __init__(self):
            self.selected_readonly = False
            self.logged_out = False

        def login(self, account, password):
            assert account == "demo@qq.com"
            assert password == "synthetic-authorization-code"
            return "OK", []

        def select(self, mailbox, readonly=False):
            assert mailbox == "INBOX"
            self.selected_readonly = readonly
            return "OK", []

        def search(self, _charset, criterion):
            assert criterion == "UNSEEN"
            return "OK", [b"1 2"]

        def fetch(self, message_id, _fields):
            return (
                "OK",
                [
                    (
                        b"RFC822",
                        b"Subject: Test interview\nFrom: advisor@example.edu\n"
                        b"Date: Thu, 27 Aug 2026 10:00:00 +0800\n\n"
                        b"Please attend the interview.",
                    )
                ],
            )

        def logout(self):
            self.logged_out = True
            return "BYE", []

    fake = FakeImap()
    messages = fetch_qq_messages(
        workspace,
        credential_store=credentials,
        max_messages=2,
        mailbox_filter="unseen",
        imap_factory=lambda *_args, **_kwargs: fake,
    )

    assert fake.selected_readonly
    assert "Subject: Test interview" in messages[0]
    assert "Please attend the interview." in messages[0]
    assert email_connector_status(workspace, "qq", credentials).connected


def test_browser_capture_only_saves_unverified_evidence_candidate(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
    )

    candidate = backend_main.create_browser_evidence_candidate(
        BrowserEvidenceCaptureRequest(
            source_url="https://example.edu/faculty/demo",
            page_title="Demo Advisor",
            selected_text="Research interests: trustworthy AI.",
        ),
        request,
    )

    saved = workspace.read("browser_evidence_candidates", candidate.candidate_id)
    assert saved["status"] == "candidate"
    assert saved["no_send"] is True
    assert saved["requires_user_confirmation"] is True
    assert "unverified_browser_capture" in saved["risk_tags"]
    assert not workspace.list("advisor_sources")


def test_missing_os_keyring_backend_is_reported_without_workspace_secret(tmp_path, monkeypatch):
    workspace = Workspace(str(tmp_path))
    store = KeyringCredentialStore(service_name="offer-harvester-test")

    class FailingKeyring:
        class errors:
            class KeyringError(Exception):
                pass

            class PasswordDeleteError(KeyringError):
                pass

        @staticmethod
        def get_password(*_args, **_kwargs):
            raise FailingKeyring.errors.KeyringError("unavailable")

    monkeypatch.setattr(store, "_keyring", lambda: FailingKeyring)

    status = email_connector_status(workspace, "gmail", store)

    assert not status.connected
    assert "OS keyring backend" in status.message
    assert not workspace.list("email_connections")
