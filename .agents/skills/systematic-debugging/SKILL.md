---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---

# Systematic Debugging

## The Iron Law
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.

## The Four Phases
1. **Phase 1: Root Cause Investigation**
   - Read error messages completely (line numbers, stack traces).
   - Reproduce consistently.
   - Trace data flow backward to root cause source.
   - Inspect trust boundaries.

2. **Phase 2: Pattern Analysis**
   - Find working examples.
   - Identify precise differences between broken and working code.

3. **Phase 3: Hypothesis and Testing**
   - Form single clear hypothesis.
   - Test minimally with smallest possible change.
   - Verify before continuing.

4. **Phase 4: Implementation**
   - Write failing test case first (TDD).
   - Implement single minimal root-cause fix.
   - Verify all tests pass with zero regressions.
