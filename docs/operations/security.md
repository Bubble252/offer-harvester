# Security And Privacy

[简体中文](security.zh-CN.md)

Offer Harvester is designed for sensitive student application material. The public
repository contains code, synthetic examples, and documentation only.

## Never Commit

- `.env`, provider keys, plugin tokens, database connection strings, private keys, or cookies
- real resumes, transcripts, certificates, recommendation letters, or contact records
- raw mailbox exports or complete private email bodies
- generated materials for a real student
- private workspace directories, model checkpoints, or copied external project trees

Use `workspace/` for real local data. Use `workspace.example/` or `workspace.demo/` for
synthetic examples. Run `make security` before a pull request.

## Evidence And User Control

- Unconfirmed facts may be used in a draft only when the quality report marks them.
- Rejected facts must not be used as evidence for generated materials.
- Web-supplemented profile facts remain candidates until the user confirms them.
- Public advisor and community content is a source signal, not an official fact by default.
- Generated materials, email signals, memory promotion, tracker updates, and external sync
  require the appropriate user confirmation path.

## No-Send Boundary

The application and the P0 Skills do not automatically send contact email, submit an
application, upload an attachment, or impersonate a recommender. DSH tools are also
candidate-only and use the Offer Harvester control plane rather than directly accessing
the workspace.

## External Providers

Before enabling an LLM, embedding, reranker, OCR, cloud database, or external-agent provider,
check the privacy route and the provider's data handling terms. Keep private student
evidence on the local route unless the user has explicitly authorized a reviewed provider.
Use a separate DSH plugin token; never reuse an LLM or database credential.

## Reporting

Do not publish sensitive content in an issue. Remove names, email addresses, URLs, source
text, tokens, screenshots, and workspace paths before sharing a reproduction. Use the
maintainer's private security contact when one is configured.
