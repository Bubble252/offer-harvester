# Read-Only Mail Connectors

[简体中文](email-connectors.zh-CN.md)

Offer Harvester supports two optional, manually triggered mail connectors:

- Gmail authorization-code flow with the `gmail.readonly` scope.
- QQ Mail IMAP with a user-created IMAP authorization code.

They are for signal discovery only. A sync can create reply, interview, material-request,
rejection, offer, or waitlist **candidates**. It cannot send a message, delete mail, change
labels, download attachments, or update the tracker until the user approves a candidate.

## Credential Boundary

- Gmail tokens and QQ authorization codes are saved in the operating-system keyring through
  `keyring`, scoped to the local workspace.
- Workspace JSON stores only non-secret connection metadata, sync traces, and reviewable signal
  candidates.
- Raw mailbox exports, tokens, authorization codes, attachments, and real email content must not
  be committed to Git.
- The connectors are manual. There is no background polling, scheduler, or automatic tracker
  write in this release.

Set these local-only values in `.env` before Gmail authorization:

```dotenv
EMAIL_CREDENTIAL_SERVICE=offer-harvester.email
GMAIL_OAUTH_CLIENT_ID=
GMAIL_OAUTH_CLIENT_SECRET=
GMAIL_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/email-connectors/gmail/callback
```

## Gmail

1. Start the local Offer Harvester server and configure the redirect URI in the Gmail OAuth client.
2. Call `POST /api/email-connectors/gmail/authorize`.
3. Open the returned authorization URL in the same local browser session and complete the consent
   flow.
4. The callback stores credentials in the keyring and records only a read-only connection status.
5. Call `POST /api/email-connectors/gmail/sync` with a matching `provider` field.
6. Review each item from `/api/email-signals`, then explicitly approve or reject it.

```bash
curl -X POST http://127.0.0.1:8000/api/email-connectors/gmail/sync \
  -H 'Content-Type: application/json' \
  -d '{"provider":"gmail","max_messages":10,"query":"newer_than:90d"}'
```

## QQ Mail

1. Enable IMAP in the QQ Mail account settings and create an authorization code.
2. Send the account and authorization code to `POST /api/email-connectors/qq/configure`.
3. Call `POST /api/email-connectors/qq/sync` with `provider: "qq"`.
4. Review signal candidates before any tracker update.

```bash
curl -X POST http://127.0.0.1:8000/api/email-connectors/qq/sync \
  -H 'Content-Type: application/json' \
  -d '{"provider":"qq","max_messages":10,"mailbox_filter":"unseen"}'
```

Disconnecting a connector removes its stored keyring credential:

```bash
curl -X DELETE http://127.0.0.1:8000/api/email-connectors/gmail
```

## Failure Handling

- A missing keyring backend, missing Gmail configuration, expired OAuth state, or IMAP error is
  returned as a visible API error and leaves the tracker unchanged.
- Duplicate message-derived candidates are skipped by source hash.
- If the local process restarts during Gmail authorization, start authorization again; the PKCE
  state is intentionally memory-only and expires after ten minutes.
