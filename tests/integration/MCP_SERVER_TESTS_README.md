# MCP Server-Level Integration Tests

## Purpose

These tests validate the **ACTUAL production code path** that the MCP server uses in production, not just the tool wrapper functions.

## The Critical Problem

### What Was Wrong

Before these tests, we had a dangerous disconnect:

```
❌ OLD TESTS:
Tests import: cogex_mcp.tools.gene_feature
MCP server uses: cogex_mcp.server.handlers.gene_feature
→ DIFFERENT FILES, DIFFERENT DEPENDENCIES!
→ Tests can PASS while MCP server FAILS!
```

### Real Example of the Problem

**What happened:**
1. `_parse_disease_associations()` was missing from `server/handlers/gene_feature.py`
2. Regular tool tests passed because they tested `tools/gene_feature.py`
3. MCP server failed because it called `handlers/gene_feature.py` which lacked the function
4. **Tests gave false confidence!**

### What These Tests Fix

```
✅ NEW TESTS:
Tests directly call: cogex_mcp.server.handlers.gene_feature.handle()
MCP server calls: cogex_mcp.server.handlers.gene_feature.handle()
→ SAME CODE PATH!
→ Tests validate production behavior!
```

## Test Architecture

### Production Code Path

```
MCP Client
    ↓ JSON-RPC request
MCP Server (stdio transport)
    ↓
server.core.handle_call_tool()
    ↓
server.handlers.gene_feature.handle()
    ↓
clients.adapter.query()
    ↓
clients.neo4j_client / clients.rest_client
    ↓
CoGEx Backend
```

**These tests start from `server.core` onwards** to validate the actual production execution path.

## Test Structure

### File: `tests/integration/test_mcp_server.py`

```
test_mcp_server.py (18 tests, 1 xfailed)
├── TestMCPServerStartup (4 tests)
│   ├── test_server_starts_without_errors
│   ├── test_server_initialization_messages
│   ├── test_server_connects_to_backend
│   └── test_server_responds_to_initialize [XFAIL]
│
├── TestHandlerCodePaths (4 tests)
│   ├── test_gene_feature_handler_direct ⭐ CRITICAL
│   ├── test_disease_phenotype_handler_direct
│   ├── test_all_handlers_importable
│   └── test_handler_has_required_functions ⭐ CRITICAL
│
├── TestToolRegistryRouting (2 tests)
│   ├── test_tool_registry_returns_16_tools
│   └── test_handler_routing_complete
│
├── TestEndToEndHandlerExecution (3 tests)
│   ├── test_e2e_gene_query_through_handler ⭐ CRITICAL
│   ├── test_e2e_multiple_tool_calls
│   └── test_e2e_error_handling
│
├── TestHandlerDependencies (2 tests)
│   ├── test_all_handler_imports_work
│   └── test_handler_helper_functions_exist ⭐ CRITICAL
│
└── TestServerCoreFunctions (4 tests)
    ├── test_initialize_backend
    ├── test_handle_list_tools
    ├── test_handle_call_tool_routing ⭐ CRITICAL
    └── test_handle_call_tool_unknown_tool
```

## Critical Tests Explained

### ⭐ test_gene_feature_handler_direct

**What it does:**
```python
from cogex_mcp.server.handlers import gene_feature

result = await gene_feature.handle(args)  # What MCP server calls!
```

**Why critical:**
- Tests the ACTUAL handler code that MCP server executes
- Not the tool wrapper, but the production implementation
- Catches missing dependencies, imports, or functions

### ⭐ test_handler_has_required_functions

**What it does:**
```python
assert hasattr(gene_feature, "_parse_disease_associations")
assert hasattr(gene_feature, "_parse_expression_data")
```

**Why critical:**
- Catches missing helper functions
- This test would have caught the `_parse_disease_associations` bug
- Ensures handler modules are complete

### ⭐ test_e2e_gene_query_through_handler

**What it does:**
- Simulates complete MCP tool call
- Goes through: handler → adapter → backend
- Tests real data flow

**Why critical:**
- Tests the COMPLETE production path
- Validates end-to-end integration
- Catches issues that unit tests miss

### ⭐ test_handle_call_tool_routing

**What it does:**
```python
from cogex_mcp.server import handle_call_tool

result = await handle_call_tool(
    name="query_gene_or_feature",
    arguments={...}
)
```

**Why critical:**
- Tests the actual routing logic in `server.core`
- This is what MCP server calls for every tool invocation
- Validates tool name → handler mapping

## Running the Tests

### Run all MCP server tests

```bash
pytest tests/integration/test_mcp_server.py -v
```

### Run specific test classes

```bash
# Handler code path tests (most critical)
pytest tests/integration/test_mcp_server.py::TestHandlerCodePaths -v

# End-to-end execution tests
pytest tests/integration/test_mcp_server.py::TestEndToEndHandlerExecution -v

# Server core function tests
pytest tests/integration/test_mcp_server.py::TestServerCoreFunctions -v
```

### Run critical tests only

```bash
pytest tests/integration/test_mcp_server.py -v -k "handler_direct or has_required_functions or e2e_gene_query or call_tool_routing"
```

## Test Results

### Current Status (as of 2025-11-25)

```
✅ 18 passed
⚠️  1 xfailed (JSON-RPC protocol testing - needs implementation)
⏱️  ~30 seconds runtime
```

### Key Validations

✅ All 16 handlers are importable
✅ All handlers have required functions
✅ Handlers execute successfully
✅ Tool registry is complete
✅ Routing logic works
✅ Server initialization works
✅ Error handling works
✅ End-to-end data flow works

## What These Tests Catch

### 1. Missing Functions

**Example:**
```python
# Handler missing _parse_disease_associations()
→ test_handler_has_required_functions FAILS
→ Caught before production!
```

### 2. Import Errors

**Example:**
```python
# Handler imports non-existent module
→ test_all_handlers_importable FAILS
→ Caught at import time!
```

### 3. Routing Issues

**Example:**
```python
# Tool name not in routing table
→ test_handler_routing_complete FAILS
→ Caught before MCP client uses it!
```

### 4. Data Flow Problems

**Example:**
```python
# Handler returns wrong format
→ test_e2e_gene_query_through_handler FAILS
→ Caught before production!
```

## Comparison with Other Tests

### Tool Tests (test_tool01_integration.py)

```python
# What they test:
from cogex_mcp.tools.gene_feature import cogex_query_gene_or_feature
result = await cogex_query_gene_or_feature(query)

# Code path: Tool wrapper → adapter → backend
# Validates: Tool API and business logic
# Misses: Handler implementation differences
```

### MCP Server Tests (test_mcp_server.py)

```python
# What they test:
from cogex_mcp.server.handlers import gene_feature
result = await gene_feature.handle(args)

# Code path: Handler → adapter → backend (PRODUCTION PATH!)
# Validates: Actual MCP server execution
# Catches: Handler-specific issues
```

**Both are needed!** They test different code paths.

## Adding New Tests

### When to add MCP server tests

1. **New handler added** → Add handler import test
2. **New helper function** → Add to required functions test
3. **New tool** → Add to routing test
4. **New error handling** → Add error handling test

### Template for new handler test

```python
async def test_new_handler_direct(self):
    """Test new_handler directly (production code path)."""
    from cogex_mcp.server.handlers import new_handler

    args = {
        "mode": "some_mode",
        "param": "value",
        "response_format": "json",
    }

    result = await new_handler.handle(args)

    assert isinstance(result, list)
    assert len(result) == 1
    text = result[0].text

    assert not text.startswith("Error:")
    data = json.loads(text)
    # Validate data structure
```

## Server Process Testing (Experimental)

### Current Status

The tests include **experimental** server process testing:

```python
async def test_server_starts_without_errors(self):
    """Start actual MCP server process and verify startup."""
    proc = await start_mcp_server()
    # Check that process is running
    # Check stderr for errors
    await stop_mcp_server(proc)
```

### Why Experimental?

- **stdio protocol complexity**: MCP uses JSON-RPC over stdin/stdout
- **Buffering issues**: Non-blocking I/O requires careful handling
- **Timing sensitivity**: Init messages may be missed
- **Platform differences**: Process management differs on Windows/Unix

### Future Work

The `test_server_responds_to_initialize` test is marked `xfail` because it needs:

1. Proper JSON-RPC message framing
2. Non-blocking stdio communication
3. Message correlation (request ID → response)
4. Timeout handling

This is a valuable addition but requires significant implementation work.

## Success Criteria

For these tests to be considered successful:

✅ All handler imports work
✅ All handlers have required functions
✅ Tool registry is complete
✅ Routing logic covers all tools
✅ At least one E2E handler test passes
✅ Error handling works gracefully
✅ Server initialization works
✅ Tests run in < 60 seconds

**All criteria met! ✅**

## Maintenance

### When to update these tests

1. **Adding a new tool** → Update routing test, add handler test
2. **Modifying handler interface** → Update E2E tests
3. **Adding helper functions** → Update required functions test
4. **Changing error handling** → Update error handling test

### Test stability

These tests are **highly stable** because they test:
- Function existence (structural)
- Import success (compile-time)
- Basic execution (runtime)

They do NOT test:
- Specific data values (too brittle)
- Backend data availability (too flaky)
- Complex workflows (too slow)

## Related Documentation

- **Tool Tests**: `tests/integration/test_tool01_integration.py`
- **Handler Code**: `src/cogex_mcp/server/handlers/`
- **Server Core**: `src/cogex_mcp/server/core.py`
- **Tools Registry**: `src/cogex_mcp/server/tools_registry.py`

## Questions?

### "Why not just test the tools?"

Because **tools and handlers are different code!** The MCP server doesn't call tools, it calls handlers.

### "Why not mock the backend?"

We want to test the **complete production path**, including backend communication. Unit tests with mocks serve a different purpose.

### "Why are some tests xfailed?"

`xfail` marks tests that **should eventually work** but need more implementation. They document what's missing without breaking CI.

### "How do I debug a failing test?"

1. Run with verbose output: `pytest -vv`
2. Check stderr: Handler logs go to stderr
3. Add breakpoints: Tests support `pytest --pdb`
4. Check adapter logs: Look for connection issues

## Summary

These tests are **critical for production confidence** because they:

1. ✅ Test the ACTUAL code path MCP server uses
2. ✅ Catch handler-specific bugs before production
3. ✅ Validate complete end-to-end integration
4. ✅ Run quickly (~30 seconds)
5. ✅ Are stable and maintainable

**They complement, not replace, the existing tool tests.** Both are needed for comprehensive coverage.
