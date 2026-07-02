"""Tests for handoff status reporting."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_co_op.handoff import _handoff_dir, handoff_status, publish


def _init_git_repo(path: Path, branch: str = "main") -> None:
    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=path,
        check=True,
        capture_output=True,
    )


class TestHandoffStatus:
    def test_empty_state(self, tmp_path: Path) -> None:
        status = handoff_status(base=tmp_path)
        assert status["active"] is False
        assert status["has_state"] is False
        assert status["has_current_handoff"] is False
        assert status["state"] is None
        assert "paths" in status

    def test_after_publish(self, tmp_path: Path) -> None:
        publish("Build feature", "plan", "my-app", base=tmp_path)
        status = handoff_status(base=tmp_path)
        assert status["active"] is True
        assert status["has_state"] is True
        assert status["has_current_handoff"] is True
        assert status["state"]["objective"] == "Build feature"
        assert status["phase"] == "plan"
        assert status["objective"] == "Build feature"
        assert status["project_id"] == "my-app"
        assert status["paths"]["published_md"].endswith("CURRENT_HANDOFF.md")

    def test_stale_warning(self, tmp_path: Path) -> None:
        publish("Old work", "resume", "my-app", base=tmp_path)
        state_path = _handoff_dir(tmp_path) / "handoff-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        state["published_at"] = old
        state_path.write_text(json.dumps(state), encoding="utf-8")

        status = handoff_status(base=tmp_path)
        assert status["stale_warning"] == "handoff older than 7 days"

    def test_branch_mismatch_warning(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, branch="feature/handoff")
        publish("Feature work", "implement", "my-app", base=tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "other-branch"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        status = handoff_status(base=tmp_path)
        assert "branch_mismatch_warning" in status
        assert "feature/handoff" in status["branch_mismatch_warning"]
        assert "other-branch" in status["branch_mismatch_warning"]
        assert "git checkout feature/handoff" in status["branch_mismatch_warning"]

    def test_no_branch_mismatch_when_branches_match(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, branch="main")
        publish("Main work", "plan", "my-app", base=tmp_path)

        status = handoff_status(base=tmp_path)
        assert "branch_mismatch_warning" not in status
