"""
INDRA CoGEx MCP Server - Modular Architecture

Main entry point for the MCP server.
Exports the main() function for running the server.
"""

from cogex_mcp.server.core import (
    main,
    server,
    initialize_backend,
    cleanup_backend,
    handle_list_tools,
    handle_call_tool,
)

__all__ = [
    "main",
    "server",
    "initialize_backend",
    "cleanup_backend",
    "handle_list_tools",
    "handle_call_tool",
]
