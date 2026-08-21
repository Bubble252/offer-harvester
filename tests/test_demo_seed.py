import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.seed_demo_workspace import build_demo_workspace  # noqa: E402


def test_seed_demo_workspace_builds_complete_case(tmp_path):
    result = build_demo_workspace(tmp_path / "workspace.demo", reset=True)

    root = Path(result["workspace"])
    assert (root / "profiles").is_dir()
    assert (root / "advisors").is_dir()
    assert (root / "targets").is_dir()
    assert (root / "matches" / f"{result['match_id']}.json").exists()
    assert (root / "generated" / f"{result['contact_email_id']}.json").exists()
    assert (root / "generated" / f"{result['interview_questions_id']}.json").exists()
    assert (root / "generated" / f"{result['ppt_outline_id']}.json").exists()
    assert (root / "presentation_tasks" / f"{result['presentation_task_id']}.json").exists()
    assert (root / "reports" / f"{result['report_id']}.json").exists()
    assert (root / "reports" / "demo_summary.md").exists()
