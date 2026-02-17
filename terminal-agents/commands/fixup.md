---
description: Fixup staged changes into the most relevant recent commit
---

Squash staged changes into the most relevant recent commit.

## Workflow

1. **Inspect staged changes**
   - Run `git diff --cached` to see staged changes
   - If nothing is staged, stop and tell the user to stage changes first

2. **Find the target commit**
   - Run `git log --oneline -20` to see recent commits
   - Match the changes to the commit most likely responsible for the code being modified (e.g. the commit that introduced the function, test, or feature being amended)
   - Prefer specificity: a commit that touched the same file/function beats a generic one

3. **Confirm with user**
   - Show the target commit (hash + message) and ask the user to confirm before proceeding
   - Stop if the user declines

4. **Fixup**
   - Create the fixup commit: `git commit --fixup=<hash>`
   - Squash it in non-interactively: `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <hash>~1`

5. **Handle conflicts** (if the rebase stops with conflicts)
   - Run `git status` to identify conflicted files
   - Read each conflicted file and understand both sides of the conflict
   - Dig deeper as needed: read surrounding code in the file, trace the history of conflicting lines with `git log -p`, check related files, and understand the intent behind each side
   - If the resolution is clear after investigation, apply it, `git add` the file, and `git rebase --continue`
   - If any conflict remains ambiguous after investigation, show the user the conflicting hunks along with your findings and ask them to decide, then continue once resolved
   - Repeat until the rebase completes

6. **Report**
   - Tell the user which commit was targeted and confirm the rebase succeeded
   - If any conflicts were resolved automatically, summarize each one: which file, what the conflict was, and how it was resolved
