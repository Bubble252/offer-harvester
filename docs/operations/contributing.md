# Contribution Guide

[简体中文](contributing.zh-CN.md)

## Development Loop

1. Check the branch and working tree.
2. Read the relevant public guide and source module.
3. Keep changes within the owning module and preserve evidence/privacy boundaries.
4. Add focused tests and update both public language files when behavior is user-facing.
5. Run `make verify`.
6. Create one descriptive Conventional Commit and open a pull request.

## Useful Commands

```bash
make install
make run
make seed-demo
make verify
```

Use explicit `WORKSPACE_DIR` or `workspace.demo` when running locally. Never use a real
student workspace in screenshots or tests.

## Architecture Rules

- Python FastAPI remains the control plane.
- Skills and external runtimes call stable adapters; they do not bypass storage or
  EvidenceAudit.
- New candidate-producing behavior defaults to `no_send`.
- A new public API needs a Pydantic model, an OpenAPI category/summary, a contract test,
  bilingual documentation, and a changelog entry.
- Heavy dependencies belong in optional extras or adapter boundaries with a fallback.

## Pull Requests

Use the repository PR template. Explain What, Why, How, Testing, Privacy and Boundaries,
and Rollback. Keep unrelated refactors out of feature commits. Do not rewrite pushed
public history.

## Commit Format

```text
feat(scope): concise result
```

For behavior, privacy, data-model, or integration changes, the body must include:

```text
背景：
- Why the change is needed.

变更：
- What was changed and where.

验证：
- Commands and manual checks.

边界：
- Privacy, fallback, compatibility, and known limits.
```

## New Skill Checklist

- Define one bounded user task.
- Add `SKILL.md`, references, schema/fixtures, and deterministic validation where useful.
- Add a catalog entry with `no_send` and write permissions.
- Use a controlled adapter for product Skills.
- Add UI only after input/output and safety boundaries are stable.
