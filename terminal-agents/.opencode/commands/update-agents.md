---
description: Sync commands and skills to all supported agents
---

# Updating Agents

1. **Scan config folders** - Check each supported agent for its user config
   directory and identify which are present on this system.

2. **Sync files** - For each present agent, compare timestamps or hashes to detect outdated files, then:
   - Symlink commands -> agent-specific commands directory
   - Symlink skills -> agent-specific skills directory
   - Patch files only when the agent requires a different format or structure
   - Skip files with conflicts; report them instead of updating

   **Conflicts** (do not update, report as conflicted):
   - Destination is a regular file (not a symlink)
   - Destination is a symlink not pointing to the source file
   - Destination is newer than source

   **Not conflicts**:
   - Destination is a symlink pointing to source -> skip (up to date)
   - Destination missing -> create symlink

   **Unmanaged files** (report separately):
   - Files in agent configs that do not originate from this repo

3. **Report changes** - For each agent, report:
   - Added: new files synced
   - Updated: files replaced with newer source
   - Skipped: up-to-date files
   - Conflicted: files that could not be updated
   - Unmanaged: files not originating from this repo

## Rules

Files to sync:
- `commands/*`
- `skills/*`

**Exclusions**: Check for any exceptions before syncing (e.g., `opencode-help` skill is OpenCode-only).

Manual mode only: use explicit hardcoded shell commands (you may chain with `&&` and `||`).
Do not use scripts or iteration constructs (`for`, `while`, `xargs`, `python`, `sh -c`, heredoc-driven logic).
If manual execution becomes impractical, stop and ask one question before changing approach.

## Example Report

```markdown
## Added

**Claude**
- Skills: new-skill

## Updated

**Claude**
- Commands: commit.md
**OpenCode**
- Commands: commit.md
- Skills: skill-creator

## Skipped

**Claude**
- Commands: review-code.md, fixup.md, stage.md
- Skills: skill-creator
**OpenCode**
- Commands: review-code.md, fixup.md, stage.md
- Skills: skill-creator, opencode-help

## Unmanaged

**Claude**
- Skills: paimel-docs

## Conflicted

**OpenCode**
- Skills: example-skill (destination is a regular file)
```
