# Safety Rules

## Repository Boundary

- Do not commit `workspace/`, `.env`, API keys, private keys, certificates, real transcripts, real contact emails, or advisor contact logs.
- Do not copy external reference project directories into this repository.
- Keep external-project reuse documented in `NOTICE`.
- Keep generated demo data anonymous.

## Model Boundary

- Current MVP uses lightweight text API and deterministic fallback.
- Do not introduce PyTorch, local vision models, `oaib`, batch inference, or image generation unless the planning doc explicitly moves that stage forward.
- Do not use image generation to fabricate student experiences, paper results, schools, labs, advisors, or project evidence.

## Privacy Boundary

- Treat student documents as local private data.
- Store raw documents separately from confirmed structured profile data.
- Record user edits and confirmations when they affect final material facts.
