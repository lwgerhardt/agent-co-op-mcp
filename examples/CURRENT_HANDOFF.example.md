# Handoff — my-saas / implement

**Objective:** Add user authentication with JWT tokens
**Role:** verifier
**Work mode:** background — Throughput — run scripts, verify, resume; minimal reads

**Phase: implement** — Verifier owns test execution; planner must not claim gates passed.

## Project
**Name:** My SaaS App

## Bootstrap

```bash
./scripts/project-status.sh
```

## Verifier
Verifier owns test execution. Planner must not claim gates passed without running `agent-co-op verify run`.
**Queue:** `.agent-co-op/verification-queue.json`
**Profile:** `default`
**Run:** `agent-co-op verify run`

## Routing

| | |
|---|---|
| Role | verifier |
| Phase | implement |
| Agent | cursor |
| Model tier | medium |
| Work mode | background |

## Files to read (indexed)
- src/auth/login.py:1-80 — Core login flow

## Blockers
- Waiting on OAuth client id from platform team

## Manual checks pending
- Verify logout clears session cookie

## Context discipline
- Rely on existing handoff state for orientation
- Skip broad codebase reads; act on what you already know
- Focus on executing tasks and verifying results

## Tool discipline
- Run terminal commands to execute and verify
- Write files only as needed by the task
- Search files when a specific location is unknown

## Next steps
- Run `agent-co-op verify run`
- Review manual checks in the verification report

## Capture

### Todos
_(populated by handoff capture)_

### Files touched
_(populated by handoff capture)_

*Published at 2026-07-02T06:00:00+00:00*
