#!/usr/bin/env python3
"""Usage: python test_suite.py [--verbose] [--failfast] # X.O.L.A. Master Test Suite Aggregator 🦋"""

import argparse
import datetime
import os
import sys
import time
import unittest

# Ensure project root is in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"

# Import all individual test modules
import tests.test_scout as test_scout
import tests.test_builder as test_builder
import tests.test_guard as test_guard
import tests.test_memory as test_memory
import tests.test_skills as test_skills
import tests.test_server as test_server
import tests.test_cli as test_cli
import tests.test_jarvis as test_jarvis
import tests.test_audit as test_audit

TEST_MODULES = [
    ("xola-scout", test_scout),
    ("xola-builder", test_builder),
    ("xola-guard", test_guard),
    ("xola-memory", test_memory),
    ("xola-skills", test_skills),
    ("xola-server", test_server),
    ("xola-cli", test_cli),
    ("xola-jarvis", test_jarvis),
    ("xola-audit", test_audit),
]


def build_aggregated_suite() -> unittest.TestSuite:
    """Construct full aggregated test suite combining all test modules 🦋"""
    loader = unittest.TestLoader()
    master_suite = unittest.TestSuite()

    for name, mod in TEST_MODULES:
        mod_suite = loader.loadTestsFromModule(mod)
        master_suite.addTest(mod_suite)

    return master_suite


def load_tests(loader, standard_tests, pattern):
    """Protocol for unittest runner discovery to load aggregated suite 🦋"""
    return build_aggregated_suite()


def run_test_suite(verbosity: int = 2, failfast: bool = False) -> unittest.TestResult:
    """Run all Phase 2 automated tests and render structured butterfly report 🦋"""
    start_time = time.perf_counter()
    ts_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n🦋 X.O.L.A. Master Automated Test Suite [{ts_now}] 🦋")
    print("=" * 76)
    print(f"Target Directory : {TESTS_DIR}")
    print(f"Python Runtime   : {sys.version.split()[0]} ({sys.executable})")
    print(f"Modules Covered  : {len(TEST_MODULES)} ({', '.join(name for name, _ in TEST_MODULES)})")
    print(f"Dependencies     : Stdlib only (unittest, zero external packages)")
    print("-" * 76)

    suite_results = []
    total_tests_run = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    loader = unittest.TestLoader()

    for mod_name, mod in TEST_MODULES:
        t0 = time.perf_counter()
        mod_suite = loader.loadTestsFromModule(mod)
        stream = sys.stdout if verbosity > 1 else None

        runner = unittest.TextTestRunner(
            verbosity=verbosity,
            failfast=failfast,
            stream=stream,
        )

        if verbosity > 1:
            print(f"\n[SUITE] Executing {mod_name} ({mod.__name__}) {WATERMARK} ...")

        res = runner.run(mod_suite)
        lat = time.perf_counter() - t0

        passed = res.testsRun - len(res.failures) - len(res.errors) - len(res.skipped)
        status_tag = "PASS" if res.wasSuccessful() else "FAIL"

        suite_results.append({
            "name": mod_name,
            "module": mod.__name__,
            "status": status_tag,
            "tests_run": res.testsRun,
            "passed": passed,
            "failures": len(res.failures),
            "errors": len(res.errors),
            "skipped": len(res.skipped),
            "latency_s": round(lat, 4),
        })

        total_tests_run += res.testsRun
        total_failures += len(res.failures)
        total_errors += len(res.errors)
        total_skipped += len(res.skipped)

        if failfast and not res.wasSuccessful():
            break

    total_latency = time.perf_counter() - start_time
    total_passed = total_tests_run - total_failures - total_errors - total_skipped
    all_passed = (total_failures == 0) and (total_errors == 0) and (total_tests_run > 0)
    pass_rate_pct = (total_passed / total_tests_run * 100.0) if total_tests_run > 0 else 0.0

    print("\n" + "=" * 76)
    print(f"🦋 X.O.L.A. Automated Test Suite — Summary Breakdown 🦋")
    print("=" * 76)
    print(f"{'Module / Subsystem':<20} | {'Status':<6} | {'Tests':<5} | {'Passed':<6} | {'Fail':<4} | {'Err':<4} | {'Latency'}")
    print("-" * 76)

    for sr in suite_results:
        st_tag = f"[{sr['status']}]"
        print(
            f"{sr['name']:<20} | {st_tag:<6} | {sr['tests_run']:>5} | "
            f"{sr['passed']:>6} | {sr['failures']:>4} | {sr['errors']:>4} | {sr['latency_s']:>6.3f}s"
        )

    print("-" * 76)
    verdict_banner = f"ALL {len(TEST_MODULES)} TEST SUITES PASSED CLEANLY 🦋" if all_passed else "FAILURES DETECTED IN SUITE"
    print(f"Overall Result : {verdict_banner}")
    print(f"Total Tests    : {total_tests_run} total | {total_passed} passed | {total_failures} failed | {total_errors} errors | {total_skipped} skipped")
    print(f"Pass Rate      : {pass_rate_pct:.2f}%")
    print(f"Total Duration : {total_latency:.3f}s")
    print("=" * 76 + "\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="xola-test-suite — Aggregator test runner for X.O.L.A. 🦋",
        epilog="Usage: python test_suite.py [--verbose] [--failfast] [--quiet]",
    )
    parser.add_argument("-v", "--verbose", action="store_true", default=True, help="Enable verbose test reporting")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode, only show summary")
    parser.add_argument("--failfast", action="store_true", help="Stop on first failure")
    args = parser.parse_args()

    verbosity = 1 if args.quiet else (2 if args.verbose else 1)
    success = run_test_suite(verbosity=verbosity, failfast=args.failfast)

    if not success:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
