#!/usr/bin/env python3
"""
Verify performance testing framework installation and readiness.

This script checks that all components are properly installed and configured.
"""

import sys
from pathlib import Path


def check_file_exists(file_path: Path, description: str) -> bool:
    """Check if a file exists and print status."""
    if file_path.exists():
        size = file_path.stat().st_size
        print(f"✓ {description}: {file_path.name} ({size:,} bytes)")
        return True
    else:
        print(f"✗ {description}: {file_path.name} MISSING")
        return False


def count_test_methods(file_path: Path) -> int:
    """Count test methods in a test file."""
    if not file_path.exists():
        return 0

    with open(file_path) as f:
        content = f.read()
        return content.count("async def test_")


def main():
    """Verify framework installation."""
    print("=" * 80)
    print("Performance Testing Framework - Installation Verification")
    print("=" * 80)
    print()

    base_dir = Path(__file__).parent
    checks_passed = []

    # Check core files
    print("Core Files:")
    print("-" * 80)
    checks_passed.append(check_file_exists(base_dir / "__init__.py", "Module init"))
    checks_passed.append(check_file_exists(base_dir / "conftest.py", "Test fixtures"))
    checks_passed.append(check_file_exists(base_dir / "profiler.py", "Profiler utilities"))
    print()

    # Check test files
    print("Test Files:")
    print("-" * 80)
    test_files = [
        ("test_latency_benchmarks.py", "Latency benchmarks"),
        ("test_concurrency.py", "Concurrency tests"),
        ("test_connection_pool.py", "Connection pool tests"),
        ("test_cache_warmup.py", "Cache performance tests"),
        ("test_framework_validation.py", "Framework validation"),
    ]

    total_tests = 0
    for file_name, description in test_files:
        file_path = base_dir / file_name
        exists = check_file_exists(file_path, description)
        checks_passed.append(exists)
        if exists:
            test_count = count_test_methods(file_path)
            total_tests += test_count
            print(f"  → {test_count} test methods")

    print(f"\nTotal test methods: {total_tests}")
    print()

    # Check documentation
    print("Documentation:")
    print("-" * 80)
    checks_passed.append(check_file_exists(base_dir / "README.md", "Framework README"))
    checks_passed.append(
        check_file_exists(base_dir / "PERFORMANCE_SUMMARY.md", "Performance summary")
    )
    print()

    # Check scripts
    print("Scripts:")
    print("-" * 80)
    checks_passed.append(
        check_file_exists(base_dir / "run_performance_tests.py", "Test runner script")
    )
    print()

    # Check reports directory
    print("Reports Directory:")
    print("-" * 80)
    reports_dir = base_dir / "reports"
    if reports_dir.exists():
        print(f"✓ Reports directory: {reports_dir}")
        # List existing reports
        report_files = list(reports_dir.glob("*.json"))
        if report_files:
            print(f"  → {len(report_files)} existing reports:")
            for rf in report_files:
                print(f"    - {rf.name}")
        else:
            print("  → No reports yet (will be generated when tests run)")
    else:
        print(f"✗ Reports directory: {reports_dir} MISSING")
        reports_dir.mkdir(parents=True, exist_ok=True)
        print("  → Created reports directory")
    print()

    # Check dependencies
    print("Dependencies:")
    print("-" * 80)
    try:
        import pytest

        print(f"✓ pytest: {pytest.__version__}")
    except ImportError:
        print("✗ pytest: NOT INSTALLED")
        checks_passed.append(False)

    try:
        import pytest_asyncio

        print(f"✓ pytest-asyncio: {pytest_asyncio.__version__}")
    except ImportError:
        print("✗ pytest-asyncio: NOT INSTALLED")
        checks_passed.append(False)

    try:
        import neo4j

        print(f"✓ neo4j: {neo4j.__version__}")
    except ImportError:
        print("✗ neo4j: NOT INSTALLED")
        checks_passed.append(False)

    try:
        import tenacity

        print(f"✓ tenacity: {tenacity.__version__}")
    except ImportError:
        print("✗ tenacity: NOT INSTALLED")
        checks_passed.append(False)

    print()

    # Summary
    print("=" * 80)
    print("Verification Summary")
    print("=" * 80)

    passed = sum(checks_passed)
    total = len(checks_passed)
    success_rate = (passed / total) * 100 if total > 0 else 0

    print(f"Checks passed: {passed}/{total} ({success_rate:.0f}%)")
    print(f"Test methods: {total_tests}")
    print()

    if passed == total:
        print("✅ Framework is ready for execution!")
        print()
        print("Next steps:")
        print("1. Verify .env.production has Neo4j credentials")
        print("2. Run framework validation:")
        print("   pytest tests/performance/test_framework_validation.py -v")
        print("3. Run full test suite:")
        print("   python tests/performance/run_performance_tests.py")
        print()
        return 0
    else:
        print("⚠️ Framework has missing components")
        print("Please review the missing items above.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
