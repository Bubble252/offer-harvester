# Release Guide

[简体中文](release.zh-CN.md)

## Version Policy

The repository is in the `0.y.z` stage. Use Semantic Versioning:

- patch: compatible bug or documentation fixes
- minor: additive user-facing capability
- major: reserved for the post-MVP compatibility contract
- `-rc.N`: release candidate requiring manual acceptance

The current public candidate is `0.2.0-rc.1`. It is not a stable `v1.0.0`.

## Release Gate

Before tagging or publishing:

```bash
make verify
```

Also perform:

- Open the blank app and synthetic demo in a browser.
- Check `/docs`, `/openapi.json`, Skill Lab, and DSH configuration examples.
- Confirm no real data, secrets, private paths, oversized binaries, or copied source trees
  are tracked.
- Confirm README, Chinese README, CHANGELOG, screenshots, and public docs describe the same
  implemented behavior.
- Record any known limits and migration notes.

## Candidate Workflow

1. Update `pyproject.toml`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, and public docs.
2. Run `make verify` and complete manual demo acceptance.
3. Create a release commit with background, changes, verification, and boundaries.
4. Push the feature branch and review the pull request.
5. After approval, create an annotated tag such as `v0.2.0-rc.1` on the merged commit.
6. Publish GitHub Release notes using `.github/release.yml`.

Do not create downloads, Docker, PyPI, npm, or benchmark badges unless the corresponding
artifact and source are real and reproducible.

## Rollback

Prefer a new fix commit. If a candidate is unsafe, mark the GitHub release as pre-release,
document the issue, disable the affected optional integration, and publish a corrected
candidate. Do not force-push a public branch.
