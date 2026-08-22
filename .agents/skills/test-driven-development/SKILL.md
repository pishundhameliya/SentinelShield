---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
---

# Test-Driven Development (TDD) Protocol

## Core Rule
**Write the test first. Watch it fail. Only then write the code.**

## The Three Laws of TDD
1. **Red**: Write a minimal failing test case that expresses the required capability or bug reproduction.
2. **Green**: Write only the simplest implementation required to make the test pass.
3. **Refactor**: Clean up the code, eliminate duplication, and verify that the test suite still passes.

## SentinelShield Specific Guidelines
- Test files live in `sentinelshield/tests/test_<feature>.py`.
- Tests must import from `core.database import db_manager` and initialize schema via `db_manager.init_schema()`.
- Use graceful fallbacks for optional C-dependencies (`cv2`, `numpy`, `fastapi`) so tests run cleanly in any environment.
- Always run `python verify.py` or `python sentinelshield/tests/test_<feature>.py` to verify the red-green cycle.
