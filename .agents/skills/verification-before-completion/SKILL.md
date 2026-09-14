---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing - requires running verification commands and confirming output before assertions
---

# Verification Before Completion

## The Iron Rule
**EVIDENCE BEFORE ASSERTIONS. NEVER CLAIM A FIX OR TASK IS COMPLETE WITHOUT PROOF.**

## The Verification Checklist
1. **Identify the Verification Command**:
   - Primary suite: `python verify.py`
   - Individual test: `python sentinelshield/tests/test_<name>.py`
   - 200-stream benchmark: `python sentinelshield/tests/benchmark_200_streams.py`
2. **Execute and Inspect Exit Code**:
   - Command must exit with code `0`.
   - Read the full output, checking for hidden warnings, tracebacks, or unhandled exceptions.
3. **Verify Git Cleanliness**:
   - Run `git status --short`.
   - Ensure no leftover scratch files, temporary lock files, or unintended diffs remain.
4. **Report Facts, Not Assumptions**:
   - Provide concrete command output, pass counts, throughput numbers, and latency measurements to the user.
