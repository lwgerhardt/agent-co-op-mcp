---
name: agent-handoff
description: Resume interrupted agent work across Cursor, Claude Code, and Copilot using agent-co-op handoff files. Use when the user says continue interrupted work, resume handoff, hand off to Cursor, verify implementation, publish handoff, clear handoff, or when .agent-co-op/CURRENT_HANDOFF.md exists.
---

# Agent handoff (agent-co-op)

Cross-IDE continuity via `.agent-co-op/` handoff files. Prefer MCP tools when the
`agent-co-op` MCP server is configured; otherwise use the CLI (`agent-co-op …`).

## Triggers

Load this skill when:

- User: "continue interrupted work", "resume handoff", "pick up where we left off"
- User: "verify implementation", "run verifier", "hand off to Cursor/Copilot"
- User: "publish handoff", "clear handoff after merge"
- Workspace contains `.agent-co-op/CURRENT_HANDOFF.md` (recent mtime)

## MCP tools (preferred)

| Tool | When |
|------|------|
| `handoff_status` | First call on resume — phase, objective, staleness |
| `handoff_pickup` | Paste-ready resume prompt for the active handoff |
| `handoff_read` via `handoff://current` or `handoff://state` | Read published markdown or JSON |
| `handoff_publish` | New or full republish of handoff state |
| `handoff_update` | Patch objective, phase, context, or next_steps without republish |
| `handoff_clear` | After merge or explicit user request |
| `handoff_role_prompt` | Scaffold / planner / verifier / resume prompts |
| `routing_show` | Role, work mode, agent hints for current project |
| `handoff_history` / `handoff_restore` | Inspect or roll back prior handoffs |

## CLI equivalents

```bash
agent-co-op handoff status [--json]
agent-co-op pickup
agent-co-op handoff publish --objective "…" --phase plan|implement|verify|resume --project <id> [--next-steps …] [--context TEXT]
agent-co-op handoff update [--objective …] [--phase …] [--next-steps …] [--append-next-steps …] [--context …]
agent-co-op handoff clear
agent-co-op role-prompt <id> --role scaffold|planner|verifier|efficiency|resume [--phase …]
agent-co-op routing show <id> [--phase …]
agent-co-op handoff history [--limit N] [--json]
agent-co-op handoff restore --id <entry_id>
```

---

## Workflow A — Resume interrupted work

1. Call `handoff_status` (or read resource `handoff://current`).
2. If inactive (`active: false`) → ask for objective or run `handoff_publish`.
3. Read **phase** from state:
   - `plan` / `resume` → bootstrap from handoff context before broad file reads.
   - `implement` → verifier posture; do not re-implement from scratch.
   - `verify` → run validation commands from next_steps only.
4. Run `git status` and `git diff` on the working branch.
5. Execute `next_steps` in order; use `handoff_update` to mark progress.
6. On success and merge → `handoff_clear`.

Use `handoff_pickup` output as the session bootstrap when starting cold in a new IDE.

---

## Workflow B — Planner end-of-session (Claude → Cursor)

1. Confirm implementation is on a feature branch with uncommitted or committed work as intended.
2. `handoff_publish` with `--phase implement`, objective, project id, and concrete next_steps
   (include branch name and any manual checks for the human).
3. Tell the human: branch name, suggested verifier prompt (`handoff_role_prompt --role verifier`).
4. **Do not claim tests or CI passed** — that is the verifier's job.

For LOA repos with a verification profile, also run the local publish-for-verifier script
if present; agent-co-op does not manage verification queues.

---

## Workflow C — Verifier session

1. `handoff_status` + read state; confirm phase is `implement` or `verify`.
2. Confirm current git branch matches handoff next_steps / context.
3. Run verification commands listed in next_steps (or project-specific queue if LOA).
4. Reply with a short PASS/FAIL summary; cite report file paths for full logs.
5. Remind the human of any open manual checks in context or next_steps.
6. On PASS → suggest `handoff_publish --phase verify` or `handoff_clear` after merge.

---

## Workflow D — Scaffold / kickoff

1. `handoff_clear` if stale handoff exists.
2. `project_init` / `agent-co-op init <id>` for new workstreams.
3. Scout codebase; record paths and decisions in `--context` on first publish.
4. `handoff_publish --phase plan --project <id>` with bootstrap next_steps.
5. Print `handoff_role_prompt --role planner --phase plan` for the human to paste into Claude.

---

## Workflow E — Post-session efficiency

1. If the repo has `review_claude_session.py`, run it for the project id.
2. Update project manifest notes, bootstrap hints, or next publish context from findings.
3. Do not re-implement unless the user asks.

---

## Anti-patterns (do not)

- Do not re-plan from scratch when handoff + git diff answer "what's next".
- Do not bulk-read docs when handoff context lists specific paths or line ranges.
- Do not paste full verification logs into chat — cite report paths.
- Do not `handoff_clear` until merge or explicit user request.
- Planner must not run verifier-phase commands or claim CI is green.
- Do not store transcripts or secrets in handoff files.

---

## Phase → role reference

| Phase | Role | Work mode | Agent posture |
|-------|------|-----------|---------------|
| `plan` | planner | think | Bootstrap before reads |
| `implement` | verifier | background | Execute next_steps; minimal rediscovery |
| `verify` | verifier | background | Run checks only |
| `resume` | resume | background | Continue listed next_steps |

See `docs/design-alignment.md` for LOA-specific paths and verification queue integration.
