"""
Client adapters for backend connectivity.

Provides unified interface to Neo4j and REST backends with automatic fallback.
"""

from cogex_mcp.clients.adapter import ClientAdapter

__all__ = ["ClientAdapter"]
