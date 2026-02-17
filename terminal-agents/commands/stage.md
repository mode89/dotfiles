---
description: Stage specific git changes matching a described intent, leaving unrelated changes unstaged
---

Stage git changes relevant to the following intent: $ARGUMENTS

Only process modified tracked files (`git diff --name-only`). Do not handle untracked/new files.

## Workflow

### 1. Expand the intent

Before processing any files, read all modified files' diffs (`git diff`) to understand the full scope of changes. Formulate a clear description of what changes are relevant and what are not, noting any ambiguous cases and how to resolve them.

### 2. Process each file

**You must process files strictly one at a time, in sequence. Complete diff, staging, and verification for one file before moving to the next. Never process multiple files simultaneously.** Do not modify any files — only read diffs and run git staging commands.

For each file:

1. Get the diff:
   ```bash
   git diff <file>
   ```

2. Read each hunk (delimited by `@@` headers) and decide whether it matches the intent.

3. Stage the file:
   - **All hunks relevant** — stage the whole file at once:
     ```bash
     git add <file>
     ```
   - **Mixed relevance** — pipe per-hunk responses to `git add -p`:
     ```bash
     git add -p <file> << 'EOF'
     y
     n
     q
     EOF
     ```
     Responses: `y` (stage), `n` (skip), `q` (quit — skips remaining hunks).

   If a hunk mixes relevant and irrelevant changes, skip it with `n` and note it.

4. Verify what was staged and what was not for this file:
   ```bash
   git diff --cached <file>  # staged
   echo "----- UNSTAGED CHANGES -----"
   git diff <file>           # unstaged
   ```

### After all files:

If any hunks were skipped due to mixed content (relevant and irrelevant changes interleaved), report them so the user can handle them manually.
