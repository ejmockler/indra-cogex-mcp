"""
Entry point for running the INDRA CoGEx MCP server as a module.

Usage:
    python -m cogex_mcp.server
"""

from cogex_mcp.server import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
