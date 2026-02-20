#!/usr/bin/env python3

# pylint: disable=too-many-lines

# Test: pytest git_stage.py
# Lint: pylint --max-line-length=80 git_stage.py

"""
git_stage.py: Convert diff hunks to an editable plain-text format, then apply
selections via `git apply --cached`.

Usage:
    git_stage.py --updates <file>       # writes updates file to stdout
    git_stage.py --apply <file>.updates # applies and stages
                                        # deletes file on success
"""

import argparse
import re
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and dispatch to --updates or --apply command."""
    parser = argparse.ArgumentParser(
        description="Stage selected diff hunks via an editable updates file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--updates", metavar="FILE", help="Generate updates file from diff"
    )
    group.add_argument(
        "--apply", metavar="UPDATES_FILE", help="Apply updates file and stage"
    )
    args = parser.parse_args()

    if args.updates:
        cmd_updates(args.updates)
    else:
        cmd_apply(args.apply)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Hunk:
    """A single @@ hunk from a unified diff."""

    old_start: int  # 1-based line number in old file
    old_count: int
    new_start: int  # 1-based line number in new file
    new_count: int
    lines: list[str]  # raw lines including ' ', '+', '-' prefixes


@dataclass
class ChangeGroup:
    """
    A maximal run of -/+ lines within a hunk.

    No context lines between them.
    """

    old_line: int  # 1-based line of first '-' in old file (0 if insertion)
    old_lines: list[str]  # content of '-' lines, stripped of prefix
    new_lines: list[str]  # content of '+' lines, stripped of prefix


@dataclass
class UpdateHunk:
    """A single @@old/@@new/@@end block from an updates file."""

    old_line: int  # line-number hint from @@old header
    old_lines: list[str]  # expected old content (empty for pure insertion)
    new_lines: list[str]  # replacement content (empty for pure deletion)


# ---------------------------------------------------------------------------
# Pure functions — parsing
# ---------------------------------------------------------------------------


def parse_unified_diff(diff_text: str) -> list[Hunk]:
    """
    Parse the output of `git diff <file>` into a list of Hunk objects.

    Skips the file header lines (diff --git, index, ---, +++) and
    processes each @@ hunk header along with the lines that follow it.
    """
    hunks: list[Hunk] = []
    lines = diff_text.splitlines(keepends=True)

    # Pattern to match hunk header:
    # @@ -old_start,old_count +new_start,new_count @@ optional_text
    hunk_pattern = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip file header lines
        if line.startswith(("diff --git", "index ", "--- ", "+++ ")):
            i += 1
            continue

        # Check for hunk header
        match = hunk_pattern.match(line)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1

            hunk_lines: list[str] = []
            i += 1

            # Collect lines until next hunk header or end
            while i < len(lines):
                next_line = lines[i]
                # Stop at next hunk header
                if hunk_pattern.match(next_line):
                    break
                # Stop at file header (shouldn't happen mid-hunk, but be safe)
                if next_line.startswith(("diff --git", "--- ", "+++ ")):
                    break
                # Only include diff lines (start with ' ', '-', '+')
                # Also handle '\ No newline at end of file'
                if next_line.startswith((" ", "-", "+", "\\")):
                    hunk_lines.append(next_line)
                i += 1

            hunks.append(Hunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=hunk_lines,
            ))
        else:
            i += 1

    return hunks


def split_into_change_groups(hunk: Hunk) -> list[ChangeGroup]:
    """
    Split a Hunk into maximal runs of -/+ lines uninterrupted by context.

    A context line (prefix ' ') ends the current group. A new group starts
    when the next -/+ line is encountered. Each group tracks the 1-based
    line number of its first '-' line in the old file.
    """
    groups: list[ChangeGroup] = []
    old_lines: list[str] = []
    new_lines: list[str] = []
    old_line = 0  # 1-based line of first '-' in old file (0 if insertion)
    current_old_line = hunk.old_start  # track position in old file

    for line in hunk.lines:
        if line.startswith(" "):
            # Context line: finalize current group if any
            if old_lines or new_lines:
                groups.append(ChangeGroup(
                    old_line=old_line,
                    old_lines=old_lines,
                    new_lines=new_lines,
                ))
                old_lines = []
                new_lines = []
                old_line = 0
            current_old_line += 1
        elif line.startswith("-"):
            # Old line: start tracking if first '-' in group
            if not old_lines and not new_lines:
                old_line = current_old_line
            old_lines.append(line[1:])  # strip prefix
            current_old_line += 1
        elif line.startswith("+"):
            # New line: part of current group
            new_lines.append(line[1:])  # strip prefix
        # Ignore other lines (e.g., "\ No newline at end of file")

    # Finalize any remaining group
    if old_lines or new_lines:
        groups.append(ChangeGroup(
            old_line=old_line,
            old_lines=old_lines,
            new_lines=new_lines,
        ))

    return groups


def parse_updates_file(content: str) -> tuple[str, list[UpdateHunk]]:
    """
    Parse an updates file into a (file_path, hunks) pair.

    Format:
        file: <path>

        @@old <line>
        <old lines...>
        @@new
        <new lines...>
        @@end

    Returns the file path and an ordered list of UpdateHunk objects.
    Empty old-lines section means pure insertion; empty new-lines means
    deletion.
    """
    lines = content.splitlines(keepends=True)
    hunks: list[UpdateHunk] = []
    file_path = ""

    # Pattern to match file header
    file_pattern = re.compile(r"^file:\s*(.+)$")

    # Pattern to match @@old <line>
    old_pattern = re.compile(r"^@@old\s+(\d+)$")

    i = 0
    # Parse file header
    while i < len(lines):
        line = lines[i].rstrip("\n")
        match = file_pattern.match(line)
        if match:
            file_path = match.group(1).strip()
            i += 1
            break
        i += 1

    # Parse hunks
    while i < len(lines):
        line = lines[i].rstrip("\n")

        # Check for @@old <line>
        match = old_pattern.match(line)
        if match:
            old_line = int(match.group(1))
            old_lines: list[str] = []
            new_lines: list[str] = []
            i += 1

            # Collect old lines until @@new
            while i < len(lines):
                current = lines[i].rstrip("\n")
                if current == "@@new":
                    i += 1
                    break
                old_lines.append(lines[i])
                i += 1

            # Collect new lines until @@end
            while i < len(lines):
                current = lines[i].rstrip("\n")
                if current == "@@end":
                    i += 1
                    break
                new_lines.append(lines[i])
                i += 1

            hunks.append(UpdateHunk(
                old_line=old_line,
                old_lines=old_lines,
                new_lines=new_lines,
            ))
        else:
            i += 1

    return (file_path, hunks)


# ---------------------------------------------------------------------------
# Pure functions — transformation
# ---------------------------------------------------------------------------


def format_updates_file(file_path: str, groups: list[ChangeGroup]) -> str:
    """
    Render a list of ChangeGroups into the updates file text format.

    Returns the full text, including the 'file:' header and all
    @@old/@@new/@@end blocks. If groups is empty, returns just the header.
    """
    parts: list[str] = [f"file: {file_path}\n"]

    for group in groups:
        parts.append(f"\n@@old {group.old_line}\n")
        parts.extend(group.old_lines)
        parts.append("@@new\n")
        parts.extend(group.new_lines)
        parts.append("@@end\n")

    return "".join(parts)


def validate_hunks(hunks: list[UpdateHunk]) -> None:
    """
    Raise ValueError if any pair of hunks overlap.

    Two hunks overlap when the old-line range of one intersects the
    old-line range of another (taking the length of old_lines into
    account). Called before any modification so the index is never
    partially updated.
    """
    for i, hunk_a in enumerate(hunks):
        for hunk_b in hunks[i + 1:]:
            # Calculate the range occupied by each hunk
            # For a hunk starting at old_line with n old_lines, it
            # occupies lines old_line through old_line + n - 1 (inclusive)
            start_a = hunk_a.old_line
            if hunk_a.old_lines:
                end_a = hunk_a.old_line + len(hunk_a.old_lines) - 1
            else:
                end_a = hunk_a.old_line - 1
            start_b = hunk_b.old_line
            if hunk_b.old_lines:
                end_b = hunk_b.old_line + len(hunk_b.old_lines) - 1
            else:
                end_b = hunk_b.old_line - 1

            # Check for overlap: ranges overlap if start_a <= end_b and
            # start_b <= end_a. For pure insertions (empty old_lines),
            # end will be old_line - 1, which means they don't occupy any
            # lines and won't overlap with modifications
            if start_a <= end_b and start_b <= end_a:
                raise ValueError(
                    f"Hunks overlap: hunk at line {hunk_a.old_line} "
                    f"and hunk at line {hunk_b.old_line}"
                )


def sort_hunks(hunks: list[UpdateHunk]) -> list[UpdateHunk]:
    """Return hunks sorted in ascending order of old_line."""
    return sorted(hunks, key=lambda h: h.old_line)


def apply_hunks(lines: list[str], hunks: list[UpdateHunk]) -> list[str]:
    """
    Apply a sorted, validated list of UpdateHunks to content lines.

    Processes hunks in order with a cumulative offset:
    - Locate old_lines near (hunk.old_line + offset); raise ValueError
      if the content does not match, showing expected vs actual.
    - Replace with new_lines; update offset by len(new_lines) -
      len(old_lines).
    - Pure insertion (empty old_lines): insert new_lines before the
      adjusted line.

    'lines' should NOT end with a trailing newline sentinel — each
    element already contains its own '\\n' (or lacks one for a
    no-newline-at-EOF file).

    Returns the modified list of lines.
    """
    result = list(lines)  # Make a copy to avoid mutating input
    offset = 0  # Cumulative line offset from previous hunks

    for hunk in hunks:
        adjusted_line = hunk.old_line + offset

        if hunk.old_lines:
            # Replacement or deletion
            # Convert to 0-based index
            start_idx = adjusted_line - 1

            # Verify that old_lines match
            actual_lines = result[start_idx:start_idx + len(hunk.old_lines)]
            if actual_lines != hunk.old_lines:
                raise ValueError(
                    f"old lines not found at line {adjusted_line}: "
                    f"expected {hunk.old_lines!r}, found {actual_lines!r}"
                )

            # Replace old lines with new lines
            result[start_idx:start_idx + len(hunk.old_lines)] = hunk.new_lines

            # Update offset: +difference in line count
            offset += len(hunk.new_lines) - len(hunk.old_lines)
        else:
            # Pure insertion: insert before the adjusted line
            insert_idx = adjusted_line - 1
            result[insert_idx:insert_idx] = hunk.new_lines

            # Update offset: +number of inserted lines
            offset += len(hunk.new_lines)

    return result


def generate_patch(
    file_path: str, old_lines: list[str], new_lines: list[str]
) -> str:
    """
    Generate a git-compatible unified diff patch string.

    Uses `git diff --no-index` with temp files to generate a proper
    patch, then replaces the temp paths with the actual file path.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Write old and new content to temp files
        old_file = tmp_path / "old" / file_path
        old_file.parent.mkdir(parents=True)
        old_file.write_text("".join(old_lines))

        new_file = tmp_path / "new" / file_path
        new_file.parent.mkdir(parents=True)
        new_file.write_text("".join(new_lines))

        # Generate diff using git
        result = subprocess.run(
            ["git", "diff", "--no-index", str(old_file), str(new_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        # Replace temp paths with actual file paths in the output
        patch = result.stdout
        patch = patch.replace(str(old_file), f"/{file_path}")
        patch = patch.replace(str(new_file), f"/{file_path}")

        return patch


# ---------------------------------------------------------------------------
# I/O boundary functions — side-effectful
# ---------------------------------------------------------------------------


def run_git_diff(file_path: str) -> str:
    """
    Run `git diff <file>` and return stdout as a string.

    Returns an empty string if there are no unstaged changes.
    """
    result = subprocess.run(
        ["git", "diff", file_path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def run_git_show_index(file_path: str) -> str:
    """
    Run `git show :<path>` and return the file content from the index.

    Returns the content as a string. Raises RuntimeError on failure.
    """
    result = subprocess.run(
        ["git", "show", f":{file_path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show :{file_path} failed: {result.stderr}")
    return result.stdout


def run_git_apply_cached(patch: str) -> tuple[bool, str]:
    """Pipe patch text to `git apply --cached` and return (success, stderr)."""
    result = subprocess.run(
        ["git", "apply", "--cached"],
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    success = result.returncode == 0
    return (success, result.stderr)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_updates(file_path: str) -> None:
    """
    Handle the --updates command.

    1. Run git diff on the file.
    2. Parse the unified diff into hunks.
    3. Split each hunk into change groups.
    4. Format and print the updates file to stdout.
    """

    # TODO: Detect deleted files and exit with a descriptive error.
    # TODO: Detect renamed/moved files and exit with a descriptive error.
    # TODO: Detect binary diffs and exit with a descriptive error.

    diff_text = run_git_diff(file_path)
    hunks = parse_unified_diff(diff_text)

    # Collect all change groups from all hunks
    all_groups: list[ChangeGroup] = []
    for hunk in hunks:
        groups = split_into_change_groups(hunk)
        all_groups.extend(groups)

    # Format and print the updates file
    output = format_updates_file(file_path, all_groups)
    print(output, end="")


def cmd_apply(updates_file: str) -> None:
    """
    Handle the --apply command.

    1. Read and parse the updates file.
    2. If no hunks, delete the file and exit 0.
    3. Sort and validate hunks.
    4. Read old content from the index (git show :<path>).
    5. Apply hunks to produce new content.
    6. Generate a unified diff patch.
    7. Pipe to git apply --cached.
    8. On success: delete the updates file, exit 0.
    9. On failure: keep the updates file, print error, exit 1.
    """

    # 1. Read and parse the updates file
    updates_path = Path(updates_file)
    content = updates_path.read_text(encoding="utf-8")
    file_path, hunks = parse_updates_file(content)

    # 2. If no hunks, delete the file and exit 0
    if not hunks:
        updates_path.unlink()
        return

    # 3. Sort and validate hunks
    sorted_hunks = sort_hunks(hunks)
    try:
        validate_hunks(sorted_hunks)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 4. Read old content from the index
    try:
        old_content = run_git_show_index(file_path)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Split into lines (preserving newlines)
    old_lines = old_content.splitlines(keepends=True)

    # 5. Apply hunks to produce new content
    try:
        new_lines = apply_hunks(old_lines, sorted_hunks)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 6. Generate a unified diff patch
    patch = generate_patch(file_path, old_lines, new_lines)

    # 7. Pipe to git apply --cached
    success, stderr = run_git_apply_cached(patch)

    # 8. On success: delete the updates file, exit 0
    if success:
        updates_path.unlink()
        return

    # 9. On failure: keep the updates file, print error, exit 1
    print(stderr, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
    sys.exit(0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# pylint: disable=import-error,wrong-import-position
import pytest


# -- helpers -----------------------------------------------------------------


def make_git_repo(tmp_path: Path) -> Path:
    """Initialise a git repo in tmp_path and return its path."""
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


def write_and_commit(repo: Path, rel_path: str, content: str) -> None:
    """Write content to rel_path inside repo and create an initial commit."""
    file_path = repo / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    subprocess.run(
        ["git", "add", rel_path],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        capture_output=True,
        check=True,
    )


def unstaged_edit(repo: Path, rel_path: str, content: str) -> None:
    """Overwrite rel_path with new content without staging."""
    file_path = repo / rel_path
    file_path.write_text(content)


# -- parse_unified_diff ------------------------------------------------------


def test_parse_unified_diff_basic():
    """Single hunk is parsed into one Hunk with correct metadata and lines."""
    diff_text = textwrap.dedent("""\
        diff --git a/example.py b/example.py
        index 1234567..abcdefg 100644
        --- a/example.py
        +++ b/example.py
        @@ -10,6 +10,7 @@ def hello():
         context line 1
         context line 2
        -old line 1
        -old line 2
        +new line 1
        +new line 2
        +new line 3
         context line 3
    """)
    hunks = parse_unified_diff(diff_text)
    assert len(hunks) == 1
    hunk = hunks[0]
    assert hunk.old_start == 10
    assert hunk.old_count == 6
    assert hunk.new_start == 10
    assert hunk.new_count == 7
    assert hunk.lines == [
        " context line 1\n",
        " context line 2\n",
        "-old line 1\n",
        "-old line 2\n",
        "+new line 1\n",
        "+new line 2\n",
        "+new line 3\n",
        " context line 3\n",
    ]


def test_parse_unified_diff_multiple_hunks():
    """Multiple @@ sections produce multiple Hunk objects."""
    diff_text = textwrap.dedent("""\
        diff --git a/example.py b/example.py
        index 1234567..abcdefg 100644
        --- a/example.py
        +++ b/example.py
        @@ -5,3 +5,4 @@ def first():
         line a
        -line b
        +line b modified
        +line c
        @@ -20,2 +21,3 @@ def second():
         line x
        +line y
         line z
    """)
    hunks = parse_unified_diff(diff_text)
    assert len(hunks) == 2

    hunk1 = hunks[0]
    assert hunk1.old_start == 5
    assert hunk1.old_count == 3
    assert hunk1.new_start == 5
    assert hunk1.new_count == 4
    assert hunk1.lines == [
        " line a\n",
        "-line b\n",
        "+line b modified\n",
        "+line c\n",
    ]

    hunk2 = hunks[1]
    assert hunk2.old_start == 20
    assert hunk2.old_count == 2
    assert hunk2.new_start == 21
    assert hunk2.new_count == 3
    assert hunk2.lines == [
        " line x\n",
        "+line y\n",
        " line z\n",
    ]


# -- split_into_change_groups ------------------------------------------------


def test_split_single_group():
    """A hunk with no context between changes yields one ChangeGroup."""
    hunk = Hunk(
        old_start=10,
        old_count=6,
        new_start=10,
        new_count=7,
        lines=[
            " context line 1\n",
            " context line 2\n",
            "-old line 1\n",
            "-old line 2\n",
            "+new line 1\n",
            "+new line 2\n",
            "+new line 3\n",
            " context line 3\n",
        ],
    )
    groups = split_into_change_groups(hunk)
    assert len(groups) == 1
    group = groups[0]
    # old_line is the 1-based line number of first '-' in old file
    # Lines 1-2 are context, so first '-' is at line 10+2 = 12
    assert group.old_line == 12
    assert group.old_lines == ["old line 1\n", "old line 2\n"]
    assert group.new_lines == [
        "new line 1\n", "new line 2\n", "new line 3\n"
    ]


def test_split_multiple_groups_from_one_hunk():
    """Context lines separating changes produce multiple ChangeGroups."""
    # Hunk with two groups separated by a context line:
    # @@ -10,8 +10,9 @@
    #  context 1       (old line 10, new line 10)
    # -old a           (old line 11)
    # +new a           (new line 11)
    #  context 2       (old line 12, new line 12)
    #                  <- separates groups
    # -old b           (old line 13)
    # +new b           (new line 13)
    # +new c           (new line 14)
    #  context 3       (old line 14, new line 15)
    hunk = Hunk(
        old_start=10,
        old_count=8,
        new_start=10,
        new_count=9,
        lines=[
            " context 1\n",
            "-old a\n",
            "+new a\n",
            " context 2\n",
            "-old b\n",
            "+new b\n",
            "+new c\n",
            " context 3\n",
        ],
    )
    groups = split_into_change_groups(hunk)
    assert len(groups) == 2

    # First group: starts at old line 11 (10 + 1 context line)
    group1 = groups[0]
    assert group1.old_line == 11
    assert group1.old_lines == ["old a\n"]
    assert group1.new_lines == ["new a\n"]

    # Second group: starts at old line 13
    # (10 + 1 context + 1 old + 1 new + 1 context = 5 lines consumed,
    # but in old file: 10 + 1 ctx + 1 old + 1 ctx = line 13)
    group2 = groups[1]
    assert group2.old_line == 13
    assert group2.old_lines == ["old b\n"]
    assert group2.new_lines == ["new b\n", "new c\n"]


# -- parse_updates_file ------------------------------------------------------


def test_parse_updates_file_basic():
    """Full updates file is parsed into the correct file path and hunks."""
    content = textwrap.dedent("""\
        file: src/auth.py

        @@old 43
        old line 1
        old line 2
        @@new
        new line 1
        new line 2
        new line 3
        @@end

        @@old 88
        deleted line
        @@new
        @@end
    """)
    file_path, hunks = parse_updates_file(content)
    assert file_path == "src/auth.py"
    assert len(hunks) == 2

    hunk1 = hunks[0]
    assert hunk1.old_line == 43
    assert hunk1.old_lines == ["old line 1\n", "old line 2\n"]
    assert hunk1.new_lines == ["new line 1\n", "new line 2\n", "new line 3\n"]

    hunk2 = hunks[1]
    assert hunk2.old_line == 88
    assert hunk2.old_lines == ["deleted line\n"]
    assert hunk2.new_lines == []


def test_parse_updates_file_deletion():
    """Empty @@new section is parsed as a deletion hunk."""
    content = textwrap.dedent("""\
        file: example.py

        @@old 10
        line to delete
        another line
        @@new
        @@end
    """)
    file_path, hunks = parse_updates_file(content)
    assert file_path == "example.py"
    assert len(hunks) == 1
    hunk = hunks[0]
    assert hunk.old_line == 10
    assert hunk.old_lines == ["line to delete\n", "another line\n"]
    assert hunk.new_lines == []


def test_parse_updates_file_insertion():
    """Empty @@old section is parsed as an insertion hunk."""
    content = textwrap.dedent("""\
        file: example.py

        @@old 5
        @@new
        inserted line 1
        inserted line 2
        @@end
    """)
    file_path, hunks = parse_updates_file(content)
    assert file_path == "example.py"
    assert len(hunks) == 1
    hunk = hunks[0]
    assert hunk.old_line == 5
    assert hunk.old_lines == []
    assert hunk.new_lines == [
        "inserted line 1\n", "inserted line 2\n"
    ]


def test_parse_updates_file_no_hunks():
    """Updates file with only the header and no @@old blocks yields empty."""
    content = textwrap.dedent("""\
        file: unchanged.py

    """)
    file_path, hunks = parse_updates_file(content)
    assert file_path == "unchanged.py"
    assert not hunks


# -- format_updates_file -----------------------------------------------------


def test_format_updates_file_roundtrip():
    """format then parse returns the same groups."""
    groups = [
        ChangeGroup(
            old_line=43,
            old_lines=["old line 1\n", "old line 2\n"],
            new_lines=[
                "new line 1\n", "new line 2\n", "new line 3\n"
            ],
        ),
        ChangeGroup(
            old_line=88,
            old_lines=["deleted line\n"],
            new_lines=[],  # deletion
        ),
        ChangeGroup(
            old_line=100,
            old_lines=[],  # insertion
            new_lines=["inserted line 1\n", "inserted line 2\n"],
        ),
    ]
    file_path = "src/auth.py"
    formatted = format_updates_file(file_path, groups)
    parsed_path, parsed_hunks = parse_updates_file(formatted)

    assert parsed_path == file_path
    assert len(parsed_hunks) == 3

    # Check first hunk (replacement)
    assert parsed_hunks[0].old_line == 43
    assert parsed_hunks[0].old_lines == [
        "old line 1\n", "old line 2\n"
    ]
    assert parsed_hunks[0].new_lines == [
        "new line 1\n", "new line 2\n", "new line 3\n"
    ]

    # Check second hunk (deletion)
    assert parsed_hunks[1].old_line == 88
    assert parsed_hunks[1].old_lines == ["deleted line\n"]
    assert parsed_hunks[1].new_lines == []

    # Check third hunk (insertion)
    assert parsed_hunks[2].old_line == 100
    assert parsed_hunks[2].old_lines == []
    assert parsed_hunks[2].new_lines == [
        "inserted line 1\n", "inserted line 2\n"
    ]


# -- validate_hunks ----------------------------------------------------------


def test_validate_hunks_no_overlap():
    """Non-overlapping hunks pass validation without error."""
    # Hunk 1: lines 10-11 (2 old lines)
    # Hunk 2: lines 20-22 (3 old lines)
    # Hunk 3: insertion at line 30 (no old lines, doesn't occupy range)
    # Hunk 4: lines 40-40 (1 old line)
    hunks = [
        UpdateHunk(
            old_line=10,
            old_lines=["line 10\n", "line 11\n"],
            new_lines=["new\n"],
        ),
        UpdateHunk(
            old_line=20,
            old_lines=["a\n", "b\n", "c\n"],
            new_lines=["x\n"],
        ),
        UpdateHunk(
            old_line=30, old_lines=[], new_lines=["inserted\n"]
        ),
        UpdateHunk(
            old_line=40, old_lines=["line 40\n"], new_lines=["new 40\n"]
        ),
    ]
    # Should not raise
    validate_hunks(hunks)


def test_validate_hunks_overlap_raises():
    """Overlapping hunks raise ValueError before any changes are applied."""
    # Hunk 1: lines 10-14 (5 old lines)
    # Hunk 2: lines 13-15 (3 old lines) - overlaps with hunk 1
    hunks = [
        UpdateHunk(
            old_line=10,
            old_lines=["a\n", "b\n", "c\n", "d\n", "e\n"],
            new_lines=["x\n"],
        ),
        UpdateHunk(
            old_line=13,
            old_lines=["c\n", "d\n", "f\n"],
            new_lines=["y\n"],
        ),
    ]
    with pytest.raises(ValueError, match="overlap"):
        validate_hunks(hunks)


# -- sort_hunks --------------------------------------------------------------


def test_sort_hunks():
    """Hunks are returned in ascending old_line order."""
    hunks = [
        UpdateHunk(
            old_line=88, old_lines=["line d\n"], new_lines=[]
        ),
        UpdateHunk(
            old_line=10, old_lines=["line a\n"], new_lines=["new a\n"]
        ),
        UpdateHunk(
            old_line=43,
            old_lines=["line b\n", "line c\n"],
            new_lines=["new b\n"],
        ),
        UpdateHunk(
            old_line=5, old_lines=[], new_lines=["inserted\n"]
        ),
    ]
    sorted_hunks = sort_hunks(hunks)
    assert [h.old_line for h in sorted_hunks] == [5, 10, 43, 88]
    # Verify the hunks themselves are correct (not just old_line values)
    assert sorted_hunks[0].old_lines == []
    assert sorted_hunks[0].new_lines == ["inserted\n"]
    assert sorted_hunks[1].old_lines == ["line a\n"]
    assert sorted_hunks[2].old_lines == ["line b\n", "line c\n"]
    assert sorted_hunks[3].old_lines == ["line d\n"]


# -- apply_hunks -------------------------------------------------------------


def test_apply_hunks_replace():
    """Replacement hunk substitutes the correct lines."""
    # Original content: lines 1-5
    lines = [
        "line 1\n",
        "line 2\n",
        "line 3\n",
        "line 4\n",
        "line 5\n",
    ]
    # Replace lines 2-3 with new content
    hunks = [
        UpdateHunk(
            old_line=2,
            old_lines=["line 2\n", "line 3\n"],
            new_lines=["new line 2\n", "new line 3\n", "new line 3b\n"],
        ),
    ]
    result = apply_hunks(lines, hunks)
    assert result == [
        "line 1\n",
        "new line 2\n",
        "new line 3\n",
        "new line 3b\n",
        "line 4\n",
        "line 5\n",
    ]


def test_apply_hunks_deletion():
    """Empty new_lines deletes the old lines."""
    # Original content: lines 1-5
    lines = [
        "line 1\n",
        "line 2\n",
        "line 3\n",
        "line 4\n",
        "line 5\n",
    ]
    # Delete lines 2-3
    hunks = [
        UpdateHunk(
            old_line=2,
            old_lines=["line 2\n", "line 3\n"],
            new_lines=[],
        ),
    ]
    result = apply_hunks(lines, hunks)
    assert result == [
        "line 1\n",
        "line 4\n",
        "line 5\n",
    ]


def test_apply_hunks_insertion():
    """Empty old_lines inserts new lines at the given position."""
    # Original content: lines 1-3
    lines = [
        "line 1\n",
        "line 2\n",
        "line 3\n",
    ]
    # Insert before line 2 (between line 1 and line 2)
    hunks = [
        UpdateHunk(
            old_line=2,
            old_lines=[],
            new_lines=["inserted 1\n", "inserted 2\n"],
        ),
    ]
    result = apply_hunks(lines, hunks)
    assert result == [
        "line 1\n",
        "inserted 1\n",
        "inserted 2\n",
        "line 2\n",
        "line 3\n",
    ]


def test_apply_hunks_old_lines_not_found():
    """Mismatched old lines raise ValueError with descriptive message."""
    # Original content
    lines = [
        "line 1\n",
        "line 2\n",
        "line 3\n",
    ]
    # Try to replace with wrong old_lines
    hunks = [
        UpdateHunk(
            old_line=2,
            old_lines=["wrong line\n"],
            new_lines=["new line\n"],
        ),
    ]
    with pytest.raises(ValueError, match="old lines not found"):
        apply_hunks(lines, hunks)


def test_apply_hunks_out_of_order():
    """Hunks provided out of order are handled correctly after sorting."""
    # Original content: lines 1-5
    lines = [
        "line 1\n",
        "line 2\n",
        "line 3\n",
        "line 4\n",
        "line 5\n",
    ]
    # Two hunks in reverse order
    hunks = [
        UpdateHunk(
            old_line=4,
            old_lines=["line 4\n"],
            new_lines=["new line 4\n"],
        ),
        UpdateHunk(
            old_line=2,
            old_lines=["line 2\n"],
            new_lines=["new line 2\n"],
        ),
    ]
    # Sort the hunks first (as apply_hunks expects sorted input)
    sorted_hunks = sort_hunks(hunks)
    result = apply_hunks(lines, sorted_hunks)
    assert result == [
        "line 1\n",
        "new line 2\n",
        "line 3\n",
        "new line 4\n",
        "line 5\n",
    ]


# -- generate_patch ----------------------------------------------------------


def test_generate_patch_format():
    """Patch starts with the git diff header and is accepted by git apply."""
    old_lines = ["line 1\n", "line 2\n", "line 3\n"]
    new_lines = ["line 1\n", "line 2 modified\n", "line 3\n"]

    patch = generate_patch("example.py", old_lines, new_lines)

    # Must start with the git diff header
    assert patch.startswith("diff --git a/example.py b/example.py\n")
    # Must contain unified diff headers
    assert "--- a/example.py\n" in patch
    assert "+++ b/example.py\n" in patch
    # Must contain a hunk header
    assert "@@" in patch
    # Must show the change
    assert "-line 2\n" in patch
    assert "+line 2 modified\n" in patch


def test_generate_patch_no_newline_at_eof():
    """File lacking trailing newline produces correct \\ No newline marker."""
    # Old file has no trailing newline on last line
    old_lines = ["line 1\n", "line 2\n", "line 3"]  # no \n on last
    # New file also has no trailing newline
    new_lines = ["line 1\n", "line 2\n", "line 3 modified"]  # no \n

    patch = generate_patch("example.py", old_lines, new_lines)

    # The patch should include the "\ No newline at end of file" marker
    # for both the old and new file versions
    assert patch.count("\\ No newline at end of file") == 2


# -- cmd_updates (integration) -----------------------------------------------


def test_cmd_updates_produces_correct_blocks(
    tmp_path, monkeypatch, capsys
):
    """--updates produces @@old/@@new/@@end blocks matching the diff."""
    repo = make_git_repo(tmp_path)
    # Create initial file with 3 lines
    write_and_commit(repo, "example.py", "line 1\nline 2\nline 3\n")
    # Make an unstaged edit: replace line 2 with two new lines
    unstaged_edit(
        repo, "example.py", "line 1\nnew line 2a\nnew line 2b\nline 3\n"
    )

    # Change working directory to the repo for git commands
    monkeypatch.chdir(repo)

    cmd_updates("example.py")

    captured = capsys.readouterr()
    output = captured.out

    # Should start with file header
    assert output.startswith("file: example.py\n")
    # Should contain the change block
    assert "@@old 2\n" in output
    assert "line 2\n" in output
    assert "@@new\n" in output
    assert "new line 2a\n" in output
    assert "new line 2b\n" in output
    assert "@@end\n" in output


def test_cmd_updates_no_changes_header_only(tmp_path, monkeypatch, capsys):
    """--updates with no unstaged changes outputs only the file: header."""
    repo = make_git_repo(tmp_path)
    # Create initial file
    write_and_commit(repo, "unchanged.py", "line 1\nline 2\nline 3\n")
    # No unstaged edits

    # Change working directory to the repo for git commands
    monkeypatch.chdir(repo)

    cmd_updates("unchanged.py")

    captured = capsys.readouterr()
    output = captured.out

    # Should only contain the file header
    assert output == "file: unchanged.py\n"


# -- cmd_apply (integration) -------------------------------------------------


def test_cmd_apply_full(tmp_path, monkeypatch):
    """--apply on a full updates file stages all changes correctly."""
    repo = make_git_repo(tmp_path)
    # Create initial file with 3 lines
    write_and_commit(repo, "example.py", "line 1\nline 2\nline 3\n")
    # Make an unstaged edit: replace line 2 with two new lines
    unstaged_edit(
        repo, "example.py", "line 1\nnew line 2a\nnew line 2b\nline 3\n"
    )

    monkeypatch.chdir(repo)

    # Create an updates file with the full change
    updates_file = repo / "example.py.updates"
    updates_content = textwrap.dedent("""\
        file: example.py

        @@old 2
        line 2
        @@new
        new line 2a
        new line 2b
        @@end
    """)
    updates_file.write_text(updates_content)

    # Apply the updates
    cmd_apply(str(updates_file))

    # Updates file should be deleted on success
    assert not updates_file.exists()

    # Verify the change is staged (git diff --cached should show it)
    result = subprocess.run(
        ["git", "diff", "--cached", "example.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    staged_diff = result.stdout
    assert "-line 2" in staged_diff
    assert "+new line 2a" in staged_diff
    assert "+new line 2b" in staged_diff

    # Working tree should still have the modified content
    working_content = (repo / "example.py").read_text()
    assert working_content == "line 1\nnew line 2a\nnew line 2b\nline 3\n"


def test_cmd_apply_partial(tmp_path, monkeypatch):
    """Removing a hunk from the updates file stages only the kept changes."""
    repo = make_git_repo(tmp_path)
    # Create initial file with multiple lines
    write_and_commit(
        repo, "example.py", "line 1\nline 2\nline 3\nline 4\nline 5\n"
    )
    # Make unstaged edits: change line 2 and line 4
    unstaged_edit(
        repo, "example.py", "line 1\nnew line 2\nline 3\nnew line 4\nline 5\n"
    )

    monkeypatch.chdir(repo)

    # Create an updates file with only the first change (line 2),
    # removing the line 4 change
    updates_file = repo / "example.py.updates"
    updates_content = textwrap.dedent("""\
        file: example.py

        @@old 2
        line 2
        @@new
        new line 2
        @@end
    """)
    updates_file.write_text(updates_content)

    # Apply the partial updates
    cmd_apply(str(updates_file))

    # Updates file should be deleted
    assert not updates_file.exists()

    # Verify only line 2 change is staged
    result = subprocess.run(
        ["git", "diff", "--cached", "example.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    staged_diff = result.stdout
    assert "-line 2" in staged_diff
    assert "+new line 2" in staged_diff
    # line 4 change should NOT be staged
    assert "-line 4" not in staged_diff
    assert "+new line 4" not in staged_diff


def test_cmd_apply_no_hunks_noop(tmp_path, monkeypatch):
    """--apply with no hunks is a no-op; updates file is deleted."""
    repo = make_git_repo(tmp_path)
    # Create initial file
    write_and_commit(repo, "example.py", "line 1\nline 2\nline 3\n")
    # No unstaged changes

    monkeypatch.chdir(repo)

    # Create an updates file with only the header (no hunks)
    updates_file = repo / "example.py.updates"
    updates_content = "file: example.py\n"
    updates_file.write_text(updates_content)

    # Apply should be a no-op
    cmd_apply(str(updates_file))

    # Updates file should still be deleted
    assert not updates_file.exists()

    # Nothing should be staged
    result = subprocess.run(
        ["git", "diff", "--cached", "example.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout == ""


def test_cmd_apply_old_lines_not_found_keeps_file(
    tmp_path, monkeypatch, capsys
):
    """--apply with bad old-lines prints an error and keeps the updates file."""
    repo = make_git_repo(tmp_path)
    # Create initial file
    write_and_commit(repo, "example.py", "line 1\nline 2\nline 3\n")
    # No unstaged changes - so old content is "line 1\nline 2\nline 3\n"

    monkeypatch.chdir(repo)

    # Create an updates file with wrong old_lines
    updates_file = repo / "example.py.updates"
    updates_content = textwrap.dedent("""\
        file: example.py

        @@old 2
        wrong old content
        @@new
        new content
        @@end
    """)
    updates_file.write_text(updates_content)

    # Apply should fail
    with pytest.raises(SystemExit) as exc_info:
        cmd_apply(str(updates_file))

    # Should exit with code 1
    assert exc_info.value.code == 1

    # Updates file should be kept
    assert updates_file.exists()

    # Should have printed an error message
    captured = capsys.readouterr()
    assert (
        "old lines not found" in captured.err
        or "old lines not found" in captured.out
    )


def test_cmd_apply_overlapping_hunks_aborts(
    tmp_path, monkeypatch, capsys
):
    """Overlapping hunks abort before touching the index."""
    repo = make_git_repo(tmp_path)
    # Create initial file
    write_and_commit(
        repo, "example.py", "line 1\nline 2\nline 3\nline 4\nline 5\n"
    )

    monkeypatch.chdir(repo)

    # Create an updates file with overlapping hunks
    updates_file = repo / "example.py.updates"
    updates_content = textwrap.dedent("""\
        file: example.py

        @@old 2
        line 2
        line 3
        @@new
        new line 2
        @@end

        @@old 3
        line 3
        line 4
        @@new
        new line 3
        @@end
    """)
    updates_file.write_text(updates_content)

    # Apply should fail
    with pytest.raises(SystemExit) as exc_info:
        cmd_apply(str(updates_file))

    # Should exit with code 1
    assert exc_info.value.code == 1

    # Updates file should be kept
    assert updates_file.exists()

    # Should have printed an error message about overlap
    captured = capsys.readouterr()
    assert "overlap" in captured.err or "overlap" in captured.out

    # Nothing should be staged
    result = subprocess.run(
        ["git", "diff", "--cached", "example.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout == ""


def test_cmd_apply_no_newline_at_eof(tmp_path, monkeypatch):
    """--apply preserves the no-newline-at-EOF property correctly."""
    repo = make_git_repo(tmp_path)
    # Create initial file WITHOUT trailing newline
    write_and_commit(
        repo, "example.py", "line 1\nline 2\nline 3"
    )  # no trailing newline

    monkeypatch.chdir(repo)

    # Make an unstaged edit (also no trailing newline)
    unstaged_edit(
        repo, "example.py", "line 1\nnew line 2\nline 3"
    )  # no trailing newline

    # Create an updates file
    updates_file = repo / "example.py.updates"
    updates_content = textwrap.dedent("""\
        file: example.py

        @@old 2
        line 2
        @@new
        new line 2
        @@end
    """)
    updates_file.write_text(updates_content)

    # Apply the updates
    cmd_apply(str(updates_file))

    # Updates file should be deleted
    assert not updates_file.exists()

    # Verify the change is staged
    result = subprocess.run(
        ["git", "diff", "--cached", "example.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    staged_diff = result.stdout
    assert "-line 2" in staged_diff
    assert "+new line 2" in staged_diff

    # Verify the working tree file still has no trailing newline
    working_content = (repo / "example.py").read_text()
    assert not working_content.endswith("\n")
    assert working_content == "line 1\nnew line 2\nline 3"


def test_cmd_apply_nested_file(tmp_path, monkeypatch):
    """--apply works correctly with files in nested directories."""
    repo = make_git_repo(tmp_path)
    # Create initial file in a nested directory
    write_and_commit(repo, "src/lib/utils.py", "def foo():\n    pass\n")
    # Make an unstaged edit
    unstaged_edit(repo, "src/lib/utils.py", "def foo():\n    return 42\n")

    monkeypatch.chdir(repo)

    # Create an updates file for the nested file
    updates_file = repo / "src" / "lib" / "utils.py.updates"
    updates_content = textwrap.dedent("""\
        file: src/lib/utils.py

        @@old 2
            pass
        @@new
            return 42
        @@end
    """)
    updates_file.write_text(updates_content)

    # Apply the updates
    cmd_apply(str(updates_file))

    # Updates file should be deleted on success
    assert not updates_file.exists()

    # Verify the change is staged
    result = subprocess.run(
        ["git", "diff", "--cached", "src/lib/utils.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    staged_diff = result.stdout
    assert "-    pass" in staged_diff
    assert "+    return 42" in staged_diff

    # Working tree should have the modified content
    working_content = (repo / "src" / "lib" / "utils.py").read_text()
    assert working_content == "def foo():\n    return 42\n"
