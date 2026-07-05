"""Tests for MCP support helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from agent_co_op.mcp_support import normalize_context, resolve_workspace_base


class TestMcpSupport:
    def test_normalize_structured_context(self) -> None:
        payload = normalize_context({"blockers": ["x"]})
        assert payload == {"blockers": ["x"]}

    def test_normalize_invalid_context_raises(self) -> None:
        with pytest.raises(ToolError, match="context must be"):
            normalize_context(123)

    def test_resolve_workspace_path_must_be_directory(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not-a-dir"
        file_path.write_text("x", encoding="utf-8")
        with pytest.raises(ToolError, match="not a directory"):
            resolve_workspace_base(str(file_path))

    def test_resolve_env_root_must_be_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        file_path = tmp_path / "file"
        file_path.write_text("x", encoding="utf-8")
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(file_path))
        with pytest.raises(ToolError, match="AGENT_CO_OP_ROOT"):
            resolve_workspace_base("")
