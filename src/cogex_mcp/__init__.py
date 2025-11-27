"""
INDRA CoGEx MCP Server

Production-grade Model Context Protocol server for INDRA CoGEx biomedical knowledge graph.

Provides 16 compositional, bidirectional tools covering 100/110 endpoints (91% coverage)
across 28+ biomedical databases.
"""

__version__ = "1.0.0"
__author__ = "INDRA CoGEx MCP Team"

# Lazy import to avoid MCP dependency for standalone usage
def __getattr__(name):
    if name == "server":
        from cogex_mcp.server import server
        return server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["server", "__version__"]
