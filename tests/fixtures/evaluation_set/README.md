# Evaluation Set

This directory contains the fixed regression set for the project.

Rules:

- Use anonymous, short fixtures only.
- Keep full text local to tests; do not add real user documents here.
- Use these files for deterministic unit tests and local smoke checks.
- Use live web sources only in the future `16E` live test runner.
- Policy fixtures are structural baselines; replace them with school-specific 2026 notices when you want a stricter benchmark set.

Structure:

- `teacher_pages/`: anonymized public teacher-page summaries
- `policy_pages/`: anonymized current-year policy/notice summaries
- `email_signals/`: read-only email fixtures for signal detection
- `student_profiles/`: anonymous student profile samples
- `manifest.json`: file list and metadata
