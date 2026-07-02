# Agent Handoff — Design Alignment Review

Status: review (maps LOA proposal → `agent-co-op-mcp`)  
Related: [README](../README.md), `.cursor/skills/agent-handoff/SKILL.md`

This document reviews the Legacy of Arcana (LOA) agent-handoff proposal against the
generalized **agent-co-op** package in this repository. LOA keeps repo-specific capture,
verification, and transcript tooling; agent-co-op provides the portable contract (handoff
files, routing, MCP, skill).

---

## Executive summary

| Area | LOA today | agent-co-op today | Recommendation |
|------|-----------|-------------------|----------------|
| Artifact root | `.claude/handoff/` + `docs/agent-rules/` | `.agent-co-op/` | Keep agent-co-op paths for portable package; LOA can symlink or wrap |
| Capture | Transcript-aware CLI | Manual `publish` / `update` | LOA keeps `capture_agent_handoff.py`; agent-co-op stays explicit publish |
| Verification queue | Full runner + reports | Not in scope | LOA-only until a generic profile format is agreed |
| MCP read layer | Proposed | **Partial** — status, pickup, resources | Ship resources + enriched status (this PR) |
| MCP write layer | Proposed | **Done** — publish, update, clear, restore | Align tool names in skill docs |
| Cursor skill | Proposed | **Added** — `.cursor/skills/agent-handoff/` | Primary onboarding path |
| v2 schema | Rich nested state | Flat v1.1-like state | Extend additively when LOA migrates or generic capture lands |
| History / restore | Not in LOA doc | **Done** | agent-co-op advantage; document in LOA integration map |

**Verdict:** The LOA proposal and agent-co-op share the same design principles (filesystem
as API, phase gates, cross-IDE publish surface, no transcript in git). agent-co-op already
implements Phases 1–3 of the LOA roadmap for the portable core. LOA-specific intelligence
(transcript parsing, verification queue, Claudikins ACM) should remain in LOA and call
agent-co-op for publish/status/clear.

---

## Path and artifact mapping

| LOA path | agent-co-op path | Notes |
|----------|------------------|-------|
| `.claude/handoff/handoff-state.json` | `.agent-co-op/handoff-state.json` | Same role; schema differs (see below) |
| `.claude/handoff/handoff.md` | `.agent-co-op/handoff.md` | Human summary |
| `docs/agent-rules/CURRENT_HANDOFF.md` | `.agent-co-op/CURRENT_HANDOFF.md` | Published pickup file |
| `.claude/handoff/verification-queue.json` | — | LOA-only (Phase 4) |
| `.claude/handoff/verification-report.md` | — | LOA-only |
| `.claude/handoff/handoff-history/` | `.agent-co-op/handoff-history/` | agent-co-op adds archive on republish |

LOA's `context-budget` rule ("read CURRENT_HANDOFF.md on resume") maps to the agent-handoff
skill trigger when `.agent-co-op/CURRENT_HANDOFF.md` exists.

---

## MCP tool mapping

### Core tools (LOA §4.1)

| LOA tool | agent-co-op MCP | Status |
|----------|-----------------|--------|
| `handoff_status` | `handoff_status` | Done; enriched with `active`, `paths`, `stale_warning` |
| `handoff_capture` | — | LOA CLI; use `handoff_publish` for manual capture |
| `handoff_publish` | `handoff_publish` | Done |
| `handoff_clear` | `handoff_clear` | Done |
| `handoff_read` | `handoff_status` + resources | Use `handoff://state` / `handoff://current` |
| `handoff_set_context` | `handoff_update` | Done (`context`, `objective`, `phase`, `next_steps`) |

### Planner / verifier (LOA §4.2)

| LOA tool | agent-co-op | Status |
|----------|-------------|--------|
| `handoff_publish_for_verifier` | `handoff_publish --phase implement` | Partial — no queue file in agent-co-op |
| `handoff_run_verification` | — | LOA `run_agent_verification.py` |
| `handoff_verification_report` | — | LOA-only |

### Agent project (LOA §4.3)

| LOA tool | agent-co-op MCP | Status |
|----------|-----------------|--------|
| `handoff_link_project` | `project_init` / manifest in publish | Done via `project_id` on publish |
| `handoff_routing` | `routing_show` | Done |
| `handoff_role_prompt` | `handoff_role_prompt` | Done |

### Transcript & efficiency (LOA §4.4)

| LOA tool | agent-co-op | Status |
|----------|-------------|--------|
| `handoff_resolve_transcript` | — | LOA capture internals |
| `handoff_parse_transcript` | — | LOA capture internals |
| `handoff_review_session` | — | LOA `review_claude_session.py` |

### agent-co-op extras (not in LOA doc)

| Tool | Purpose |
|------|---------|
| `handoff_pickup` | Paste-ready resume prompt (replaces manual CURRENT_HANDOFF read) |
| `handoff_history` | List archived handoffs |
| `handoff_restore` | Roll back to prior handoff without losing history |
| `project_validate` | JSON Schema check on manifests |

---

## MCP resources (LOA §4.6)

| URI | agent-co-op resource | Status |
|-----|----------------------|--------|
| `handoff://status` | `handoff://status` | Added |
| `handoff://current` | `handoff://current` | Added |
| `handoff://state` | `handoff://state` | Added |
| `handoff://queue` | — | LOA-only |
| `handoff://report` | — | LOA-only |
| `handoff://project/{id}` | — | Use `project_show` tool |

---

## Schema comparison

### agent-co-op v1 (current)

Flat top-level: `phase`, `objective`, `project_id`, `role`, `work_mode`, `next_steps`,
`context`, `published_at`, `updated_at`, optional restore metadata.

### LOA v2 (proposed)

Nested: `version`, `context.*`, `git.*`, `routing.*`, `provenance.*`.

**Migration strategy:** When LOA adopts agent-co-op as the publish target, either:

1. **Adapter layer** in LOA capture that maps v2 → v1 for publish, keeping v2 in
   `.claude/handoff/` only; or
2. **Additive v2** in agent-co-op: accept optional nested fields in `handoff-state.json`
   without breaking v1 readers (ignore unknown keys).

Recommendation: (2) when generic capture is ported; until then LOA keeps its richer state
locally and publishes a slim subset via `agent-co-op handoff publish`.

Fields worth porting first (highest resume value / lowest complexity):

- `git.branch`, `git.modified_files`, `git.uncommitted`
- `context.read_map` (line-range index)
- `context.blockers`, `context.manual_checks_pending`
- `provenance.source_ide`

Defer until verification is generic: `verification_queue`, `verify_command` profile merge.

---

## Phase gate alignment

Both systems use the same four phases: `plan`, `implement`, `verify`, `resume`.

| Phase | Default role (both) | Work mode (agent-co-op) |
|-------|---------------------|-------------------------|
| `plan` | planner | `think` — bootstrap before reads |
| `implement` | verifier | `background` — do not re-plan |
| `verify` | verifier | `background` — run checks only |
| `resume` | resume | `background` — continue next steps |

LOA's rule that **planner must not claim gates passed** belongs in the skill anti-patterns
(section 5.3 of LOA doc); agent-co-op encodes role via phase→role mapping but does not
enforce verifier-only behavior in code — the skill and published markdown discipline bullets
carry that contract.

---

## Gaps and recommended phases

### In agent-co-op (this repo)

| Phase | Work | Priority |
|-------|------|----------|
| 1 Skill | `.cursor/skills/agent-handoff/SKILL.md` | **Done (this PR)** |
| 2 Read layer | MCP resources + status enrichment | **Done (this PR)** |
| 3 Write layer | Already shipped | — |
| 5 Intelligence | Git snapshot, staleness, branch mismatch warnings | Next |
| 5 | Optional v2 nested fields | After LOA adapter agreement |

### In LOA (consumer repo)

| Phase | Work |
|-------|------|
| 0 | Keep this alignment doc updated when LOA paths change |
| 1 | Point LOA agents at agent-co-op skill + MCP |
| 4 | Wrap verification runner as MCP tools (LOA-specific) |
| 5 | Transcript capture → `handoff_publish` bridge |
| 6 | SessionStart hooks referencing `handoff://current` |

---

## Security & privacy (LOA §10)

agent-co-op already satisfies:

- Handoff state under `.agent-co-op/` with gitignore via `init`
- No transcript storage
- MCP runs locally over stdio; no remote upload

LOA must continue to strip secrets from captured bash history before any future generic
capture lands here.

---

## Acceptance criteria cross-check (LOA §14)

| Criterion | agent-co-op |
|-----------|-------------|
| "Continue interrupted work" without re-planning | Yes — skill + `handoff_pickup` / `handoff://current` |
| One tool to publish for verifier | Partial — `handoff_publish --phase implement`; queue is LOA |
| One tool to run verification queue | No — LOA scope |
| `handoff_clear` idempotent | Yes |
| Same files across IDEs | Yes — `.agent-co-op/` contract |
| No transcript in git | Yes |
| Phase implement blocks planner re-implementation | Skill + work mode discipline (not code-enforced) |
| MCP delegates to single implementation | Yes — imports `handoff`, `projects`, `routing` modules |

---

## Open questions (LOA §15) — agent-co-op answers

| Question | Answer |
|----------|--------|
| Commit handoff template? | Commit `examples/`; generated files gitignored |
| Cloud agents → local checkout command? | Recommend in `next_steps` on publish (skill workflow B) |
| Multi-repo | Out of scope; `project_dir` / cwd is monorepo root |
| Handoff chaining | agent-co-op overwrites + archives to `handoff-history/`; optional `parent_handoff_id` in v2 |
| MCP server location | `src/agent_co_op/mcp_server.py` (this repo) |
| Copilot | Skill portable; MCP via VS Code 1.99+ `mcp.json` |

---

## Integration sketch (LOA → agent-co-op)

```
LOA capture_agent_handoff.py
    │ infer objective, todos, git, transcript path
    ▼
agent-co-op handoff publish | handoff update
    │ writes .agent-co-op/CURRENT_HANDOFF.md
    ▼
Cursor / Copilot / Claude (MCP or skill)
    │ handoff_pickup | handoff://current
    ▼
LOA run_agent_verification.py (verifier only)
    │ PASS/FAIL report paths in next_steps or LOA queue

