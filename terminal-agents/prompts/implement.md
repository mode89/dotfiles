# Task: Implement next function in `<TARGET_FILE>`

## Placeholders

- `TARGET_FILE`: `path/to/script.py`
- `SPEC_FILE`: `PLAN.md`
- `LOG_FILE`: `LOG.md`
- `TEST_CMD`: `pytest`

---

## Main agent instructions

1. If a bottom-up function order has not yet been established in this
   conversation, read `<SPEC_FILE>` and `<TARGET_FILE>`, then produce the
   full ordered list (dependencies before dependents).
2. From that list, pick the next function that is not yet implemented.
3. Identify the tests that cover it.
4. Spawn a subagent with the prompt below, substituting the placeholders.
5. When the subagent returns:
   - Report which function and tests were implemented
   - Report any findings or challenges from the subagent
   - Propose the next function to work on
   - Stop

---

## Subagent prompt

Your task is to implement `<function_name>` and its tests.

### Scope

Only touch:
- `<function_name>` function body
- `<test_1>` test body
- `<test_2>` test body
- *(add more tests as needed)*

Do not implement or modify any other functions or tests. Do not leave any
touched tests failing.

### References

All paths are relative to the working directory. Read these files for context:
- `<TARGET_FILE>` — full script with dataclass definitions, docstrings, and
  already-implemented functions for style reference
- `<SPEC_FILE>` — design spec describing algorithms and data formats
- `<LOG_FILE>` — development log (read if present)

### Steps

1. Read the files above
2. Implement the tests (they must initially fail since the function is not yet implemented)
3. Confirm the tests fail by running them
4. Implement `<function_name>`
5. Make sure all of the function's tests pass
6. Run the full test suite and fix any regressions until it is clean
7. Append a brief entry to `<LOG_FILE>` (entries separated by `---`) covering:
   what was implemented, findings, challenges, unexpected outcomes, and any
   divergence from the spec
8. Report back to the main agent

### Constraints

- Use `<TEST_CMD>` to run tests
- Do not implement any other function bodies or test bodies
- If a test cannot pass without another not-yet-implemented function:
  - If that function is a small helper with no tests of its own, implement it
  - Otherwise, mock it or simplify/split the test to avoid the dependency
