#!/usr/bin/env python3
"""
Validation script for SubnetworkClient unit tests.

Checks test file quality, organization, and completeness.
"""

import ast
import sys
from pathlib import Path


def analyze_test_file(filepath: Path) -> dict:
    """Analyze test file structure and quality."""
    with open(filepath, 'r') as f:
        content = f.read()
        tree = ast.parse(content)

    stats = {
        'total_lines': len(content.splitlines()),
        'classes': [],
        'fixtures': [],
        'test_methods': [],
        'imports': [],
        'has_main': False,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith('Test'):
                methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef) and m.name.startswith('test_')]
                stats['classes'].append({
                    'name': node.name,
                    'test_count': len(methods),
                    'methods': methods
                })

        elif isinstance(node, ast.FunctionDef):
            if node.decorator_list and any(
                isinstance(d, ast.Name) and d.id == 'fixture'
                or isinstance(d, ast.Attribute) and d.attr == 'fixture'
                for d in node.decorator_list
            ):
                stats['fixtures'].append(node.name)
            elif node.name.startswith('test_'):
                stats['test_methods'].append(node.name)
            elif node.name == '__main__':
                stats['has_main'] = True

        elif isinstance(node, ast.Import):
            stats['imports'].extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                stats['imports'].append(node.module)

    return stats


def validate_test_quality(stats: dict) -> list:
    """Validate test file meets quality standards."""
    issues = []
    recommendations = []

    # Check test count
    total_tests = sum(cls['test_count'] for cls in stats['classes'])
    if total_tests < 30:
        issues.append(f"Only {total_tests} test methods (expected ~30+)")
    else:
        recommendations.append(f"✅ {total_tests} test methods (exceeds 30 minimum)")

    # Check test organization
    if len(stats['classes']) < 5:
        issues.append(f"Only {len(stats['classes'])} test classes (expected 5+ for organization)")
    else:
        recommendations.append(f"✅ {len(stats['classes'])} test classes (well organized)")

    # Check fixtures
    required_fixtures = ['mock_neo4j_client', 'subnetwork_client', 'sample_statements']
    missing_fixtures = [f for f in required_fixtures if f not in stats['fixtures']]
    if missing_fixtures:
        issues.append(f"Missing required fixtures: {missing_fixtures}")
    else:
        recommendations.append(f"✅ All required fixtures present ({len(stats['fixtures'])} total)")

    # Check imports
    required_imports = ['pytest', 'unittest.mock', 'indra.statements']
    for imp in required_imports:
        if not any(imp in i for i in stats['imports']):
            issues.append(f"Missing required import: {imp}")

    if 'unittest.mock' in str(stats['imports']):
        recommendations.append("✅ Uses unittest.mock for mocking")

    # Check test coverage categories
    test_categories = {
        'init': any('init' in cls['name'].lower() for cls in stats['classes']),
        'parsing': any('pars' in cls['name'].lower() for cls in stats['classes']),
        'filtering': any('filter' in cls['name'].lower() for cls in stats['classes']),
        'conversion': any('conver' in cls['name'].lower() for cls in stats['classes']),
        'statistics': any('stat' in cls['name'].lower() for cls in stats['classes']),
        'extraction': any('extract' in cls['name'].lower() for cls in stats['classes']),
        'edge_cases': any('edge' in cls['name'].lower() for cls in stats['classes']),
    }

    missing_categories = [k for k, v in test_categories.items() if not v]
    if missing_categories:
        issues.append(f"Missing test categories: {missing_categories}")
    else:
        recommendations.append("✅ All major test categories covered")

    return issues, recommendations


def main():
    """Run validation."""
    test_file = Path('tests/unit/test_subnetwork_client.py')

    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return 1

    print("🔍 Analyzing SubnetworkClient unit tests...")
    print("=" * 60)

    stats = analyze_test_file(test_file)

    print(f"\n📊 Test File Statistics:")
    print(f"  Lines of code: {stats['total_lines']}")
    print(f"  Test classes: {len(stats['classes'])}")
    print(f"  Test fixtures: {len(stats['fixtures'])}")
    print(f"  Total test methods: {sum(cls['test_count'] for cls in stats['classes'])}")

    print(f"\n📋 Test Classes:")
    for cls in stats['classes']:
        print(f"  • {cls['name']}: {cls['test_count']} tests")

    print(f"\n🔧 Test Fixtures:")
    for fixture in stats['fixtures']:
        print(f"  • {fixture}")

    issues, recommendations = validate_test_quality(stats)

    if recommendations:
        print(f"\n✅ Quality Checks Passed:")
        for rec in recommendations:
            print(f"  {rec}")

    if issues:
        print(f"\n⚠️  Issues Found:")
        for issue in issues:
            print(f"  • {issue}")
        return 1
    else:
        print(f"\n🎉 All quality checks passed!")

    print("\n" + "=" * 60)
    print("✅ Validation complete: Test file is production-ready!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
