# Staging

Stage files/hunks for this commit. Process files strictly one at a time, in sequence — complete diff, staging, and verification for one file before moving to the next.

## Modified tracked files

For each target file that is tracked and modified:

1. **Generate the `.updates` file:**

   ```bash
   git_stage.py --updates <file> > <temp>/<file>.updates
   ```

   This creates an editable plain-text representation of all diff hunks.
   Save this file in the system temp directory to avoid cluttering the working tree with untracked files.

2. **Read the `.updates` file** and decide which hunks belong to this commit.

   **Updates file format:**
   ```
   file: src/auth.py

   @@old 43
   old line 1
   @@new
   new line 1
   new line 2
   @@end
   ```

   - Each `@@old <line>` ... `@@new` ... `@@end` block is one change
   - Empty `@@new` section = deletion; empty `@@old` section = insertion

3. **Edit the `.updates` file** to keep only relevant hunks:

   - **Remove a hunk**: Delete the entire `@@old` ... `@@end` block
   - **Modify lines**: Edit content within `@@old` or `@@new` sections
   - **Split a hunk**: Create two blocks with separate `@@old`/`@@new`/`@@end`

4. **Apply the updates:**

   ```bash
   git_stage.py --apply <temp>/<file>.updates
   ```

   - **Success**: `.updates` file is deleted, changes are staged
   - **Failure**: `.updates` file is kept, error printed to stderr. Inspect the file for formatting errors, correct it, and retry once. If it fails again, abort staging and report the error and the `.updates` file path to the caller.

5. **Verify what was staged and what was not for this file:**

   ```bash
   git diff --cached <file>  # staged
   echo "----- UNSTAGED CHANGES -----"
   git diff <file>           # unstaged
   ```

## Untracked files

For each target file that is untracked:

1. Read the file content and decide whether it belongs to this commit.
2. If relevant: `git add <file>`

## After all files

Confirm only the intended changes are staged and the remaining unstaged changes don't contain any relevant modifications:

```bash
git diff --cached --stat   # staged
git diff --stat            # unstaged
```
