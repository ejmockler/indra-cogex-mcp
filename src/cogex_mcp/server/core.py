#!/usr/bin/env python3
"""
INDRA CoGEx MCP Server - Core Infrastructure

Contains:
- Server initialization
- Tool listing handler
- Tool call router
- Backend lifecycle management
"""

import asyncio
import logging
import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from cogex_mcp.clients.adapter import close_adapter, get_adapter
from cogex_mcp.config import settings
from cogex_mcp.services.cache import get_cache

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if settings.log_format == "text"
    else '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)

# Initialize MCP server
server = Server("cogex_mcp")

# Global state
_adapter = None
_cache = None


async def initialize_backend():
    """Initialize backend connections and services."""
    global _adapter, _cache

    logger.info("🚀 Starting INDRA CoGEx MCP Server (Modular)")
    logger.info(
        f"Configuration: primary_backend={settings.has_neo4j_config}, "
        f"fallback={settings.has_rest_fallback}"
    )

    # Initialize client adapter
    _adapter = await get_adapter()
    logger.info("✓ Client adapter initialized")

    # Initialize cache
    _cache = get_cache()
    logger.info(
        f"✓ Cache initialized: max_size={_cache.max_size}, "
        f"ttl={_cache.ttl_seconds}s, enabled={_cache.enabled}"
    )

    # Get adapter status
    status = _adapter.get_status()
    logger.info(f"Backend status: {status}")
    logger.info("✓ Server initialization complete")


async def cleanup_backend():
    """Cleanup backend connections."""
    logger.info("🛑 Shutting down INDRA CoGEx MCP Server")

    if _cache and _cache.enabled:
        stats = _cache.get_stats()
        logger.info(f"Final cache stats: {stats}")

    await close_adapter()
    logger.info("✓ Connections closed")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List all available MCP tools.

    Tool definitions are in tools_registry module.
    Handler implementations are in server/handlers/.
    """
    from cogex_mcp.server.tools_registry import get_all_tools

    return get_all_tools()


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """
    Route tool calls to appropriate handler implementations.

    Args:
        name: Tool name (e.g., "query_disease_or_phenotype")
        arguments: Tool-specific parameters

    Returns:
        List of text content responses

    Raises:
        ValueError: If tool name is unknown
    """
    # Import handlers dynamically
    from cogex_mcp.server.handlers import (
        gilda,
        disease_phenotype,
        gene_feature,
        subnetwork,
        enrichment,
        drug_effect,
        pathway,
        cell_line,
        clinical_trials,
        literature,
        variants,
        identifier,
        relationship,
        ontology,
        cell_markers,
        kinase,
        protein_function,
    )

    try:
        # Route to appropriate handler
        if name == "ground_biomedical_term":
            return await gilda.handle(arguments)
        elif name == "query_disease_or_phenotype":
            return await disease_phenotype.handle(arguments)
        elif name == "query_gene_or_feature":
            return await gene_feature.handle(arguments)
        elif name == "extract_subnetwork":
            return await subnetwork.handle(arguments)
        elif name == "enrichment_analysis":
            return await enrichment.handle(arguments)
        elif name == "query_drug_or_effect":
            return await drug_effect.handle(arguments)
        elif name == "query_pathway":
            return await pathway.handle(arguments)
        elif name == "query_cell_line":
            return await cell_line.handle(arguments)
        elif name == "query_clinical_trials":
            return await clinical_trials.handle(arguments)
        elif name == "query_literature":
            return await literature.handle(arguments)
        elif name == "query_variants":
            return await variants.handle(arguments)
        elif name == "resolve_identifiers":
            return await identifier.handle(arguments)
        elif name == "check_relationship":
            return await relationship.handle(arguments)
        elif name == "get_ontology_hierarchy":
            return await ontology.handle(arguments)
        elif name == "query_cell_markers":
            return await cell_markers.handle(arguments)
        elif name == "analyze_kinase_enrichment":
            return await kinase.handle(arguments)
        elif name == "query_protein_functions":
            return await protein_function.handle(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Tool error in {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("INDRA CoGEx MCP Server (Modular) v1.0.0 - All 17 Tools (16 + GILDA)")
    logger.info("=" * 80)
    logger.info("Transport: stdio")
    logger.info(f"Debug mode: {settings.debug_mode}")
    logger.info(f"Character limit: {settings.character_limit:,}")
    logger.info("=" * 80)

    try:
        # Initialize backend
        await initialize_backend()

        # Run server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="cogex_mcp",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await cleanup_backend()


if __name__ == "__main__":
    asyncio.run(main())
