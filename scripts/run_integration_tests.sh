#!/bin/bash
# Run integration tests with proper environment
# Tests all Phase 1 and Phase 2 fixes end-to-end

set -e

cd /Users/noot/Documents/indra-cogex-mcp

echo "=================================================="
echo "INDRA CoGEx MCP - Integration Test Suite"
echo "Testing Phase 1 & Phase 2 Fixes"
echo "=================================================="
echo ""

# Activate venv
if [ ! -d ".venv" ]; then
    echo "❌ Error: .venv not found"
    echo "   Run: python -m venv .venv && source .venv/bin/activate && pip install -e .[test]"
    exit 1
fi

source .venv/bin/activate

# Check credentials
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Run: cp .env.example .env and configure credentials"
    exit 1
fi

echo "✓ Environment configured"
echo "✓ Testing against live backends:"
echo "  - Neo4j: bolt://indra-cogex-lb-..."
echo "  - REST: https://discovery.indra.bio"
echo ""

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    echo "❌ Error: pytest not installed"
    echo "   Run: pip install -e .[test]"
    exit 1
fi

echo "=================================================="
echo "Running Integration Tests..."
echo "=================================================="
echo ""

# Track results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run test and capture results
run_test() {
    local test_file=$1
    local test_name=$2

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if pytest "$test_file" -v -m integration --tb=short --color=yes; then
        echo "✓ $test_name: PASSED"
        return 0
    else
        echo "✗ $test_name: FAILED"
        return 1
    fi
    echo ""
}

# Layer 4: Backend Client Tests
echo ""
echo "1. Testing Backend Clients (Layer 4)"
echo "   - Neo4j connection and queries"
echo "   - REST API connection and endpoints"
echo "   - Phase 1 & 2 fix validation"
echo ""

if run_test "tests/integration/test_backend_clients.py" "Backend Clients"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Layer 2: Entity Resolver Tests
echo ""
echo "2. Testing Entity Resolver (Layer 2)"
echo "   - Symbol resolution (TP53)"
echo "   - CURIE resolution (hgnc:11998)"
echo "   - Tuple resolution ((HGNC, 11998))"
echo "   - Query routing validation"
echo ""

if run_test "tests/integration/test_entity_resolver_integration.py" "Entity Resolver"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Layer 1: MCP Tool Integration Tests
echo ""
echo "3. Testing Tool 1 (Layer 1)"
echo "   - cogex_query_gene_or_feature"
echo "   - gene_to_features mode"
echo "   - tissue_to_genes mode"
echo "   - GO term queries"
echo ""

if run_test "tests/integration/test_tool01_integration.py" "Tool 1 Integration"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# End-to-End Workflow Tests
echo ""
echo "4. Testing E2E Workflows"
echo "   - Simple gene lookup"
echo "   - Multi-gene comparison"
echo "   - Identifier format handling"
echo "   - Error recovery"
echo "   - Phase validation"
echo ""

if run_test "tests/integration/test_e2e_integration.py" "E2E Workflows"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Summary
echo ""
echo "=================================================="
echo "Test Suite Complete!"
echo "=================================================="
echo ""
echo "Results:"
echo "  Total test files: $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS"
echo "  Failed: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ All integration tests passed!"
    echo ""
    echo "Phase 1 Fixes Validated:"
    echo "  ✓ Entity resolver query routing"
    echo "  ✓ Neo4j schema corrections"
    echo "  ✓ Symbol/CURIE/tuple resolution"
    echo ""
    echo "Phase 2 Fixes Validated:"
    echo "  ✓ REST client None parameter handling"
    echo "  ✓ Endpoint lazy evaluation"
    echo ""
    exit 0
else
    echo "⚠ Some tests failed. Check logs above for details."
    echo ""
    echo "To run specific test categories:"
    echo "  pytest tests/integration/test_backend_clients.py -v"
    echo "  pytest tests/integration/test_entity_resolver_integration.py -v"
    echo "  pytest tests/integration/test_tool01_integration.py -v"
    echo "  pytest tests/integration/test_e2e_integration.py -v"
    echo ""
    echo "To run with more detail:"
    echo "  pytest tests/integration/ -v -s --log-cli-level=INFO"
    echo ""
    exit 1
fi
