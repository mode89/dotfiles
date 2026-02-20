Collection of reusable commands, skills and scripts for AI coding agents.

# Conventions

When referencing files from the working directory, use relative paths.

# Supported Agents

## Claude Code

User configuration: `~/.claude/`
- `settings.json` - Global configuration
- `commands/` - Custom slash commands (`.md` files)
- `skills/` - Custom skills
- `CLAUDE.md` - Global agent instructions

## OpenCode

User configuration: `~/.config/opencode/`
- `opencode.json` - Global configuration
- `commands/` - Custom commands (`.md` files)
- `skills/` - Custom skills
- `AGENTS.md` - Global agent instructions

> Note: The `opencode-help` skill is OpenCode-specific — sync only to OpenCode, skip for all other agents.
