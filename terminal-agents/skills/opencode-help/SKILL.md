---
name: opencode-help
description: Look up official documentation for OpenCode (opencode.ai), the AI coding agent for terminal and IDE workflows, to answer questions about its features, behavior, commands, configuration, permissions, agents, tools, etc. Use this when a user asks about OpenCode.
---

# OpenCode Docs Assistant

Use this skill to retrieve accurate, up-to-date guidance from the official OpenCode docs.

## Workflow

1. Start from `https://opencode.ai/docs` to find the relevant section.
2. Navigate to the best matching docs page and fetch it.
3. Prefer the latest web docs over memory when details may have changed.
4. Answer directly and concisely.
5. Use minimal citations: include links only when helpful for verification, for non-obvious claims, or when the user asks for sources.

## Answer Quality Rules

- Distinguish documented behavior from inference.
- If docs are missing or ambiguous, say so explicitly and provide the best-effort interpretation.
- Prefer exact option names, command names, and file paths from docs.
- Keep answers practical: include short examples only when they clarify usage.
