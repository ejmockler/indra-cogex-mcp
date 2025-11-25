#!/usr/bin/env python3
"""
Performance test runner with comprehensive reporting.

Usage:
    python tests/performance/run_performance_tests.py [--quick] [--verbose]

Options:
    --quick     Run quick test suite (fewer iterations)
    --verbose   Enable verbose output
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from profiler import PerformanceProfiler

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging for test runner."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("tests/performance/reports/test_run.log", mode="w"),
        ],
    )


def run_pytest(test_path: str, markers: str = None, verbose: bool = False) -> int:
    """
    Run pytest with specified parameters.

    Args:
        test_path: Path to test file or directory
        markers: Pytest markers to filter tests
        verbose: Enable verbose output

    Returns:
        Exit code from pytest
    """
    cmd = ["pytest", test_path]

    if markers:
        cmd.extend(["-m", markers])

    if verbose:
        cmd.append("-v")

    cmd.extend(
        [
            "--log-cli-level=INFO",
            "--tb=short",
            "-x",  # Stop on first failure
        ]
    )

    logger.info(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def print_banner(text: str):
    """Print formatted banner."""
    width = 80
    print("\n" + "=" * width)
    print(text.center(width))
    print("=" * width + "\n")


def main():
    """Run performance tests and generate reports."""
    parser = argparse.ArgumentParser(description="Run INDRA CoGEx MCP performance tests")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test suite (fewer iterations)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--suite",
        choices=["all", "latency", "concurrency", "pool", "cache"],
        default="all",
        help="Test suite to run",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    print_banner("INDRA CoGEx MCP Performance Testing Framework")

    start_time = datetime.now()
    logger.info(f"Test run started at {start_time.isoformat()}")

    # Initialize profiler
    profiler = PerformanceProfiler()
    reports_dir = Path("tests/performance/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Define test suites
    test_suites = {
        "latency": {
            "name": "Latency Benchmarks",
            "path": "tests/performance/test_latency_benchmarks.py",
            "description": "Benchmark latency for all 16 tools",
        },
        "concurrency": {
            "name": "Concurrency Tests",
            "path": "tests/performance/test_concurrency.py",
            "description": "Test concurrent query handling",
        },
        "pool": {
            "name": "Connection Pool Tests",
            "path": "tests/performance/test_connection_pool.py",
            "description": "Analyze connection pool efficiency",
        },
        "cache": {
            "name": "Cache Performance Tests",
            "path": "tests/performance/test_cache_warmup.py",
            "description": "Measure cache effectiveness",
        },
    }

    # Determine which suites to run
    if args.suite == "all":
        suites_to_run = list(test_suites.keys())
    else:
        suites_to_run = [args.suite]

    # Run test suites
    results = {}
    for suite_name in suites_to_run:
        suite = test_suites[suite_name]

        print_banner(suite["name"])
        logger.info(f"Description: {suite['description']}")

        exit_code = run_pytest(
            suite["path"],
            markers="performance",
            verbose=args.verbose,
        )

        results[suite_name] = {
            "name": suite["name"],
            "exit_code": exit_code,
            "passed": exit_code == 0,
        }

        if exit_code != 0:
            logger.error(f"{suite['name']} failed with exit code {exit_code}")
        else:
            logger.info(f"{suite['name']} completed successfully")

    # Generate summary report
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print_banner("Performance Test Summary")

    # Print suite results
    print("Test Suite Results:")
    print("-" * 80)
    for _suite_name, result in results.items():
        status = "✓ PASSED" if result["passed"] else "✗ FAILED"
        print(f"{result['name']:40s} {status}")
    print()

    # Print statistics
    passed = sum(1 for r in results.values() if r["passed"])
    total = len(results)
    print(f"Total: {passed}/{total} suites passed")
    print(f"Duration: {duration:.1f} seconds")
    print()

    # Generate optimization recommendations
    print_banner("Generating Optimization Recommendations")
    try:
        profiler.save_recommendations()
        profiler.print_summary()
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")

    # Save run summary
    summary = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "suites": results,
        "passed": passed,
        "total": total,
        "success_rate": (passed / total) * 100 if total > 0 else 0,
    }

    summary_file = reports_dir / f"run_summary_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Run summary saved to {summary_file}")

    # Print final status
    print_banner("Performance Testing Complete")
    print(f"Reports available in: {reports_dir}")
    print(f"Run summary: {summary_file}")
    print()

    # Exit with failure if any suite failed
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
