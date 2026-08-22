#!/usr/bin/env python3
"""Universal Verification & Test Runner for SentinelShield.

Discovers and executes all automated unit, integration, and high-density
stress benchmark suites across the modular architecture.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time


def run_verification() -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable

    test_pattern = os.path.join(base_dir, "sentinelshield", "tests", "test_*.py")
    bench_pattern = os.path.join(base_dir, "sentinelshield", "tests", "benchmark_*.py")
    test_files = sorted(glob.glob(test_pattern) + glob.glob(bench_pattern))

    if not test_files:
        print("[ERROR] No test suites discovered in sentinelshield/tests/")
        return 1

    print("================================================================================")
    print("           SENTINELSHIELD (SENTINEL-X GUJARAT) — VERIFICATION SUITE             ")
    print("================================================================================")
    print(f" Python Executable : {python_exe}")
    print(f" Working Directory : {base_dir}")
    print(f" Discovered Suites : {len(test_files)} test & benchmark files\n")
    print(f" {'STATUS':<10} | {'DURATION':<10} | {'TEST SUITE'}")
    print(" " + "-" * 78)

    total_start = time.perf_counter()
    failed_count = 0
    passed_count = 0

    for test_path in test_files:
        rel_name = os.path.relpath(test_path, base_dir)
        t0 = time.perf_counter()
        
        proc = subprocess.run(
            [python_exe, test_path],
            cwd=base_dir,
            capture_output=True,
            text=True,
        )
        elapsed = time.perf_counter() - t0

        if proc.returncode == 0:
            passed_count += 1
            print(f" \033[92m[PASS]\033[0m     | {elapsed:6.3f} s    | {rel_name}")
        else:
            failed_count += 1
            print(f" \033[91m[FAIL]\033[0m     | {elapsed:6.3f} s    | {rel_name}")
            if proc.stdout.strip():
                print("   --- STDOUT ---")
                for line in proc.stdout.strip().splitlines()[-6:]:
                    print(f"   {line}")
            if proc.stderr.strip():
                print("   --- STDERR ---")
                for line in proc.stderr.strip().splitlines()[-6:]:
                    print(f"   {line}")
            print(" " + "-" * 78)

    total_elapsed = time.perf_counter() - total_start
    print(" " + "=" * 78)
    print(f" RESULTS: {passed_count} Passed, {failed_count} Failed in {total_elapsed:.2f} seconds.")

    if failed_count == 0:
        print("\033[92m [ALL PASS] System architecture, scaling, and integrity 100% verified.\033[0m")
        return 0
    else:
        print("\033[91m [FAILURE] One or more test suites failed.\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(run_verification())
