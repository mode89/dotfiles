---
name: git-commit
description: Intelligently commit Git changes based on context and intent. Use ONLY when the user explicitly requests to commit (e.g., "commit my changes", "do a commit", "commit the auth changes"). Supports optional scope to focus on specific changes (e.g., "commit the auth changes", "commit only the UI fixes").
---

# git-commit

Only trigger when the user explicitly requests a commit. Extract any scope hint from the request (e.g., "commit the auth changes" → scope: auth-related changes).

When no explicit scope is provided:
- If staged changes exist, commit **only currently staged changes**.
- If nothing is staged, no filtering is applied — all unstaged and untracked changes are in scope.

## State Detection

```bash
git status --porcelain
```

- Staged changes exist → **Path A**
- No staged, but unstaged or untracked exist → **Path B**
- Both staged and unstaged/untracked exist → **Path A** (note the unstaged changes to the user)
- Nothing → respond: "No changes to commit."

---

## Path A: Staged Changes

1. Run `git diff --cached` to review all staged changes
2. → [Context Gathering](#context-gathering)
3. Check scope against staged changes:
   - **No scope**: commit exactly what is staged
     - do not run `git add`, `git rm`, or otherwise change staging
     - note content of remaining changes to the user
   - **Scope provided**: verify all staged changes match the scope
     - Mismatched changes found → list them, notify the user, ask for instructions: proceed or abort?
     - All match → continue
4. → [Committing](#committing)

---

## Path B: Unstaged Changes

1. Run `git diff --find-renames` and `git ls-files --others --exclude-standard` to review all unstaged and untracked changes
2. If **scope provided**: identify only the files/hunks matching the scope; note any excluded files
3. → [Context Gathering](#context-gathering) for in-scope files
4. Assess whether in-scope changes form one cohesive commit or multiple unrelated concerns
   - Use one cohesive commit only if all criteria below are true; otherwise split into multiple commits.
   - Same intent/problem solved
   - Same subsystem or concern boundary
   - Can be described with one commit subject line
   - Would likely be reverted together
5. If **multiple commits**: present proposed commits to the user (e.g., "Commit 1: auth changes in X, Y — Commit 2: UI fixes in Z"), ask for confirmation or adjustments
6. For each confirmed commit, one at a time:

   a. Stage trivial changes directly in the main agent (do not spawn subagent).
      Apply only to files whose entire change belongs to this commit:

      - Modified tracked file (all hunks in scope): `git add <file>`
      - New untracked file: `git add <file>`
      - Deleted file: `git rm <file>`
      - Rename/move without edits: `git add -A <old> <new>`
      - Rename/move with only related edits: `git add -A <old> <new>`
      - Binary file: `git add <file>`

   b. If any file appears in more than one planned commit, **partial hunk staging** is mandatory for that file. If any file in the commit needs **partial hunk staging**, spawn a general-purpose subagent only for those partial files. Use the prompt template below, substituting placeholders from the context gathered in step 3, and substitute `<skill-base-dir>` with the base directory of this skill. Wait for it to complete before proceeding.

       ```
       Stage the partial changes for this commit.

       ## Summary

       **Intent:**
       <one-paragraph description of what this commit achieves>

       **Target files:**
       - `<file>`: <which changes within this file belong to this commit, described precisely enough to identify the relevant hunks>

       **Context:**
       <key findings from context gathering — problem solved, relevant behaviour>

       ## Instructions

       Find `git_stage.py` under `<skill-base-dir>/scripts` directory, but DO NOT read it.
       Read `<skill-base-dir>/references/staging.md` and stage only the files listed above.
       Process only target files and skip every other changed file.
       ```

   c. → [Committing](#committing) the staged changes.

7. Once all changes are committed, confirm all commits landed and no changes were accidentally left behind or left staged:

   ```bash
   git log --oneline -15   # confirm commits landed
   git status              # confirm working tree is clean
   ```

---

## Committing

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <short description>

<Why: motivation or problem being solved — up to 5 sentences>

<What: implementation details — up to 5 sentences or a bullet list>

<optional footer: BREAKING CHANGE or issue refs>
EOF
)"
```

Use imperative mood. Focus on *why*, not just *what*. Subject line ≤72 chars, body lines ≤72 chars.
Do not add `Co-Authored-By` or any agent attribution footer.

**Types**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code restructuring without changing behavior
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates
- `ci`: CI/CD configuration changes
- `build`: Build system or external dependency changes

Report the resulting commit hash and subject line.

---

## Context Gathering

Be thorough in understanding context, but surgical in what you read — use search to find exactly what you need rather than reading entire files.

- Read surrounding code (20–50 lines around changes) in modified files
- Look up key symbols in the diff — find definitions of *used* symbols; find call sites of *modified* symbols
- Check recent history: `git log --oneline -n 10 -- <file>`
- If the motivation behind changed lines is unclear, use `git blame -L <start>,<end> <file>` to understand when/why they were introduced
- Check for test files covering the modified code — they document intended behavior
- Note any TODO/FIXME comments near the changes
