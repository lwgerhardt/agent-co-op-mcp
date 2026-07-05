"""Tests for structured CURRENT_HANDOFF.md rendering."""

from __future__ import annotations

import json
from pathlib import Path

from agent_co_op.handoff import publish, read_current_handoff, update
from agent_co_op.projects import init_project, pickup
from agent_co_op.verification import publish_for_verifier


def _write_manifest(tmp_path: Path, project_id: str, manifest: dict) -> None:
    d = tmp_path / ".agent-co-op"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{project_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


class TestHandoffStructuredRender:
    def test_plan_phase_banner_and_bootstrap(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-app",
            {
                "id": "my-app",
                "name": "My App",
                "bootstrap": ["./scripts/status.sh"],
                "roles": {},
            },
        )
        publish("Design API", "plan", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "**Phase: plan**" in content
        assert "Run bootstrap before broad file reads" in content
        assert "## Bootstrap" in content
        assert "./scripts/status.sh" in content
        assert "## Project" in content
        assert "**Name:** My App" in content
        assert "## Routing" in content
        assert "| Role | planner |" in content

    def test_implement_phase_verifier_section(self, tmp_path: Path) -> None:
        publish("Build auth", "implement", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "**Phase: implement**" in content
        assert "## Verifier" in content
        assert "Verifier owns test execution" in content
        assert "planner must not claim gates passed" in content
        assert "`agent-co-op verify run`" in content

    def test_verifier_section_with_queue(self, tmp_path: Path) -> None:
        init_project("my-app", base=tmp_path)
        manifest_path = tmp_path / ".agent-co-op" / "my-app.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["verification"] = {
            "profiles": {
                "default": {
                    "commands": [{"id": "ok", "label": "Pass", "command": "true"}]
                }
            }
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        publish_for_verifier("Build auth", "my-app", base=tmp_path)

        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "verification-queue.json" in content
        assert "**Profile:** `default`" in content

    def test_read_map_blockers_in_markdown(self, tmp_path: Path) -> None:
        publish(
            "Build API",
            "implement",
            "my-app",
            context={
                "read_map": [
                    {"file": "src/api.py", "lines": "10-40", "why": "Routes"}
                ],
                "blockers": ["Waiting on credentials"],
                "manual_checks_pending": ["Verify logout"],
            },
            base=tmp_path,
        )
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "Files to read (indexed)" in content
        assert "src/api.py:10-40 — Routes" in content
        assert "## Blockers" in content
        assert "Waiting on credentials" in content
        assert "Manual checks pending" in content

    def test_manifest_read_map_when_state_has_none(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-app",
            {
                "id": "my-app",
                "read_map": ["README.md 1-20 — setup"],
                "roles": {},
            },
        )
        publish("Plan work", "plan", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "## Files to read" in content
        assert "README.md 1-20 — setup" in content

    def test_capture_placeholders(self, tmp_path: Path) -> None:
        publish("Build feature", "plan", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "## Capture" in content
        assert "_(populated by handoff capture)_" in content

    def test_verify_phase_banner(self, tmp_path: Path) -> None:
        publish("Validate release", "verify", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "**Phase: verify**" in content
        assert "## Verifier" in content

    def test_resume_phase_banner_without_verifier(self, tmp_path: Path) -> None:
        publish("Continue work", "resume", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "**Phase: resume**" in content
        assert "## Verifier" not in content

    def test_update_re_renders_sections(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        update(
            context={"blockers": ["Needs API key"]},
            base=tmp_path,
        )
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "Needs API key" in content

    def test_pickup_returns_structured_handoff(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "## Verifier" in result
        assert "## Routing" in result
        assert "Build feature" in result

    def test_bootstrap_from_queue(self, tmp_path: Path) -> None:
        queue_path = tmp_path / ".agent-co-op" / "verification-queue.json"
        queue_path.parent.mkdir(parents=True)
        queue_path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "profile_id": "default",
                    "project_id": "my-app",
                    "bootstrap": ["./scripts/verify-setup.sh"],
                    "commands": [{"id": "ok", "label": "Pass", "command": "true"}],
                }
            ),
            encoding="utf-8",
        )
        publish("Verify work", "verify", "my-app", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "./scripts/verify-setup.sh" in content
