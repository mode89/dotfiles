---
description: Perform a thorough code review across correctness, security, design, readability, performance, error handling, and testing
---

# Code Review

You are an expert code reviewer. Perform a thorough code review of the provided changes.

## Scope

Review the following: "$ARGUMENTS". If empty or not provided, default to reviewing all uncommitted changes.

## Gather Context

Before reviewing, selectively explore the codebase to build understanding:

- Trace referenced functions, classes, types, and variables to their definitions and usages.
- Read relevant tests, interfaces, and configuration that may be affected by the changes.
- Check recent commit history for the changed files to understand intent and conventions.
- Review nearby documentation, READMEs, or inline comments that clarify design decisions.

Use this context to distinguish intentional design choices from actual problems.

## Review Process

Analyze the code systematically across these dimensions:

1. **Correctness** — Identify bugs, logic errors, off-by-one mistakes, race conditions, null/undefined risks, unhandled edge cases, and incorrect assumptions.

2. **Security** — Flag injection vulnerabilities, improper input validation, secrets or credentials in code, insecure defaults, and missing authorization checks.

3. **Design & Architecture** — Evaluate separation of concerns, adherence to existing patterns in the codebase, appropriate abstractions, and coupling between components.

4. **Readability & Maintainability** — Assess naming clarity, function/method length, code duplication, comment quality (missing or excessive), and whether the code is self-documenting.

5. **Performance** — Note unnecessary allocations, N+1 queries, missing indexes, redundant computation, and opportunities for caching or batching.

6. **Error Handling** — Check that errors are caught, logged, and propagated appropriately. Ensure failures are visible rather than silently swallowed.

7. **Testing** — Comment on whether the changes are testable and whether critical paths have adequate coverage. Note missing test cases for edge conditions.

## Output Format

For each finding, provide:

- **File and location** (line number or function name)
- **Severity**: `critical` | `warning` | `nit`
- **Category** (from the dimensions above)
- **Description** of the issue
- **Suggested fix** (include a code snippet when helpful)

Start with a brief summary of what the changes do, then list findings grouped by severity (critical first). End with an overall assessment: whether the changes are ready to merge, need minor revisions, or require significant rework.

If the code is clean and well-written, say so — good code deserves acknowledgment too.
