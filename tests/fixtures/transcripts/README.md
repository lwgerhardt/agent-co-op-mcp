# Transcript fixtures

Synthetic `.jsonl` samples for testing transcript-assisted capture (planned `transcript.py` module; see [docs/roadmap.md](../../../docs/roadmap.md)).

| File | Format | Exercises |
|------|--------|-----------|
| [cursor-session.example.jsonl](cursor-session.example.jsonl) | Cursor agent transcript | `TodoWrite`, `StrReplace`, `Write`, `<user_query>` wrapper |
| [claude-session.example.jsonl](claude-session.example.jsonl) | Claude Code transcript | `Edit`, `Write`, `TodoWrite`, `type`/`role` fields |

Paths are fictional (`/workspace/example-project`). No real session content.

Expected extractions from `cursor-session.example.jsonl` once `parse_transcript` is implemented:

- **objective:** last user message about publishing handoff
- **active_todos:** one item `in_progress` (Add unit tests)
- **key_files_modified:** `middleware.py`, `test_jwt_middleware.py`
