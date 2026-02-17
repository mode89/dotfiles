Collection of reusable commands, skills and scripts for AI coding agents.

# Supported Agents

## Claude Code

User configuration: `~/.claude/`
- `commands/` - Custom slash commands (`.md` files)
- `skills/` - Custom skills
- `CLAUDE.md` - Global agent instructions

## OpenCode

User configuration: `~/.config/opencode/`
- `command/` - Custom commands (`.md` files)
- `AGENTS.md` - Global agent instructions

> Note: The `opencode-help` skill is OpenCode-specific — sync only to OpenCode, skip for all other agents.

# Updating Agents

To sync prompts and commands to all supported agents:

1. **Scan config folders** — Check each supported agent for its user config
   directory and identify which are present on this system.

2. **Sync files** — For each present agent, compare timestamps or hashes to
   detect outdated files, then:
   - Symlink commands → agent-specific commands directory
   - Symlink skills → agent-specific skills directory
   - Patch files only when the agent requires a different format or structure
   - Skip files with conflicts (e.g. destination is newer, symlink points
     elsewhere, unexpected file type); report them instead of updating

3. **Report changes** — List which files were added, updated, skipped (up to
   date), or conflicted for each agent.
