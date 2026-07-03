# Agent handoff — improvement roadmap

Related: [README](../README.md), agent-handoff skills in `.cursor/skills/`, `.github/skills/`, and `.claude/skills/`

Ideas for evolving **agent-co-op** as a portable cross-IDE handoff layer. This repo stays
generic — consumer projects can add their own capture scripts, verification runners, or
IDE plugins on top.

---

## Problem

Long agent sessions fail in predictable ways:

| Trigger | Symptom | Cost |
|---------|---------|------|
| Context window saturation | Agent forgets early decisions, re-reads files | Token waste, drift |
| Session limits / hard stops | Work stops mid-implementation | Lost thread |
| IDE switch (Claude → Cursor → Copilot) | No shared resume contract | Duplicate discovery |
| Planner → verifier handoff | Planner claims tests pass; verifier re-implements | Wrong work, merge risk |
| Human interruption | Partial git state, unclear next step | Resume friction |

**Goals:** resume (don't restart), role clarity (planner vs verifier vs resume), cross-IDE
contract, token efficiency (small index + paths on disk), human in the loop for merges.

**Non-goals:** replacing git, auto-commit/push without human intent, storing full
transcripts in the repo.

---

## Current state

| Component | Path | Role |
|-----------|------|------|
| Handoff core | `src/agent_co_op/handoff.py` | Publish, update, clear, history, restore |
| Projects | `src/agent_co_op/projects.py` | Manifests, init, pickup, role prompts |
| Routing | `src/agent_co_op/routing.py` | Roles, work modes, phase→role |
| CLI | `agent-co-op` | All operations from the shell |
| MCP server | `agent-co-op-mcp` | Typed tools over stdio |
| Agent skills | `.cursor/skills/`, `.github/skills/`, `.claude/skills/` | Resume / publish / verify workflows |

### Artifact contract

| File | Purpose | Git |
|------|---------|-----|
| `.agent-co-op/<project-id>.json` | Project manifest | Commit |
| `.agent-co-op/verification-queue.json` | Verification command queue (from profile) | Ignore |
| `.agent-co-op/verification-report.json` | Machine-readable verify results | Ignore |
| `.agent-co-op/verification-report.md` | Human-readable verify results | Ignore |
| `.agent-co-op/handoff-state.json` | Machine-readable state | Ignore (via `init`) |
| `.agent-co-op/handoff.md` | Human summary | Ignore |
| `.agent-co-op/CURRENT_HANDOFF.md` | Published pickup file | Ignore |
| `.agent-co-op/handoff-history/` | Archived prior states | Ignore |

### Phases

`plan` → `implement` → `verify` → `resume` — each maps to a default role and work mode
(see README work-mode table).

---

## Design principles

1. **Filesystem as API** — MCP and CLI read/write the same paths; no parallel state store.
2. **Idempotent capture** — republish archives prior state to history; no conflicting versions.
3. **Explicit over inferred** — CLI/MCP flags override inference when provided.
4. **Small published surface** — `CURRENT_HANDOFF.md` is the human/agent entry point.
5. **Clear lifecycle** — publish → resume → clear after merge/success.
6. **Profile-aware** — project id, role notes, and routing travel with the handoff.
7. **Fail loud** — missing handoff returns clear errors; stale handoff should warn via status.

---

## Shipped today

| Capability | CLI | MCP |
|------------|-----|-----|
| Publish handoff | `handoff publish` | `handoff_publish` |
| Patch without republish | `handoff update` | `handoff_update` |
| Status | `handoff status` | `handoff_status` |
| Clear | `handoff clear` | `handoff_clear` |
| History / restore | `handoff history`, `handoff restore` | `handoff_history`, `handoff_restore` |
| Pickup prompt | `pickup` | `handoff_pickup` |
| Role prompt | `role-prompt` | `handoff_role_prompt` |
| Routing | `routing show` | `routing_show` |
| Project init / validate | `init`, `project validate` | `project_init`, `project_validate` |

---

## Potential improvements

Prioritized ideas for future work. None are required for the core contract to work today.

### Near term

| Idea | Benefit | Notes |
|------|---------|-------|
| Git snapshot in state | Resume knows branch, dirty tree, last commit | Add optional `git` block to state JSON |
| Branch mismatch warning | Catch resume on wrong branch | Extend `handoff_status` |
| MCP read resources | Low-overhead reads | `handoff://status`, `handoff://current`, `handoff://state` |
| Staleness warning | Avoid stale resumes | Warn when handoff age > N days |
| SessionStart hint | Auto-suggest resume when handoff is fresh | Cursor rule or hook doc |

### Medium term

| Idea | Benefit | Notes |
|------|---------|-------|
| Richer state schema (v2) | `read_map`, `blockers`, `recent_decisions`, `provenance` | Additive; v1 readers ignore unknown keys |
| Transcript-assisted capture | Infer todos, edited paths, failed commands | Optional module; store path only, never content in git |
| Verification profile + queue | Planner publishes queue; verifier runs one MCP call | Generic JSON queue format; runner shells out to profile commands |
| `handoff_capture` MCP tool | Single capture entry point | Delegates to capture module when present |

### Nice to have

| Idea | Benefit | Notes |
|------|---------|-------|
| `handoff_should_capture` heuristic | Suggest capture before context saturation | Context % estimate, session length, uncommitted count |
| Session efficiency review | Tune bootstrap and read maps post-session | Reads transcripts locally; writes report paths only |
| Local metrics JSONL | Tune profiles from publish→verify timing | Gitignored; not a CI gate |
| Auto-threshold capture plugin | IDE-specific complement to MCP | Document integration point; out of scope for core package |

---

## MCP tools (future sketch)

| Tool | Description |
|------|-------------|
| `handoff_capture` | Capture session state (optional transcript path, overrides) |
| `handoff_publish_for_verifier` | Publish implement-phase handoff + verification queue |
| `handoff_run_verification` | Execute queue; return PASS/FAIL summary |
| `handoff_verification_report` | Read last verification report paths |
| `handoff_resolve_transcript` | Find newest agent jsonl for cwd (local only) |
| `handoff_parse_transcript` | Return todos/edits preview without writing handoff |
| `handoff_review_session` | Efficiency report from a completed session |

New write tools should delegate to Python modules in this repo — not reimplement queue
formats or routing.

### Future MCP resources

| URI | Content |
|-----|---------|
| `handoff://status` | Compact JSON status |
| `handoff://current` | Rendered `CURRENT_HANDOFF.md` |
| `handoff://state` | Full `handoff-state.json` |
| `handoff://queue` | Verification queue JSON |
| `handoff://report` | Latest verification report |
| `handoff://project/{id}` | Project manifest summary |

---

## Target state schema (v2 sketch)

Extend current flat JSON additively:

```json
{
  "version": "2.0",
  "phase": "implement",
  "objective": "…",
  "project_id": "my-app",
  "published_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "context": {
    "progress_summary": ["bullet"],
    "recent_decisions": [{"decision": "", "rationale": "", "at": "ISO-8601"}],
    "read_map": [{"file": "", "lines": "1-80", "why": ""}],
    "blockers": ["string"],
    "manual_checks_pending": ["string"]
  },
  "git": {
    "branch": "",
    "base_branch": "main",
    "modified_files": [],
    "uncommitted": true,
    "last_commit": "sha short message"
  },
  "provenance": {
    "captured_by": "cli|mcp",
    "source_ide": "cursor|claude|copilot",
    "transcript_path": ""
  }
}
```

v1 fields remain valid; nested blocks are optional.

---

## Security & privacy

| Data | Rule |
|------|------|
| Transcripts | Local IDE dirs only; handoff stores path, never content in git |
| Handoff state | `.agent-co-op/` gitignored via `init` |
| Secrets | Never capture env or command output containing secrets |
| MCP | Local stdio only; no remote upload by default |

---

## Cross-IDE behavior

| Scenario | Capturer | Resume reader |
|----------|----------|---------------|
| Session limit → new IDE | `handoff publish` | Skill + `handoff_pickup` |
| Mid-session IDE switch | publish before switch | Read `CURRENT_HANDOFF.md` or MCP |
| Cloud agent → local human | publish + branch in next_steps | `handoff status` |
| Same IDE, new session | history / restore optional | `handoff pickup` |

---

## Suggested implementation order

1. ~~MCP read resources + enriched status~~ (shipped)
2. ~~Git snapshot + branch mismatch warnings~~ (shipped)
3. ~~Project manifest v2 schema + verification queue~~ (shipped — #31, #16, #43)
4. ~~Structured handoff markdown sections~~ (shipped — #21, #43)
5. ~~Verification CLI runner → publish-for-verifier → MCP tools~~ (shipped — #18, #20, #43)
6. Transcript-assisted capture (#24)
7. Multi-project registry + bootstrap CLI (#44, #45)
8. v2 manifest workflow fields in role prompts (read_map, bootstrap, role notes)
