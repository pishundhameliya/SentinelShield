"""Automated Code Quality, Lint, AST, and CI/CD Sanity Test Suite for SentinelShield."""
from __future__ import annotations

import ast
import glob
import os
import re
import sys
import unittest
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class TestCodeQualityAndLintSanity(unittest.TestCase):
    """Static analysis and architectural lint checks across the entire codebase."""

    def setUp(self):
        self.py_files = sorted(glob.glob(os.path.join(BASE_DIR, "**", "*.py"), recursive=True))

    def test_ast_compilation_all_python_files(self):
        """Ensure every python file in the project compiles cleanly into an AST without syntax errors."""
        self.assertGreater(len(self.py_files), 10, "Expected at least 10 python files")
        for fpath in self.py_files:
            rel_path = os.path.relpath(fpath, BASE_DIR)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            try:
                tree = ast.parse(content, filename=fpath)
                self.assertIsNotNone(tree)
            except SyntaxError as e:
                self.fail(f"SyntaxError in {rel_path}: {e}")
        print(f"[PASS] AST syntax compilation verified for all {len(self.py_files)} Python files!")

    def test_anti_pattern_no_raw_sql_fstrings(self):
        """Ensure no operational DML queries (SELECT, INSERT, UPDATE, DELETE WHERE) use unparameterized f-strings."""
        dangerous_sql_pattern = re.compile(
            r'(execute|query_rows|query_one)\s*\(\s*f["\']\s*(SELECT|INSERT|UPDATE|DELETE\s+FROM\s+\w+\s+WHERE)',
            re.IGNORECASE
        )
        violating_files = []

        for fpath in self.py_files:
            rel_path = os.path.relpath(fpath, BASE_DIR)
            # Skip test files
            if "tests" in rel_path:
                continue
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    if dangerous_sql_pattern.search(line):
                        violating_files.append(f"{rel_path}:{line_no} -> {line.strip()}")

        self.assertEqual(
            violating_files, [],
            f"Found dangerous unparameterized SQL f-strings (must use '?' placeholders):\n" + "\n".join(violating_files)
        )
        print("[PASS] Anti-Pattern Guard: Zero unparameterized DML queries detected across all modules!")

    def test_domain_isolation_app_is_composer_only(self):
        """Ensure app.py does not contain direct database queries or domain business logic."""
        app_path = os.path.join(BASE_DIR, "app.py")
        if os.path.exists(app_path):
            with open(app_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("db_manager.execute(", content, "app.py should not execute direct SQL mutations")
            self.assertNotIn("db_manager.query_rows(", content, "app.py should not execute direct SQL queries")
        print("[PASS] Domain Isolation: app.py is verified as a top-level composer only!")

    def test_legacy_re_exports_engine_parity(self):
        """Verify backward compatibility: engine.py must re-export legacy symbols."""
        try:
            import engine
            required_symbols = ["detect_vehicles", "normalize_plate", "extract_plate_candidate", "process_video"]
            for sym in required_symbols:
                self.assertTrue(hasattr(engine, sym), f"engine.py missing re-exported legacy symbol '{sym}'")
            print(f"[PASS] Backward Compatibility: engine.py re-exports all required legacy symbols {required_symbols}!")
        except ImportError as e:
            self.skipTest(f"Skipping engine import test if dependency is absent: {e}")

    def test_legacy_re_exports_gujarat_estate_parity(self):
        """Verify backward compatibility: gujarat_estate.py must re-export legacy estate symbols."""
        try:
            import gujarat_estate
            required_symbols = ["CITIES", "DEMO_CAMS", "total_cameras", "sample_points"]
            for sym in required_symbols:
                self.assertTrue(hasattr(gujarat_estate, sym), f"gujarat_estate.py missing legacy symbol '{sym}'")
            print(f"[PASS] Backward Compatibility: gujarat_estate.py re-exports all estate symbols {required_symbols}!")
        except ImportError as e:
            self.skipTest(f"Skipping gujarat_estate import test if dependency is absent: {e}")

    def test_module_imports_clean_and_acyclic(self):
        """Verify that all 12 core domain subsystems import cleanly without circular dependencies."""
        modules_to_test = [
            "core.database",
            "core.state",
            "core.security",
            "modules.integrity.hash_chain",
            "modules.integrity.tamper_detector",
            "modules.integrity.lsb_watermark",
            "modules.evidence.vault",
            "modules.evidence.pdf_builder",
            "modules.streaming.stream_pool",
            "modules.streaming.hw_accel",
            "modules.streaming.mjpeg",
            "modules.vision.service",
            "modules.vision.deblur",
            "modules.tracking.service",
            "modules.tracking.tracker",
            "modules.alerts.service",
            "modules.alerts.webhooks",
            "modules.registry.service",
            "modules.registry.importer",
            "modules.twin.heat",
            "modules.twin.assistant",
            "modules.cyber.honeypot",
        ]
        for mod_name in modules_to_test:
            try:
                mod = __import__(mod_name, fromlist=["*"])
                self.assertIsNotNone(mod, f"Failed to import {mod_name}")
            except Exception as e:
                self.fail(f"Circular dependency or import failure in {mod_name}: {e}")
        print(f"[PASS] Package Sanity: All {len(modules_to_test)} domain subsystems import cleanly & acyclically!")

    def test_requirements_file_validity(self):
        """Ensure requirements.txt exists and contains necessary runtime, testing, and linting packages."""
        req_path = os.path.join(BASE_DIR, "requirements.txt")
        self.assertTrue(os.path.exists(req_path), "sentinelshield/requirements.txt must exist")

        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        required_packages = ["fastapi", "uvicorn", "numpy", "reportlab", "pytest", "pylint"]
        for pkg in required_packages:
            self.assertIn(pkg, content, f"requirements.txt missing required package '{pkg}'")
        print(f"[PASS] Requirements Validation: requirements.txt contains all core runtime & test dependencies {required_packages}!")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCodeQualityAndLintSanity)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
