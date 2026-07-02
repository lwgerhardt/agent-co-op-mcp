"""Tests for MCP workspace path resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_co_op.mcp_server import _resolve_base, project_init
from agent_co_op.projects import init_workspace


class TestResolveBase:
    def test_explicit_workspace_path(self, tmp_path: Path) -> None:
        assert _resolve_base(str(tmp_path)) == tmp_path

    def test_env_var_overrides_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        assert _resolve_base("") == tmp_path

    def test_empty_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENT_CO_OP_ROOT", raising=False)
        assert _resolve_base("") is None


class TestMcpProjectInitWorkspace:
    def test_project_init_uses_workspace_path(self, tmp_path: Path) -> None:
        workspace = tmp_path / "repo"
        workspace.mkdir()
        result = json.loads(
            project_init("my-app", workspace_path=str(workspace))
        )
        assert (workspace / ".agent-co-op" / "my-app.json").exists()
        assert result["project_id"] == "my-app"

    def test_project_init_uses_env_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = tmp_path / "env-root"
        workspace.mkdir()
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(workspace))
        init_workspace("env-app", base=_resolve_base(""))
        assert (workspace / ".agent-co-op" / "env-app.json").exists()
