# SessionStart / resume hint patterns

When a fresh handoff exists, prepend a short resume hint at session start so agents
check `.agent-co-op/` before broad discovery.

Transcripts stay in local IDE directories only — reference handoff paths, never
transcript content, in rules or hooks.

See also: [README](../README.md), [roadmap](roadmap.md).

---

## Cursor rule snippet

Add to `.cursor/rules/agent-handoff.mdc` (or a user rule):

```markdown
When `.agent-co-op/CURRENT_HANDOFF.md` exists and was updated within the last 7 days:

1. Run `agent-co-op handoff status --json` (or MCP `handoff_status` / `handoff://status`)
2. If `active` is true, read `CURRENT_HANDOFF.md` before broad file exploration
3. Use `agent-co-op pickup` or MCP `handoff_pickup` for the resume prompt
4. Do not re-implement work listed in next steps unless verification fails
```

Set `AGENT_CO_OP_ROOT` to the workspace root in your MCP server config so tools
resolve the correct `.agent-co-op/` directory.

---

## Claude Code SessionStart hook (sketch)

In `.claude/settings.json` or project hooks config:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "test -f .agent-co-op/CURRENT_HANDOFF.md && echo 'Active handoff found — run: agent-co-op pickup'"
          }
        ]
      }
    ]
  }
}
```

Prefer MCP read resources (`handoff://status`) when the agent-co-op MCP server is
configured — lower overhead than shelling out.

---

## VS Code / Copilot instruction pattern

Add to `.github/copilot-instructions.md` or workspace instructions:

```markdown
## Agent handoff

If `.agent-co-op/CURRENT_HANDOFF.md` exists:

- Check handoff status first (`agent-co-op handoff status --json`)
- Resume from the published objective and next steps
- Publish an updated handoff before long IDE switches or session limits
- Clear handoff after merge: `agent-co-op handoff clear`
```

Install the agent-handoff skill from `.github/skills/agent-handoff/SKILL.md` for
full resume / publish / verify workflows.

---

## When not to hint

Skip the resume hint when:

- `handoff status` reports `active: false`
- `stale_warning` is present and the user has not confirmed resume
- `branch_mismatch_warning` is present — checkout the stored branch first
