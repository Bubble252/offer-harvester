# Getting Started

[简体中文](getting-started.zh-CN.md)

## Requirements

- Python 3.11 or newer
- Git
- GNU Make
- A browser

The default path is local-first. External LLM, embedding, reranker, OAuth, database, and
heavy model services are optional and are not required for the synthetic demo.

## Install

```bash
git clone https://github.com/Bubble252/offer-harvester.git
cd offer-harvester
python -m venv .venv
. .venv/bin/activate
make install
```

If package downloads are slow in your environment, configure an approved package mirror or
your local HTTP proxy before running `make install`. Do not put proxy credentials in Git.

## Run A Blank Workspace

```bash
make run
```

Open `http://127.0.0.1:8000`. The same server exposes interactive API docs at
`http://127.0.0.1:8000/docs` and the machine-readable contract at
`http://127.0.0.1:8000/openapi.json`.

The application stores local data under `workspace/`. This directory is ignored by Git.
Copy `.env.example` to `.env` only when provider configuration is needed.

## Run The Synthetic Demo

```bash
make run-demo
```

This seeds `workspace.demo/` with anonymous, synthetic data and starts the same application.
The demo includes a profile, a public advisor-source summary, a target, a match report,
candidate materials, a PPTX, and a progress report. It does not contain real student data.

To only rebuild the demo data:

```bash
make seed-demo
```

To capture screenshots when Playwright is installed:

```bash
python tools/capture_demo_screenshots.py \
  --base-url http://127.0.0.1:8000 \
  --output-dir docs/assets/demo
```

## First Workflow

1. Open **学生资料** and paste or upload local source material.
2. Review field-level evidence and set each field to `confirmed`, `unconfirmed`,
   `rejected`, or `needs_review`.
3. Open **导师资料** and add a public URL or a manually pasted fallback.
4. Create an application target.
5. Generate a match report and candidate materials.
6. Inspect evidence references, quality findings, and risk tags.
7. Copy or download only after checking the facts yourself.

The product never treats a draft as a final submission. Generated content is candidate
material and remains behind the user confirmation and no-send boundary.

## Troubleshooting

### Port already in use

```bash
make run PORT=8001
```

Then open `http://127.0.0.1:8001`.

### Browser cannot open 127.0.0.1

Make sure the server and browser run in the same host or network namespace. A process
started inside a container, remote shell, or isolated sandbox may not be reachable from
the host browser. Bind to a deliberately configured interface only in a trusted local
environment; do not expose a private workspace to the public network by default.

### External provider fails

The local hash embedding, lexical reranker, deterministic extraction, and PPT fallback
paths are intentional. Check `/api/llm/status`, provider variables in `.env`, network
access, and the privacy route before retrying. Do not paste API keys into issue reports.

### Demo data looks stale

Stop the server, run `make seed-demo`, and start it again. The demo workspace is disposable
and should not be used for real applications.

## Verify A Checkout

```bash
make verify
```

This runs Python lint and formatting checks, tests, documentation and public-boundary
checks, OpenAPI contract validation, frontend syntax checks, compilation, and DSH adapter
contract tests.
