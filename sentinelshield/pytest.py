"""Self-contained lightweight pytest implementation for test execution."""
from __future__ import annotations

import asyncio
import inspect
import os
import re
import sys
import time
import traceback
from typing import Any, Callable, Generator, List, Dict, Optional, Tuple, Type, Union

class FixtureDef:
    def __init__(self, fn: Callable, autouse: bool = False, scope: str = "function"):
        self.fn = fn
        self.name = fn.__name__
        self.autouse = autouse
        self.scope = scope

_fixtures: Dict[str, FixtureDef] = {}

def fixture(callable_or_scope=None, *args, autouse: bool = False, scope: str = "function", **kwargs):
    def decorator(fn: Callable):
        fdef = FixtureDef(fn, autouse=autouse, scope=scope)
        _fixtures[fn.__name__] = fdef
        return fn

    if callable(callable_or_scope):
        fn = callable_or_scope
        return decorator(fn)
    if isinstance(callable_or_scope, str):
        scope = callable_or_scope
    return decorator

class _RaisesContext:
    def __init__(self, expected_exc: Union[Type[Exception], Tuple[Type[Exception], ...]], match: Optional[str] = None):
        self.expected_exc = expected_exc
        self.match = match
        self.value: Optional[Exception] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"DID NOT RAISE {self.expected_exc}")
        if not issubclass(exc_type, self.expected_exc):
            return False
        self.value = exc_val
        if self.match is not None:
            if not re.search(self.match, str(exc_val)):
                raise AssertionError(f"Pattern {self.match!r} does not match {str(exc_val)!r}")
        return True

def raises(expected_exc: Union[Type[Exception], Tuple[Type[Exception], ...]], match: Optional[str] = None):
    return _RaisesContext(expected_exc, match=match)

class _Mark:
    def __getattr__(self, name: str):
        if name == "parametrize":
            def parametrize(argnames, argvalues):
                def decorator(fn):
                    if not hasattr(fn, "_pytest_parametrize"):
                        fn._pytest_parametrize = []
                    names = [n.strip() for n in argnames.split(",")] if isinstance(argnames, str) else list(argnames)
                    fn._pytest_parametrize.append((names, argvalues))
                    return fn
                return decorator
            return parametrize
        def marker(*args, **kwargs):
            def decorator(fn):
                return fn
            return decorator
        return marker

mark = _Mark()

class SkipTestException(Exception):
    """Raised when a test execution is skipped."""

def skip(reason: str = ""):
    """Skip test execution with a reason message."""
    raise SkipTestException(f"Skipped: {reason}")

def fail(msg: str = ""):
    """Explicitly fail a test execution."""
    raise AssertionError(msg)

class approx:
    def __init__(self, expected, rel=1e-6, abs=1e-12):
        self.expected = expected
        self.rel = rel
        self.abs = abs
    def __eq__(self, actual):
        if isinstance(self.expected, (int, float)):
            diff = abs(actual - self.expected)
            return diff <= max(self.rel * max(abs(actual), abs(self.expected)), self.abs)
        return False

def run_test_fn(fn: Callable, module_dict: Dict[str, Any]) -> None:
    # Resolve autouse fixtures in the module
    autouse_generators = []
    for name, fdef in list(_fixtures.items()):
        if fdef.autouse and name in module_dict:
            res = fdef.fn()
            if inspect.isgenerator(res):
                next(res)
                autouse_generators.append(res)

    # Resolve function parameter fixtures
    sig = inspect.signature(fn)
    kwargs = {}
    fn_generators = []
    for param_name in sig.parameters:
        if param_name in _fixtures:
            res = _fixtures[param_name].fn()
            if inspect.isgenerator(res):
                val = next(res)
                fn_generators.append(res)
                kwargs[param_name] = val
            else:
                kwargs[param_name] = res

    try:
        if inspect.iscoroutinefunction(fn):
            asyncio.run(fn(**kwargs))
        else:
            fn(**kwargs)
    finally:
        for g in reversed(fn_generators):
            try:
                next(g)
            except StopIteration:
                pass
        for g in reversed(autouse_generators):
            try:
                next(g)
            except StopIteration:
                pass

def main(args: Optional[List[str]] = None) -> int:
    if args is None:
        args = sys.argv[1:]

    test_targets = []
    verbose = False
    for a in args:
        if a in ("-v", "--verbose"):
            verbose = True
        elif a in ("-q", "--quiet"):
            verbose = False
        elif not a.startswith("-"):
            test_targets.append(a)

    if not test_targets:
        test_targets = ["sentinelshield/tests"]

    files_to_run: List[Tuple[str, Optional[str]]] = []
    for target in test_targets:
        if "::" in target:
            fpath, test_name = target.split("::", 1)
            files_to_run.append((fpath, test_name))
        elif os.path.isdir(target):
            for root, _, files in os.walk(target):
                for f in files:
                    if (f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py"):
                        files_to_run.append((os.path.join(root, f), None))
        elif os.path.isfile(target):
            files_to_run.append((target, None))

    total_passed = 0
    total_failed = 0
    failures = []
    start_time = time.time()

    print("=" * 30 + " test session starts " + "=" * 30)
    print(f"platform {sys.platform} -- Python {sys.version.split()[0]}")

    for fpath, specific_test in files_to_run:
        abs_path = os.path.abspath(fpath)
        mod_dir = os.path.dirname(abs_path)
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
        base_dir = os.path.dirname(os.path.dirname(abs_path))
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)

        import importlib.util
        mod_name = os.path.splitext(os.path.basename(fpath))[0]
        spec = importlib.util.spec_from_file_location(mod_name, abs_path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"ERROR loading {fpath}: {e}")
            traceback.print_exc()
            total_failed += 1
            continue

        test_funcs = []
        for name, val in inspect.getmembers(mod):
            if callable(val) and name.startswith("test_"):
                if specific_test is None or specific_test == name:
                    test_funcs.append((name, val))

        for name, fn in test_funcs:
            t0 = time.time()
            try:
                run_test_fn(fn, mod.__dict__)
                elapsed = time.time() - t0
                total_passed += 1
                if verbose:
                    print(f"{fpath}::{name} PASSED ({elapsed:.3f}s)")
                else:
                    sys.stdout.write(".")
                    sys.stdout.flush()
            except Exception as e:
                elapsed = time.time() - t0
                total_failed += 1
                failures.append((f"{fpath}::{name}", traceback.format_exc()))
                if verbose:
                    print(f"{fpath}::{name} FAILED ({elapsed:.3f}s)")
                else:
                    sys.stdout.write("F")
                    sys.stdout.flush()

    if not verbose:
        print("")

    for test_id, tb in failures:
        print("\n" + "_" * 30 + f" FAILURES: {test_id} " + "_" * 30)
        print(tb)

    total_time = time.time() - start_time
    if total_failed == 0:
        print(f"\n====== {total_passed} passed in {total_time:.2f}s ======")
        return 0
    else:
        print(f"\n====== {total_failed} failed, {total_passed} passed in {total_time:.2f}s ======")
        return 1

if __name__ == "__main__":
    sys.exit(main())
