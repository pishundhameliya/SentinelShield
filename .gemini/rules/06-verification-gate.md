# Antigravity Rule: Verification Gatekeeper (Evidence Before Assertion)

## The Iron Rule
**NEVER CLAIM ANY TASK, BUG FIX, OR REFACTOR IS COMPLETE WITHOUT RUNNING VERIFICATION.**

## Verification Protocol
1. Execute the universal runner:
   ```bash
   python verify.py
   ```
2. Confirm that all 12 test & benchmark suites pass with exit code `0`.
3. Check git hygiene with `git status --short` to ensure zero leftover scratch files.
4. Report concrete execution metrics (pass count, elapsed time, FPS) to the user.
