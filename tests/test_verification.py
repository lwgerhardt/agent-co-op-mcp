"""Tests for verification queue and runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_co_op.projects import init_project
from agent_co_op.verification import (
    VerificationError,
    publish_for_verifier,
    queue_from_profile,
    queue_path,
    report_json_path,
    run_verification,
    validate_queue_data,
    verification_report,
    write_queue,
)


def _sample_queue(project_id: str = "my-app") -> dict:
    return {
        "version": "1.0",
        "profile_id": "default",
        "project_id": project_id,
        "commands": [
            {"id": "ok", "label": "Always pass", "command": "true"},
            {"id": "fail", "label": "Always fail", "command": "false"},
        ],
        "manual_checks": ["Review UI manually"],
    }


class TestVerificationQueue:
    def test_validate_queue_data(self) -> None:
        report = validate_queue_data(_sample_queue())
        assert report["valid"] is True

    def test_validate_rejects_missing_commands(self) -> None:
        report = validate_queue_data({"version": "1.0", "profile_id": "default"})
        assert report["valid"] is False

    def test_queue_from_profile(self, tmp_path: Path) -> None:
        manifest = {
            "id": "my-app",
            "verification": {
                "profiles": {
                    "default": {
                        "commands": [
                            {
                                "id": "lint",
                                "label": "Lint",
                                "command": "true",
                            }
                        ],
                        "manual_checks": ["Manual gate"],
                    }
                }
            },
        }
        d = tmp_path / ".agent-co-op"
        d.mkdir(parents=True)
        (d / "my-app.json").write_text(json.dumps(manifest), encoding="utf-8")

        queue = queue_from_profile("my-app", base=tmp_path)
        assert queue["profile_id"] == "default"
        assert queue["commands"][0]["id"] == "lint"
        assert queue["manual_checks"] == ["Manual gate"]

    def test_publish_for_verifier(self, tmp_path: Path) -> None:
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
        assert queue_path(tmp_path).exists()

    def test_run_verification_pass(self, tmp_path: Path) -> None:
        queue = {
            "version": "1.0",
            "profile_id": "default",
            "project_id": "my-app",
            "commands": [{"id": "ok", "label": "Pass", "command": "true"}],
        }
        write_queue(queue, base=tmp_path)
        summary = run_verification(base=tmp_path)
        assert summary["overall"] == "PASS"
        assert report_json_path(tmp_path).exists()
        assert verification_report(base=tmp_path)["found"] is True

    def test_run_verification_fail(self, tmp_path: Path) -> None:
        queue = {
            "version": "1.0",
            "profile_id": "default",
            "project_id": "my-app",
            "commands": [{"id": "fail", "label": "Always fail", "command": "false"}],
        }
        write_queue(queue, base=tmp_path)
        summary = run_verification(base=tmp_path, stop_on_failure=True)
        assert summary["overall"] == "FAIL"
        assert len(summary["results"]) == 1

    def test_run_verification_missing_queue(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            run_verification(base=tmp_path)

    def test_queue_from_profile_missing(self, tmp_path: Path) -> None:
        init_project("my-app", base=tmp_path)
        with pytest.raises(VerificationError):
            queue_from_profile("my-app", base=tmp_path)
