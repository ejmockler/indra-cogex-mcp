"""
INDRA CoGEx MCP Server - Main Entry Point

FastMCP server exposing 16 bidirectional tools for biomedical knowledge graph queries.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from cogex_mcp.clients.adapter import close_adapter, get_adapter
from cogex_mcp.config import settings
from cogex_mcp.services.cache import get_cache

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if settings.log_format == "text"
    else '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
    stream=sys.stderr,  # Important: FastMCP uses stdout for protocol, stderr for logs
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """
    Lifespan context manager for server initialization and cleanup.

    Args:
        app: FastMCP application instance (required by FastMCP)

    Initializes:
    - Backend connections (Neo4j/REST)
    - Caching service
    - Health monitoring

    Yields:
        dict: Shared state available to all tools via Context
    """
    logger.info("🚀 Starting INDRA CoGEx MCP Server")
    logger.info(
        f"Configuration: primary_backend={settings.has_neo4j_config}, "
        f"fallback={settings.has_rest_fallback}"
    )

    try:
        # Initialize client adapter (Neo4j + REST)
        adapter = await get_adapter()
        logger.info("✓ Client adapter initialized")

        # Initialize cache
        cache = get_cache()
        logger.info(
            f"✓ Cache initialized: max_size={cache.max_size}, "
            f"ttl={cache.ttl_seconds}s, enabled={cache.enabled}"
        )

        # Get adapter status
        status = adapter.get_status()
        logger.info(f"Backend status: {status}")

        # Shared state for tools
        state = {
            "adapter": adapter,
            "cache": cache,
            "start_time": asyncio.get_event_loop().time(),
        }

        logger.info("✓ Server initialization complete")

        yield state

    except Exception as e:
        logger.error(f"Failed to initialize server: {e}", exc_info=True)
        raise

    finally:
        # Cleanup on shutdown
        logger.info("🛑 Shutting down INDRA CoGEx MCP Server")

        # Log final cache statistics
        if cache.enabled:
            stats = cache.get_stats()
            logger.info(f"Final cache stats: {stats}")

        # Close backend connections
        await close_adapter()
        logger.info("✓ Connections closed")


# Initialize FastMCP server
mcp = FastMCP(
    name=settings.mcp_server_name,
    lifespan=lifespan,
)

logger.info(f"FastMCP server '{settings.mcp_server_name}' created")


# ============================================================================
# Tool Imports and Registration
# ============================================================================
# Import tool implementations
# Tools are registered via @mcp.tool() decorators in their modules

try:
    # Priority 1: Core Discovery Tools
    from cogex_mcp.tools import (
        disease_phenotype,  # Tool 5
        drug_effect,  # Tool 4
        enrichment,  # Tool 3
        gene_feature,  # Tool 1
        subnetwork,  # Tool 2
    )

    logger.info("✓ Priority 1 tools imported (Tools 1-5 complete)")

    # Priority 2: Specialized Tools
    from cogex_mcp.tools import (
        cell_line,  # Tool 7
        clinical_trials,  # Tool 8
        literature,  # Tool 9
        pathway,  # Tool 6
        variants,  # Tool 10
    )

    logger.info("✓ Priority 2 tools imported (Tools 6-10 complete)")

    # Priority 3: Utilities & Advanced
    from cogex_mcp.tools import (
        cell_marker,  # Tool 14
        identifier,  # Tool 11
        kinase,  # Tool 15
        ontology,  # Tool 13
        protein_function,  # Tool 16
        relationship,  # Tool 12
    )

    logger.info("✓ Priority 3 tools imported (Tools 11-16 complete)")
    logger.info("✓ All 16 tools active (100% coverage - complete implementation)")

except ImportError as e:
    logger.warning(f"Some tools not yet implemented: {e}")


# ============================================================================
# Server Entry Point
# ============================================================================


def main() -> None:
    """
    Main entry point for the MCP server.

    Runs the server in stdio mode (default) or HTTP mode based on configuration.
    """
    logger.info("=" * 80)
    logger.info("INDRA CoGEx MCP Server v1.0.0")
    logger.info("=" * 80)
    logger.info(f"Transport: {settings.transport}")
    logger.info(f"Debug mode: {settings.debug_mode}")
    logger.info(f"Character limit: {settings.character_limit:,}")
    logger.info("=" * 80)

    try:
        if settings.transport == "http":
            # Streamable HTTP mode
            logger.info(f"Starting HTTP server on {settings.http_host}:{settings.http_port}")
            mcp.run(
                transport="http",
                host=settings.http_host,
                port=settings.http_port,
            )
        else:
            # stdio mode (default)
            logger.info("Starting in stdio mode")
            mcp.run()  # Default is stdio

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
