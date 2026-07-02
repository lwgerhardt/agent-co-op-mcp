"""Smoke tests for CLI subcommands."""

from __future__ import annotations

from pathlib import Path

from agent_co_op.cli import build_parser, cmd_handoff_status, cmd_init, cmd_project_init


class TestCliParser:
    def test_init_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["init", "my-app", "--name", "My App", "--no-gitignore"]
        )
        assert args.command == "init"
        assert args.project_id == "my-app"
        assert args.name == "My App"
        assert args.no_gitignore is True

    def test_handoff_status_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["handoff", "status", "--json"])
        assert args.command == "handoff"
        assert args.handoff_command == "status"
        assert args.json is True

    def test_project_init_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "project",
                "init",
                "my-app",
                "--name",
                "My App",
                "--description",
                "Demo",
            ]
        )
        assert args.command == "project"
        assert args.project_command == "init"
        assert args.project_id == "my-app"
        assert args.name == "My App"

    def test_project_show_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["project", "show", "my-app"])
        assert args.project_command == "show"
        assert args.project_id == "my-app"


class TestCliHandlers:
    def test_init_bootstraps_workspace(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(["init", "my-app", "--name", "My App"])
        assert cmd_init(args) == 0
        assert (tmp_path / ".agent-co-op" / "my-app.json").exists()
        assert (tmp_path / ".gitignore").exists()
        captured = capsys.readouterr()
        assert "Next steps:" in captured.out
        assert "handoff publish" in captured.out

    def test_handoff_status_json_without_state(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(["handoff", "status", "--json"])
        assert cmd_handoff_status(args) == 0
        captured = capsys.readouterr()
        assert '"has_state": false' in captured.out

    def test_project_init_creates_manifest(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(["project", "init", "my-app", "--name", "My App"])
        assert cmd_project_init(args) == 0
        assert (tmp_path / ".agent-co-op" / "my-app.json").exists()

    def test_project_init_refuses_duplicate(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(["project", "init", "my-app"])
        assert cmd_project_init(args) == 0
        assert cmd_project_init(args) == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err
