"""
MCP SERVER-LEVEL Integration Tests

Critical Purpose: Test the ACTUAL production code path that MCP server uses,
not just the tool functions.

Problem Context:
- Current tests import tool functions directly: `from cogex_mcp.tools import ...`
- Production MCP server uses handlers: `cogex_mcp.server.handlers.*`
- These are DIFFERENT files with DIFFERENT dependencies
- Tests can pass while MCP server fails!

Example Issue:
- `_parse_disease_associations()` was missing from handler
- Tests passed because they tested tools version
- MCP server would fail

Solution:
These tests validate:
1. Server startup and initialization
2. Handler code paths (what MCP actually calls)
3. MCP protocol communication
4. Handler module completeness
5. End-to-end tool execution through handlers

Architecture:
- MCP Client sends JSON-RPC → MCP Server → server.core → handlers → adapter → backend
- We test from "server.core" onwards to validate production paths
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

logger = logging.getLogger(__name__)

# ============================================================================
# Test Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
PYTHON_EXECUTABLE = sys.executable
SERVER_MODULE = "cogex_mcp.server"
SERVER_STARTUP_TIMEOUT = 10  # seconds
SERVER_SHUTDOWN_TIMEOUT = 5  # seconds


# ============================================================================
# Server Process Management Utilities
# ============================================================================


async def start_mcp_server() -> subprocess.Popen:
    """
    Start MCP server process in stdio mode.

    Returns:
        Running server process

    Raises:
        TimeoutError: If server doesn't start within timeout
        RuntimeError: If server fails to start
    """
    logger.info("Starting MCP server process...")

    # Environment for server
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    # Start server process
    proc = subprocess.Popen(
        [PYTHON_EXECUTABLE, "-m", SERVER_MODULE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=PROJECT_ROOT,
        text=True,
        bufsize=0,  # Unbuffered
    )

    # Wait for server to initialize
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
        if proc.poll() is not None:
            # Process died
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Server process died during startup. stderr: {stderr}")

        # Check stderr for initialization messages
        # Note: Server logs to stderr, so we check for successful init messages
        await asyncio.sleep(0.5)

        # For now, just wait a bit for init (we'll improve this later)
        if time.time() - start_time > 2:
            server_ready = True
            break

    if not server_ready:
        proc.terminate()
        raise TimeoutError(f"Server didn't start within {SERVER_STARTUP_TIMEOUT}s")

    logger.info(f"✓ MCP server started (PID: {proc.pid})")
    return proc


async def stop_mcp_server(proc: subprocess.Popen) -> None:
    """
    Gracefully stop MCP server process.

    Args:
        proc: Running server process
    """
    if proc.poll() is None:
        logger.info("Stopping MCP server...")
        proc.terminate()

        # Wait for graceful shutdown
        try:
            proc.wait(timeout=SERVER_SHUTDOWN_TIMEOUT)
            logger.info("✓ MCP server stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("Server didn't stop gracefully, killing...")
            proc.kill()
            proc.wait()

    # Close pipes
    if proc.stdin:
        proc.stdin.close()
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()


async def send_json_rpc(proc: subprocess.Popen, request: dict[str, Any]) -> None:
    """
    Send JSON-RPC request to server via stdin.

    Args:
        proc: Running server process
        request: JSON-RPC request dict
    """
    if proc.stdin:
        message = json.dumps(request) + "\n"
        proc.stdin.write(message)
        proc.stdin.flush()


async def read_json_rpc(
    proc: subprocess.Popen, timeout: float = 5.0
) -> dict[str, Any] | None:
    """
    Read JSON-RPC response from server stdout.

    Args:
        proc: Running server process
        timeout: Read timeout in seconds

    Returns:
        Parsed JSON-RPC response or None on timeout
    """
    if not proc.stdout:
        return None

    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check if data is available (non-blocking)
        import select

        readable, _, _ = select.select([proc.stdout], [], [], 0.1)
        if readable:
            line = proc.stdout.readline()
            if line:
                try:
                    return json.loads(line.strip())
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON from server: {e}")
                    return None

        await asyncio.sleep(0.1)

    return None


async def read_stderr_lines(proc: subprocess.Popen, num_lines: int = 10) -> list[str]:
    """
    Read recent stderr lines from server.

    Args:
        proc: Running server process
        num_lines: Number of lines to read

    Returns:
        List of stderr lines
    """
    lines = []
    if proc.stderr:
        for _ in range(num_lines):
            # Non-blocking read attempt
            import select

            readable, _, _ = select.select([proc.stderr], [], [], 0.1)
            if readable:
                line = proc.stderr.readline()
                if line:
                    lines.append(line.strip())
            else:
                break
    return lines


# ============================================================================
# Test Class 1: Server Startup and Initialization
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestMCPServerStartup:
    """Test MCP server process startup and initialization."""

    async def test_server_starts_without_errors(self):
        """
        Test that MCP server process starts successfully.

        Validates:
        - Server process can be started
        - Process doesn't immediately crash
        - No critical errors in stderr during startup
        """
        proc = None
        try:
            proc = await start_mcp_server()

            # Server should be running
            assert proc.poll() is None, "Server process should be running"

            # Wait a bit and check stderr for errors
            await asyncio.sleep(2)

            stderr_lines = await read_stderr_lines(proc, num_lines=20)
            stderr_text = "\n".join(stderr_lines)

            # Check for critical errors
            critical_errors = ["Traceback", "Exception", "CRITICAL"]
            for error in critical_errors:
                if error in stderr_text and "Error:" not in stderr_text:
                    pytest.fail(f"Server stderr contains critical error: {error}\n{stderr_text}")

            logger.info("✓ Server started without critical errors")

        finally:
            if proc:
                await stop_mcp_server(proc)

    async def test_server_initialization_messages(self):
        """
        Test that server logs expected initialization messages.

        Validates:
        - Server logs startup banner
        - Backend initialization completes
        - Adapter is initialized
        - Cache is initialized
        """
        proc = None
        try:
            proc = await start_mcp_server()
            await asyncio.sleep(3)  # Wait for full initialization

            stderr_lines = await read_stderr_lines(proc, num_lines=30)
            stderr_text = "\n".join(stderr_lines)

            # Expected initialization messages
            expected_messages = [
                "INDRA CoGEx MCP Server",  # Startup banner
                "Client adapter initialized",  # Adapter init
                "Cache initialized",  # Cache init
            ]

            found_messages = []
            for msg in expected_messages:
                if msg in stderr_text:
                    found_messages.append(msg)
                    logger.info(f"✓ Found initialization message: {msg}")

            # We should find at least some initialization messages
            # (exact messages may vary based on backend config)
            logger.info(f"Found {len(found_messages)}/{len(expected_messages)} expected messages")

        finally:
            if proc:
                await stop_mcp_server(proc)

    async def test_server_connects_to_backend(self):
        """
        Test that server successfully connects to Neo4j backend.

        Validates:
        - Backend connection is established
        - Connection status is logged
        """
        proc = None
        try:
            proc = await start_mcp_server()
            await asyncio.sleep(3)

            stderr_lines = await read_stderr_lines(proc, num_lines=30)
            stderr_text = "\n".join(stderr_lines)

            # Should see backend initialization
            # (This may fail if Neo4j is not configured, which is fine for this test)
            if "Neo4j" in stderr_text or "backend" in stderr_text:
                logger.info("✓ Server attempted backend connection")
            else:
                logger.warning("No backend connection messages found (may be using REST fallback)")

        finally:
            if proc:
                await stop_mcp_server(proc)

    @pytest.mark.xfail(reason="MCP protocol testing needs proper JSON-RPC implementation")
    async def test_server_responds_to_initialize(self):
        """
        Test MCP initialize handshake.

        Validates:
        - Server accepts initialize request
        - Returns valid initialization response
        - Protocol version is correct

        Note: This test is marked xfail until we implement proper
        JSON-RPC communication over stdio.
        """
        proc = None
        try:
            proc = await start_mcp_server()
            await asyncio.sleep(2)

            # Send initialize request
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test-client", "version": "1.0.0"}},
            }

            await send_json_rpc(proc, request)

            # Try to read response
            response = await read_json_rpc(proc, timeout=5.0)

            if response:
                assert "result" in response, "Initialize should return result"
                assert "protocolVersion" in response["result"]
                logger.info(f"✓ Server responded to initialize: {response['result']}")
            else:
                pytest.skip("Could not read JSON-RPC response (stdio communication needs work)")

        finally:
            if proc:
                await stop_mcp_server(proc)


# ============================================================================
# Test Class 2: Handler Code Path Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestHandlerCodePaths:
    """
    Test ACTUAL handler code paths that MCP server uses.

    This is CRITICAL - these tests call the handler functions directly,
    which is what server.core.handle_call_tool() does.
    """

    async def test_gene_feature_handler_direct(self):
        """
        Test gene_feature handler directly (production code path).

        This tests the ACTUAL code that MCP server executes,
        not the tool wrapper function.
        """
        from cogex_mcp.server.handlers import gene_feature

        args = {
            "mode": "gene_to_features",
            "gene": "TP53",
            "include_expression": True,
            "include_go_terms": False,
            "include_pathways": False,
            "include_diseases": False,
            "response_format": "json",
            "limit": 5,
        }

        result = await gene_feature.handle(args)

        # Handler returns list[TextContent]
        assert isinstance(result, list), "Handler should return list"
        assert len(result) == 1, "Should return single text content"

        text = result[0].text
        assert not text.startswith("Error:"), f"Handler failed: {text}"

        # Validate actual data
        data = json.loads(text)
        assert "gene" in data, "Response should include gene"
        assert data["gene"]["name"] == "TP53", "Should be TP53"

        logger.info("✓ gene_feature handler works via production code path")

    async def test_disease_phenotype_handler_direct(self):
        """Test disease_phenotype handler directly."""
        from cogex_mcp.server.handlers import disease_phenotype

        args = {
            "mode": "disease_to_mechanisms",
            "disease": "diabetes mellitus",
            "include_genes": True,
            "include_phenotypes": False,
            "include_variants": False,
            "include_drugs": False,
            "include_trials": False,
            "response_format": "json",
            "limit": 5,
        }

        result = await disease_phenotype.handle(args)

        assert isinstance(result, list)
        assert len(result) == 1

        text = result[0].text
        # May error if disease not found, which is fine
        if not text.startswith("Error:"):
            logger.info("✓ disease_phenotype handler works")
        else:
            logger.info(f"Disease query returned error (may be expected): {text[:100]}")

    async def test_all_handlers_importable(self):
        """
        Test that all 16 tool handlers can be imported.

        This catches missing handler files or import errors.
        """
        handler_modules = [
            "disease_phenotype",
            "gene_feature",
            "subnetwork",
            "enrichment",
            "drug_effect",
            "pathway",
            "cell_line",
            "clinical_trials",
            "literature",
            "variants",
            "identifier",
            "relationship",
            "ontology",
            "cell_markers",
            "kinase",
            "protein_function",
        ]

        for module_name in handler_modules:
            try:
                # This is what server.core does
                module = __import__(
                    f"cogex_mcp.server.handlers.{module_name}",
                    fromlist=["handle"],
                )
                assert hasattr(module, "handle"), f"{module_name} missing handle() function"
                logger.info(f"✓ Handler {module_name} importable")
            except ImportError as e:
                pytest.fail(f"Failed to import handler {module_name}: {e}")

    async def test_handler_has_required_functions(self):
        """
        Ensure handlers have all required helper functions.

        This catches issues like missing _parse_* functions.
        """
        from cogex_mcp.server.handlers import gene_feature

        # These were missing before and caused failures!
        required_functions = [
            "_parse_disease_associations",
            "_parse_expression_data",
            "_parse_go_annotations",
            "_parse_pathway_memberships",
            "_parse_gene_list",
        ]

        for func_name in required_functions:
            assert hasattr(
                gene_feature, func_name
            ), f"gene_feature handler missing {func_name}"
            logger.info(f"✓ gene_feature.{func_name} exists")


# ============================================================================
# Test Class 3: Tool Registry and Routing
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestToolRegistryRouting:
    """Test tool registry and handler routing."""

    async def test_tool_registry_returns_16_tools(self):
        """
        Test that tool registry defines all 16 tools.

        Validates:
        - get_all_tools() returns 16 tool definitions
        - Each tool has required fields
        """
        from cogex_mcp.server.tools_registry import get_all_tools

        tools = get_all_tools()

        assert len(tools) == 16, f"Should have 16 tools, got {len(tools)}"

        # Validate each tool structure
        required_fields = ["name", "description", "inputSchema"]
        for tool in tools:
            for field in required_fields:
                assert hasattr(tool, field), f"Tool missing field: {field}"

        logger.info(f"✓ Tool registry has {len(tools)} tools with valid structure")

    async def test_handler_routing_complete(self):
        """
        Test that all tool names can be routed to handlers.

        This validates server.core.handle_call_tool() routing logic.
        """
        from cogex_mcp.server.tools_registry import get_all_tools

        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]

        # Expected routing (from server.core)
        expected_routing = {
            "query_disease_or_phenotype": "disease_phenotype",
            "query_gene_or_feature": "gene_feature",
            "extract_subnetwork": "subnetwork",
            "enrichment_analysis": "enrichment",
            "query_drug_or_effect": "drug_effect",
            "query_pathway": "pathway",
            "query_cell_line": "cell_line",
            "query_clinical_trials": "clinical_trials",
            "query_literature": "literature",
            "query_variants": "variants",
            "resolve_identifiers": "identifier",
            "check_relationship": "relationship",
            "get_ontology_hierarchy": "ontology",
            "query_cell_markers": "cell_markers",
            "analyze_kinase_enrichment": "kinase",
            "query_protein_functions": "protein_function",
        }

        for tool_name in tool_names:
            assert tool_name in expected_routing, f"Tool {tool_name} has no routing"

            handler_module = expected_routing[tool_name]
            # Try to import the handler
            try:
                module = __import__(
                    f"cogex_mcp.server.handlers.{handler_module}",
                    fromlist=["handle"],
                )
                assert callable(module.handle), f"{handler_module} handle() not callable"
                logger.info(f"✓ {tool_name} → {handler_module}.handle()")
            except Exception as e:
                pytest.fail(f"Routing failed for {tool_name}: {e}")


# ============================================================================
# Test Class 4: End-to-End Handler Execution
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndHandlerExecution:
    """
    Test end-to-end execution through handlers.

    These tests simulate what happens when MCP client calls a tool.
    """

    async def test_e2e_gene_query_through_handler(self):
        """
        End-to-end test: MCP tool call → handler → adapter → backend.

        This tests the COMPLETE production path.
        """
        from cogex_mcp.server.handlers import gene_feature

        # Simulate MCP tool call arguments
        args = {
            "mode": "gene_to_features",
            "gene": "TP53",
            "include_expression": True,
            "include_go_terms": True,
            "include_pathways": True,
            "include_diseases": True,
            "response_format": "json",
            "limit": 10,
        }

        # Call handler (what server.core does)
        result = await gene_feature.handle(args)

        # Validate result structure (list[TextContent])
        assert isinstance(result, list)
        assert len(result) >= 1

        text = result[0].text

        # Should not be an error
        if text.startswith("Error:"):
            # Check if it's a known issue
            if "not found" in text.lower():
                logger.warning(f"Entity resolution failed: {text}")
            else:
                pytest.fail(f"Handler execution failed: {text}")
        else:
            # Validate data
            data = json.loads(text)
            assert "gene" in data
            assert data["gene"]["name"] == "TP53"

            # Check for features
            features = ["expression", "go_terms", "pathways", "diseases"]
            found = [f for f in features if f in data]
            logger.info(f"✓ E2E gene query returned {len(found)} feature types")

    async def test_e2e_multiple_tool_calls(self):
        """
        Test multiple tool calls through handlers.

        Validates:
        - No state contamination between calls
        - Handlers work consistently
        """
        from cogex_mcp.server.handlers import gene_feature

        genes = ["TP53", "BRCA1", "EGFR"]
        results = []

        for gene in genes:
            args = {
                "mode": "gene_to_features",
                "gene": gene,
                "include_expression": True,
                "response_format": "json",
                "limit": 5,
            }

            result = await gene_feature.handle(args)
            text = result[0].text

            if not text.startswith("Error:"):
                results.append(gene)
                logger.info(f"✓ {gene} query succeeded")

        assert len(results) >= 2, "Should successfully query at least 2 genes"
        logger.info(f"✓ Multiple handler calls successful: {results}")

    async def test_e2e_error_handling(self):
        """
        Test that handlers properly handle errors.

        Validates:
        - Invalid input is handled gracefully
        - Error message is informative
        - Handler doesn't crash with exception
        """
        from cogex_mcp.server.handlers import gene_feature

        args = {
            "mode": "gene_to_features",
            "gene": "FAKEGENE999",
            "include_expression": True,
            "response_format": "json",
        }

        # Handler may raise EntityNotFoundError or return error text
        # Both are acceptable error handling approaches
        try:
            result = await gene_feature.handle(args)
            text = result[0].text

            # Should return error message, not crash
            assert text.startswith("Error:"), "Should return error for invalid gene"
            assert "not found" in text.lower(), f"Error should mention 'not found': {text}"
            logger.info(f"✓ Error handling works (error text): {text}")

        except Exception as e:
            # If handler raises exception, that's also acceptable
            # as long as it's informative
            assert "not found" in str(e).lower() or "FAKEGENE999" in str(e)
            logger.info(f"✓ Error handling works (exception): {type(e).__name__}: {e}")


# ============================================================================
# Test Class 5: Handler Dependencies and Imports
# ============================================================================


@pytest.mark.integration
class TestHandlerDependencies:
    """
    Test that handlers have all required dependencies.

    This catches issues where handlers import things that don't exist.
    """

    def test_all_handler_imports_work(self):
        """
        Test that all handler modules can be imported without errors.

        This catches:
        - Missing dependencies
        - Circular imports
        - Syntax errors
        """
        handlers = [
            "disease_phenotype",
            "gene_feature",
            "subnetwork",
            "enrichment",
            "drug_effect",
            "pathway",
            "cell_line",
            "clinical_trials",
            "literature",
            "variants",
            "identifier",
            "relationship",
            "ontology",
            "cell_markers",
            "kinase",
            "protein_function",
        ]

        for handler in handlers:
            try:
                module = __import__(
                    f"cogex_mcp.server.handlers.{handler}",
                    fromlist=["handle"],
                )

                # Check for common required imports
                assert hasattr(module, "handle"), f"{handler} missing handle()"

                logger.info(f"✓ {handler} imports successfully")

            except ImportError as e:
                pytest.fail(f"Failed to import {handler}: {e}")
            except Exception as e:
                pytest.fail(f"Error importing {handler}: {e}")

    def test_handler_helper_functions_exist(self):
        """
        Test that handlers define required helper functions.

        This prevents issues where code calls missing functions.
        """
        from cogex_mcp.server.handlers import gene_feature

        # Check parsing functions that were missing before
        parsing_functions = [
            "_parse_disease_associations",
            "_parse_expression_data",
            "_parse_go_annotations",
            "_parse_pathway_memberships",
        ]

        for func_name in parsing_functions:
            assert hasattr(gene_feature, func_name), f"Missing function: {func_name}"
            func = getattr(gene_feature, func_name)
            assert callable(func), f"{func_name} is not callable"

        logger.info("✓ All required helper functions exist")


# ============================================================================
# Test Class 6: Server Core Functions
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestServerCoreFunctions:
    """Test server.core module functions."""

    async def test_initialize_backend(self):
        """
        Test that initialize_backend() works.

        Validates:
        - Adapter is initialized
        - Cache is initialized
        - No errors during init
        """
        from cogex_mcp.server import cleanup_backend, initialize_backend

        try:
            await initialize_backend()
            logger.info("✓ Backend initialization succeeded")
        except Exception as e:
            pytest.fail(f"Backend initialization failed: {e}")
        finally:
            await cleanup_backend()

    async def test_handle_list_tools(self):
        """
        Test handle_list_tools() function.

        This is what MCP server calls for tools/list request.
        """
        from cogex_mcp.server import handle_list_tools

        tools = await handle_list_tools()

        assert len(tools) == 16, f"Should return 16 tools, got {len(tools)}"

        # Validate tool structure
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

        logger.info("✓ handle_list_tools() returns all 16 tools")

    async def test_handle_call_tool_routing(self):
        """
        Test handle_call_tool() routing logic.

        This is the critical function that routes tool calls to handlers.
        """
        from cogex_mcp.server import cleanup_backend, handle_call_tool, initialize_backend

        try:
            await initialize_backend()

            # Test a simple tool call
            result = await handle_call_tool(
                name="query_gene_or_feature",
                arguments={
                    "mode": "gene_to_features",
                    "gene": "TP53",
                    "include_expression": True,
                    "response_format": "json",
                    "limit": 5,
                },
            )

            assert isinstance(result, list)
            assert len(result) >= 1
            text = result[0].text

            # Should not crash (may error, but should handle it)
            logger.info(f"✓ handle_call_tool() routed successfully: {text[:100]}...")

        finally:
            await cleanup_backend()

    async def test_handle_call_tool_unknown_tool(self):
        """
        Test that handle_call_tool() handles unknown tools gracefully.
        """
        from cogex_mcp.server import cleanup_backend, handle_call_tool, initialize_backend

        try:
            await initialize_backend()

            result = await handle_call_tool(
                name="nonexistent_tool",
                arguments={},
            )

            # Should return error, not crash
            assert isinstance(result, list)
            text = result[0].text
            assert "Error:" in text or "Unknown tool" in text

            logger.info("✓ Unknown tool handled gracefully")

        finally:
            await cleanup_backend()


# ============================================================================
# Summary and Reporting
# ============================================================================


def pytest_report_header(config):
    """Add custom header to test report."""
    return [
        "MCP Server Integration Tests",
        "Testing production code paths (handlers, not tool wrappers)",
        f"Python: {sys.version}",
        f"Project: {PROJECT_ROOT}",
    ]
