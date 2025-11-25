"""
INDRA CoGEx MCP Server

Production-grade Model Context Protocol server for INDRA CoGEx biomedical knowledge graph.

Provides 16 compositional, bidirectional tools covering 100/110 endpoints (91% coverage)
across 28+ biomedical databases.
"""

__version__ = "1.0.0"
__author__ = "INDRA CoGEx MCP Team"

from cogex_mcp.server import mcp

__all__ = ["mcp", "__version__"]
