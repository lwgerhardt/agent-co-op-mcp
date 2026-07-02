"""Tests for routing module — phase→role, work mode resolution, routing dicts."""

from __future__ import annotations

import pytest

from agent_co_op.routing import (
    VALID_PHASES,
    VALID_ROLES,
    load_defaults,
    phase_to_role,
    resolve_routing,
    resolve_work_mode,
)


class TestPhaseToRole:
    def test_plan_maps_to_planner(self) -> None:
        assert phase_to_role("plan") == "planner"

    def test_implement_maps_to_verifier(self) -> None:
        assert phase_to_role("implement") == "verifier"

    def test_verify_maps_to_verifier(self) -> None:
        assert phase_to_role("verify") == "verifier"

    def test_resume_maps_to_resume(self) -> None:
        assert phase_to_role("resume") == "resume"

    def test_unknown_phase_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown phase"):
            phase_to_role("deploy")

    def test_all_valid_phases_covered(self) -> None:
        for phase in VALID_PHASES:
            role = phase_to_role(phase)
            assert role in VALID_ROLES


class TestResolveWorkMode:
    def test_plan_plus_planner_overrides_to_think(self) -> None:
        assert resolve_work_mode("planner", phase="plan") == "think"

    def test_planner_without_phase_uses_default(self) -> None:
        assert resolve_work_mode("planner") == "default"

    def test_verifier_uses_background(self) -> None:
        assert resolve_work_mode("verifier") == "background"

    def test_scaffold_uses_long_context(self) -> None:
        assert resolve_work_mode("scaffold") == "longContext"

    def test_efficiency_uses_background(self) -> None:
        assert resolve_work_mode("efficiency") == "background"

    def test_resume_uses_background(self) -> None:
        assert resolve_work_mode("resume") == "background"

    def test_implement_verifier_still_background(self) -> None:
        assert resolve_work_mode("verifier", phase="implement") == "background"

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            resolve_work_mode("ghost")

    def test_unknown_phase_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown phase"):
            resolve_work_mode("planner", phase="deploy")


class TestResolveRouting:
    def test_returns_expected_keys(self) -> None:
        info = resolve_routing("planner", phase="plan", project_id="test")
        assert info["role"] == "planner"
        assert info["phase"] == "plan"
        assert info["project_id"] == "test"
        assert info["work_mode"] == "think"
        assert info["agent"] == "claude"
        assert info["model_tier"] == "high"
        assert isinstance(info["context_discipline"], list)
        assert isinstance(info["tool_discipline"], list)
        assert len(info["context_discipline"]) > 0
        assert len(info["tool_discipline"]) > 0

    def test_verifier_implement(self) -> None:
        info = resolve_routing("verifier", phase="implement")
        assert info["work_mode"] == "background"
        assert info["agent"] == "cursor"

    def test_no_phase(self) -> None:
        info = resolve_routing("planner")
        assert info["phase"] is None
        assert info["work_mode"] == "default"

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            resolve_routing("ghost")


class TestLoadDefaults:
    def test_defaults_has_required_keys(self) -> None:
        d = load_defaults()
        assert "work_modes" in d
        assert "role_work_modes" in d
        assert "phase_work_mode_overrides" in d
        assert "defaults" in d

    def test_all_work_modes_present(self) -> None:
        d = load_defaults()
        for mode in ("background", "think", "longContext", "default"):
            assert mode in d["work_modes"]

    def test_work_mode_has_context_and_tools(self) -> None:
        d = load_defaults()
        for mode, info in d["work_modes"].items():
            assert "context" in info, f"work_mode {mode} missing context"
            assert "tools" in info, f"work_mode {mode} missing tools"
            assert "description" in info, f"work_mode {mode} missing description"
