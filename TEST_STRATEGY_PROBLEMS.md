# Test Strategy Problems and Solutions

**Date**: 2025-11-25
**Issue**: Tests pass (120 passed, 48 xfailed, 19 xpassed) but tools fail when actually used in production

## Critical Problems

### 1. Tests Don't Validate Actual Data is Returned

**Current Test Pattern** (from `test_tool01_integration.py` line 46-47):
```python
# Should not be an error
assert not result.startswith("Error:"), f"Query failed: {result}"
```

**Problem**: Tests only check that the result doesn't start with "Error:" - they don't assert that meaningful data was actually returned.

**Example** (lines 87-94):
```python
# Check for at least some features
feature_keys = ["expression", "go_terms", "pathways", "diseases"]
found_features = [k for k in feature_keys if k in data]

logger.info(f"✓ TP53 full profile with {len(found_features)} feature types")
for key in found_features:
    if data.get(key):
        logger.info(f"  - {key}: {len(data[key])} entries")
```

This **logs** the features but **doesn't assert** they exist! Test passes even if all features are empty.

### 2. Missing Runtime Imports Not Caught

**Example**: `_parse_disease_associations()` was missing from `server/handlers/gene_feature.py`

- Tests import `cogex_mcp.tools.gene_feature` (standalone tool module)
- MCP server uses `cogex_mcp.server.handlers.gene_feature` (modular handler)
- These are DIFFERENT files with different dependencies
- Tests pass because they test the `tools/` version, but MCP server fails because `handlers/` version is missing imports

### 3. Tests Don't Use the MCP Server

Tests call tool functions directly:
```python
result = await cogex_query_gene_or_feature(query)
```

But in production, tools run through the MCP server which:
- Uses different imports (handlers vs tools)
- Goes through additional layers (server → handler → adapter → client)
- Has different error handling paths

**Tests pass but production fails because they're testing different code paths.**

### 4. No End-to-End MCP Protocol Tests

Current tests:
- ✓ Test tool functions directly
- ✗ Don't test MCP server startup
- ✗ Don't test MCP protocol communication
- ✗ Don't test actual Claude Code integration

## Required Fixes

### Fix 1: Add Data Validation Assertions

**Before**:
```python
assert not result.startswith("Error:")
```

**After**:
```python
assert not result.startswith("Error:")

# Validate actual data returned
data = json.loads(result)
assert "gene" in data
assert data["gene"]["name"] == "TP53"

# If requesting features, assert they're present and non-empty
if include_expression:
    assert "expression" in data, "Expression data should be present"
    assert len(data["expression"]) > 0, "Expression data should not be empty"
```

### Fix 2: Add MCP Server Integration Tests

Create `test_mcp_server_integration.py`:
```python
import subprocess
import json
import asyncio

async def test_mcp_server_starts():
    """Test MCP server starts without errors."""
    proc = subprocess.Popen(
        [venv_python, "-m", "cogex_mcp.server"],
        env={"PYTHONPATH": src_path},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for initialization
    await asyncio.sleep(2)

    # Server should still be running
    assert proc.poll() is None, "Server crashed on startup"

    proc.terminate()

async def test_mcp_tool_via_protocol():
    """Test calling a tool through MCP protocol."""
    # Start server
    proc = subprocess.Popen(...)

    # Send MCP initialize request
    request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {...},
        "id": 1
    }

    # Validate response
    # Send tool call request
    # Validate data returned
```

### Fix 3: Test Both Code Paths

For each tool, test:
1. **Direct tool function** (`tools/gene_feature.py`)
2. **Handler function** (`server/handlers/gene_feature.py`)
3. **Full MCP server path** (through protocol)

### Fix 4: Add Smoke Tests for All 16 Tools

Current coverage:
- Tool 1 (Gene/Feature): Well tested
- Tools 2-16: Minimal or no tests

**Required**: Each tool needs at least:
```python
async def test_tool_N_smoke():
    """Smoke test: Tool N returns data, not empty."""
    result = await tool_function(valid_input)

    assert not result.startswith("Error:")
    data = json.loads(result)

    # Assert key data fields are present and non-empty
    assert len(data) > 0
    assert data["primary_field"]  # Whatever the key field is
```

### Fix 5: Add Data Quality Checks

Beyond "data exists", validate:
```python
# Check data structure
assert "gene" in data
assert "name" in data["gene"]
assert "curie" in data["gene"]

# Check data quality
assert data["gene"]["name"], "Gene name should not be empty"
assert data["gene"]["curie"].startswith("hgnc:"), "Should be valid HGNC CURIE"

# Check feature data quality
if "expression" in data:
    for expr in data["expression"]:
        assert "tissue" in expr
        assert expr["tissue"]["name"], "Tissue name should not be empty"
```

### Fix 6: Test Against Real Database

Current tests use live Neo4j - good! But need to:
- Verify queries return actual data (not empty results)
- Test with known entities that definitely exist
- Assert minimum data counts (e.g., "TP53 should have >10 pathways")

Example:
```python
async def test_tp53_pathways_exist():
    """TP53 should have pathway data in database."""
    result = await query_gene("TP53", include_pathways=True)

    data = json.loads(result)
    assert "pathways" in data
    assert len(data["pathways"]) > 5, "TP53 should be in multiple pathways"
```

## Implementation Priority

1. **HIGH**: Fix Tool 1 tests to assert data exists and is valid
2. **HIGH**: Add `test_mcp_server_integration.py` to test server startup
3. **HIGH**: Add smoke tests for Tools 2-16
4. **MEDIUM**: Test handler code paths separately from tool functions
5. **MEDIUM**: Add MCP protocol-level tests
6. **LOW**: Add comprehensive data quality checks

## Test Success Criteria

A test should only pass if:
1. No errors occurred ✓
2. Response is well-formed JSON/Markdown ✓
3. **Primary data fields are present** ← Currently missing!
4. **Primary data fields are non-empty** ← Currently missing!
5. Data structure matches expected schema ← Currently missing!

## Example: Proper Test for Tool 1

```python
async def test_tp53_comprehensive_validation(self):
    """Test TP53 query with full data validation."""
    query = GeneFeatureQuery(
        mode=QueryMode.GENE_TO_FEATURES,
        gene="TP53",
        include_expression=True,
        include_go_terms=True,
        include_pathways=True,
        include_diseases=True,
        response_format=ResponseFormat.JSON,
        limit=10
    )

    result = await cogex_query_gene_or_feature(query)

    # 1. No errors
    assert not result.startswith("Error:"), f"Query failed: {result}"

    # 2. Valid JSON
    data = json.loads(result)

    # 3. Gene data present
    assert "gene" in data, "Response should include gene info"
    assert data["gene"]["name"] == "TP53"
    assert data["gene"]["curie"] == "hgnc:11998"

    # 4. Features present when requested
    assert "expression" in data, "Expression should be present"
    assert "go_terms" in data, "GO terms should be present"
    assert "pathways" in data, "Pathways should be present"
    assert "diseases" in data, "Diseases should be present"

    # 5. Features non-empty (TP53 is well-studied)
    assert len(data["expression"]) > 0, "TP53 should have expression data"
    assert len(data["go_terms"]) > 0, "TP53 should have GO annotations"
    assert len(data["pathways"]) > 0, "TP53 should be in pathways"
    assert len(data["diseases"]) > 0, "TP53 should have disease associations"

    # 6. Data quality checks
    for expr in data["expression"]:
        assert "tissue" in expr
        assert expr["tissue"]["name"], "Tissue name should not be empty"

    for go_term in data["go_terms"]:
        assert "go_term" in go_term
        assert go_term["go_term"]["curie"].startswith("GO:"), "Should be valid GO ID"

    logger.info(f"✓ TP53 full validation passed: {len(data['expression'])} tissues, "
                f"{len(data['go_terms'])} GO terms, {len(data['pathways'])} pathways")
```

## Root Cause

**Tests were written to verify "code runs without crashing" rather than "tools return meaningful data".**

This is a common anti-pattern in integration testing. The fix is to always assert on the actual data, not just the absence of errors.
