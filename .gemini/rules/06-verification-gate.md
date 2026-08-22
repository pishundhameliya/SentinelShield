# Antigravity Rule: Verification Gatekeeper (Evidence Before Assertion)

## The Iron Rule
**NEVER CLAIM ANY TASK, BUG FIX, OR REFACTOR IS COMPLETE WITHOUT RUNNING VERIFICATION.**

## Verification Protocol
1. Execute the universal test and verification runner:
   ```bash
   python verify.py
   ```
2. Confirm that all 13 test & benchmark suites pass with exit code `0`.
3. Validate PyLint score and static analysis:
   ```bash
   python -m pylint sentinelshield/modules/ sentinelshield/core/ sentinelshield/app.py --rcfile=.pylintrc
   ```
4. Check git hygiene with `git status --short` to ensure zero leftover scratch files and confirm the root `README.md` has 0 diffs.
5. Report concrete execution metrics (pass count, elapsed time, FPS) to the user.
