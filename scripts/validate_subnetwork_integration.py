#!/usr/bin/env python3
"""
Validation script for SubnetworkClient integration in Neo4jClient.

This script verifies that:
1. SubnetworkClient is properly imported
2. Routing is configured for extract_subnetwork
3. The _execute_subnetwork_extraction method exists and is callable
4. The method signature is correct
"""

import inspect
import sys
from typing import get_type_hints


def validate_import():
    """Validate that SubnetworkClient is imported in neo4j_client.py"""
    print("=" * 70)
    print("VALIDATION 1: Import Check")
    print("=" * 70)

    try:
        from cogex_mcp.clients.neo4j_client import Neo4jClient
        from cogex_mcp.clients.subnetwork_client import SubnetworkClient
        print("✓ Both Neo4jClient and SubnetworkClient imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def validate_method_exists():
    """Validate that _execute_subnetwork_extraction method exists"""
    print("\n" + "=" * 70)
    print("VALIDATION 2: Method Existence Check")
    print("=" * 70)

    from cogex_mcp.clients.neo4j_client import Neo4jClient

    if not hasattr(Neo4jClient, '_execute_subnetwork_extraction'):
        print("✗ Method _execute_subnetwork_extraction not found in Neo4jClient")
        return False

    print("✓ Method _execute_subnetwork_extraction exists")

    # Check it's async
    method = getattr(Neo4jClient, '_execute_subnetwork_extraction')
    if not inspect.iscoroutinefunction(method):
        print("✗ Method is not async (should be async def)")
        return False

    print("✓ Method is async")
    return True


def validate_method_signature():
    """Validate method signature is correct"""
    print("\n" + "=" * 70)
    print("VALIDATION 3: Method Signature Check")
    print("=" * 70)

    from cogex_mcp.clients.neo4j_client import Neo4jClient

    method = getattr(Neo4jClient, '_execute_subnetwork_extraction')
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())

    expected_params = ['self', 'params']
    if params != expected_params:
        print(f"✗ Incorrect parameters. Expected {expected_params}, got {params}")
        return False

    print(f"✓ Method signature correct: {sig}")

    # Check return type
    if sig.return_annotation != 'dict[str, Any]':
        # Python 3.9+ uses dict[str, Any], older versions might use Dict[str, Any]
        # Both are acceptable
        print(f"  Note: Return annotation is {sig.return_annotation}")

    return True


def validate_routing():
    """Validate that routing logic is in place"""
    print("\n" + "=" * 70)
    print("VALIDATION 4: Routing Logic Check")
    print("=" * 70)

    import ast

    # Read the neo4j_client.py source
    with open('src/cogex_mcp/clients/neo4j_client.py', 'r') as f:
        source = f.read()

    # Check for the routing logic
    if 'if query_name == "extract_subnetwork":' in source:
        print('✓ Found routing logic: if query_name == "extract_subnetwork"')
    else:
        print('✗ Routing logic not found')
        return False

    # Check it calls the new method
    if 'return await self._execute_subnetwork_extraction(params)' in source:
        print('✓ Found call to _execute_subnetwork_extraction()')
    else:
        print('✗ Call to _execute_subnetwork_extraction() not found')
        return False

    return True


def validate_subnetwork_client_usage():
    """Validate that SubnetworkClient is instantiated and used"""
    print("\n" + "=" * 70)
    print("VALIDATION 5: SubnetworkClient Usage Check")
    print("=" * 70)

    with open('src/cogex_mcp/clients/neo4j_client.py', 'r') as f:
        source = f.read()

    # Check SubnetworkClient instantiation
    if 'SubnetworkClient(neo4j_client=self)' in source:
        print('✓ SubnetworkClient is instantiated correctly')
    else:
        print('✗ SubnetworkClient instantiation not found')
        return False

    # Check mode routing
    modes = ['direct', 'mediated', 'shared_upstream', 'shared_downstream']
    for mode in modes:
        if f'mode == "{mode}"' in source:
            print(f'✓ Routing for mode "{mode}" found')
        else:
            print(f'✗ Routing for mode "{mode}" not found')
            return False

    # Check method calls
    expected_calls = [
        'subnetwork_client.extract_direct(',
        'subnetwork_client.extract_mediated(',
        'subnetwork_client.extract_shared_upstream(',
        'subnetwork_client.extract_shared_downstream(',
    ]

    for call in expected_calls:
        if call in source:
            print(f'✓ Found call: {call}')
        else:
            print(f'✗ Call not found: {call}')
            return False

    return True


def validate_deprecated_dispatcher():
    """Validate that old dispatcher is marked as deprecated"""
    print("\n" + "=" * 70)
    print("VALIDATION 6: Deprecated Dispatcher Check")
    print("=" * 70)

    with open('src/cogex_mcp/clients/neo4j_client.py', 'r') as f:
        source = f.read()

    # Check that _dispatch_subnetwork_mode exists but is marked deprecated
    if 'def _dispatch_subnetwork_mode' in source:
        print('✓ Old dispatcher method still exists (for backward compatibility)')

        # Check for deprecation notice
        if 'DEPRECATED' in source and '_dispatch_subnetwork_mode' in source:
            print('✓ Dispatcher marked as DEPRECATED')
        else:
            print('⚠ Warning: Dispatcher not clearly marked as deprecated')

    # Check that it's NOT called in execute_query anymore
    lines = source.split('\n')
    in_execute_query = False
    for line in lines:
        if 'async def execute_query' in line:
            in_execute_query = True
        elif in_execute_query and 'async def ' in line:
            in_execute_query = False
        elif in_execute_query and 'self._dispatch_subnetwork_mode(params)' in line and not line.strip().startswith('#'):
            print('✗ Old dispatcher is still being called in execute_query!')
            return False

    print('✓ Old dispatcher NOT called in execute_query (correct)')
    return True


def print_summary(results):
    """Print validation summary"""
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    total = len(results)
    passed = sum(results.values())

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print("\n" + "-" * 70)
    print(f"Total: {passed}/{total} validations passed")
    print("-" * 70)

    if passed == total:
        print("\n🎉 ALL VALIDATIONS PASSED! SubnetworkClient is properly integrated.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} validation(s) failed. Please review the output above.")
        return 1


def main():
    """Run all validations"""
    print("SubnetworkClient Integration Validation")
    print("=" * 70)
    print()

    results = {
        'Import Check': validate_import(),
        'Method Existence': validate_method_exists(),
        'Method Signature': validate_method_signature(),
        'Routing Logic': validate_routing(),
        'SubnetworkClient Usage': validate_subnetwork_client_usage(),
        'Deprecated Dispatcher': validate_deprecated_dispatcher(),
    }

    return print_summary(results)


if __name__ == '__main__':
    sys.exit(main())
