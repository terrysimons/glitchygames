---
name: feedback_no_config_changes_for_tests
description: Never modify linter/type checker configs just to make tests pass - fix the actual code instead
type: feedback
---

Do not change configurations of linters, type checkers, or other tools just to get tests to pass.

**Why:** The user wants real fixes, not config workarounds. Suppressing rules globally weakens the tool for all code.

**How to apply:** When a linter/type checker flags test code, fix the code itself (add type annotations, restructure logic, use casts for incorrect stubs, etc.) rather than adding rules to per-file-ignores or pyrightconfig.json.
