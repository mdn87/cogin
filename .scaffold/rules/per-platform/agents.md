# Generic AGENTS.md Platform Rules (Cursor, Windsurf)

## File Targets

- Agent rules → `.agents/rules.md`
- Command whitelist → `.agents/always-approve-whitelisted-commands.md`

## rules.md Structure

Uses frontmatter format with `trigger: always_on` followed by project context, workflow notes, and operating rules.

## Rendering Notes

- Include both PowerShell and bash commands in whitelist
- Support broader command formats than Claude Code
- Reference `.scaffold/` paths for orchestration
