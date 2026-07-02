"""Tests for git snapshot capture."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent_co_op.git_snapshot import capture_git_snapshot, current_branch
from agent_co_op.handoff import publish, read_state


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


class TestGitSnapshot:
    def test_returns_none_outside_git_repo(self, tmp_path: Path) -> None:
        assert capture_git_snapshot(base=tmp_path) is None
        assert current_branch(base=tmp_path) is None

    def test_capture_git_snapshot(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, branch="dev")
        snapshot = capture_git_snapshot(base=tmp_path)
        assert snapshot is not None
        assert snapshot["branch"] == "dev"
        assert snapshot["base_branch"] == "main"
        assert snapshot["uncommitted"] is False
        assert "initial commit" in snapshot["last_commit"]

    def test_publish_records_git_block(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        publish("Ship it", "verify", "my-app", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        git_block = state.get("git")
        assert isinstance(git_block, dict)
        assert git_block["branch"] == "main"
        assert git_block["uncommitted"] is False

    def test_publish_detects_uncommitted_changes(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "dirty.txt").write_text("changes\n", encoding="utf-8")
        publish("Dirty tree", "plan", "my-app", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        git_block = state["git"]
        assert git_block["uncommitted"] is True
        assert "dirty.txt" in git_block["modified_files"]

    def test_role_prompt_includes_git_block(self, tmp_path: Path) -> None:
        from agent_co_op.projects import role_prompt

        _init_git_repo(tmp_path, branch="feature/x")
        publish("Feature", "implement", "my-app", base=tmp_path)
        result = role_prompt("my-app", "verifier", phase="implement", base=tmp_path)
        assert "**Branch:** feature/x" in result
