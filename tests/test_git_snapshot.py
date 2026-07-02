"""Tests for git snapshot capture."""

from __future__ import annotations

from pathlib import Path

from agent_co_op.git_snapshot import capture_git_snapshot, current_branch
from agent_co_op.handoff import publish, read_state

from git_helpers import init_git_repo, requires_git


class TestGitSnapshot:
    def test_returns_none_outside_git_repo(self, tmp_path: Path) -> None:
        assert capture_git_snapshot(base=tmp_path) is None
        assert current_branch(base=tmp_path) is None

    @requires_git
    def test_capture_git_snapshot(self, tmp_path: Path) -> None:
        init_git_repo(tmp_path, branch="dev")
        snapshot = capture_git_snapshot(base=tmp_path)
        assert snapshot is not None
        assert snapshot["branch"] == "dev"
        assert snapshot["base_branch"] == "main"
        assert snapshot["uncommitted"] is False
        assert "initial commit" in snapshot["last_commit"]

    @requires_git
    def test_publish_records_git_block(self, tmp_path: Path) -> None:
        init_git_repo(tmp_path)
        publish("Ship it", "verify", "my-app", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        git_block = state.get("git")
        assert isinstance(git_block, dict)
        assert git_block["branch"] == "main"
        assert git_block["uncommitted"] is False

    @requires_git
    def test_publish_detects_uncommitted_changes(self, tmp_path: Path) -> None:
        init_git_repo(tmp_path)
        (tmp_path / "dirty.txt").write_text("changes\n", encoding="utf-8")
        publish("Dirty tree", "plan", "my-app", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        git_block = state["git"]
        assert git_block["uncommitted"] is True
        assert "dirty.txt" in git_block["modified_files"]

    @requires_git
    def test_role_prompt_includes_git_block(self, tmp_path: Path) -> None:
        from agent_co_op.projects import role_prompt

        init_git_repo(tmp_path, branch="feature/x")
        publish("Feature", "implement", "my-app", base=tmp_path)
        result = role_prompt("my-app", "verifier", phase="implement", base=tmp_path)
        assert "**Branch:** feature/x" in result
