#!/usr/bin/env python3
"""
INDRA CoGEx MCP Server - Low-Level Implementation

Uses the low-level MCP SDK instead of FastMCP for better Claude Code compatibility.
"""

import asyncio
import json
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
from cogex_mcp.services.entity_resolver import get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.constants import CHARACTER_LIMIT, STANDARD_QUERY_TIMEOUT

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if settings.log_format == "text"
    else '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)

# Initialize server
server = Server("cogex_mcp")

# Global state
_adapter = None
_cache = None


async def initialize_backend():
    """Initialize backend connections and services."""
    global _adapter, _cache

    logger.info("🚀 Starting INDRA CoGEx MCP Server (Low-Level)")
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
    """List all available tools."""
    return [
        types.Tool(
            name="cogex_query_disease_or_phenotype",
            description="""Query diseases, phenotypes, and their mechanisms bidirectionally.

This tool supports 3 query modes for comprehensive disease-phenotype exploration:

**Mode 1: disease_to_mechanisms**
Get comprehensive disease profile including associated genes, genetic variants,
phenotypes, drug therapies, and clinical trials.

**Mode 2: phenotype_to_diseases**
Find diseases associated with a specific phenotype. Useful for differential
diagnosis and phenotype-based discovery.

**Mode 3: check_phenotype**
Boolean check: Does a specific disease exhibit a specific phenotype?

Examples:
- Get diabetes profile: mode="disease_to_mechanisms", disease="diabetes mellitus"
- Find diseases with seizures: mode="phenotype_to_diseases", phenotype="HP:0001250"
- Check if Alzheimer's has memory impairment: mode="check_phenotype",
  disease="Alzheimer disease", phenotype="memory impairment"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": [
                            "disease_to_mechanisms",
                            "phenotype_to_diseases",
                            "check_phenotype",
                        ],
                        "description": "Query mode",
                    },
                    "disease": {
                        "type": "string",
                        "description": "Disease name or CURIE (e.g., 'diabetes' or 'mondo:MONDO:0005015')",
                    },
                    "phenotype": {
                        "type": "string",
                        "description": "Phenotype term or CURIE (e.g., 'HP:0001250' or 'seizures')",
                    },
                    "include_genes": {
                        "type": "boolean",
                        "description": "Include associated genes (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_variants": {
                        "type": "boolean",
                        "description": "Include genetic variants (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_phenotypes": {
                        "type": "boolean",
                        "description": "Include phenotypes (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_drugs": {
                        "type": "boolean",
                        "description": "Include drug therapies (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_trials": {
                        "type": "boolean",
                        "description": "Include clinical trials (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "response_format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "description": "Output format: 'markdown' (human-readable) or 'json' (machine-readable)",
                        "default": "markdown",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (phenotype_to_diseases mode)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "minimum": 0,
                        "default": 0,
                    },
                },
                "required": ["mode"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle tool calls."""
    if name == "cogex_query_disease_or_phenotype":
        return await _handle_disease_phenotype_query(arguments)

    raise ValueError(f"Unknown tool: {name}")


async def _handle_disease_phenotype_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle disease/phenotype query."""
    try:
        mode = args.get("mode")
        disease = args.get("disease")
        phenotype = args.get("phenotype")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "disease_to_mechanisms":
            if not disease:
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for disease_to_mechanisms mode"
                )]

            result = await _disease_to_mechanisms(args)
        elif mode == "phenotype_to_diseases":
            if not phenotype:
                return [types.TextContent(
                    type="text",
                    text="Error: phenotype parameter required for phenotype_to_diseases mode"
                )]

            result = await _phenotype_to_diseases(args)
        elif mode == "check_phenotype":
            if not disease or not phenotype:
                return [types.TextContent(
                    type="text",
                    text="Error: both disease and phenotype parameters required for check_phenotype mode"
                )]

            result = await _check_phenotype(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: Unexpected error occurred. {str(e)}"
        )]


async def _disease_to_mechanisms(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive disease profile with all molecular mechanisms."""
    disease_input = args["disease"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    result = {
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        }
    }

    adapter = await get_adapter()

    # Fetch requested features
    if args.get("include_genes", True):
        gene_data = await adapter.query(
            "get_genes_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["genes"] = _parse_gene_associations(gene_data)

    if args.get("include_variants", True):
        variant_data = await adapter.query(
            "get_variants_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["variants"] = _parse_variant_associations(variant_data)

    if args.get("include_phenotypes", True):
        phenotype_data = await adapter.query(
            "get_phenotypes_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["phenotypes"] = _parse_phenotype_associations(phenotype_data)

    if args.get("include_drugs", True):
        drug_data = await adapter.query(
            "get_drugs_for_indication",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["drugs"] = _parse_drug_therapies(drug_data)

    if args.get("include_trials", True):
        trial_data = await adapter.query(
            "get_trials_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_clinical_trials(trial_data)

    return result


async def _phenotype_to_diseases(args: dict[str, Any]) -> dict[str, Any]:
    """Find diseases associated with a specific phenotype."""
    phenotype_id = args["phenotype"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    disease_data = await adapter.query(
        "get_diseases_for_phenotype",
        phenotype_id=phenotype_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    diseases = _parse_disease_list(disease_data)

    return {
        "diseases": diseases,
        "pagination": {
            "total_count": disease_data.get("total_count", len(diseases)),
            "count": len(diseases),
            "offset": offset,
            "limit": limit,
            "has_more": disease_data.get("total_count", len(diseases)) > offset + len(diseases),
        },
    }


async def _check_phenotype(args: dict[str, Any]) -> dict[str, Any]:
    """Boolean check: Does disease have specific phenotype?"""
    disease_input = args["disease"]
    phenotype_id = args["phenotype"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease_ref.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_phenotype = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_phenotype": has_phenotype,
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        },
        "phenotype": {
            "name": phenotype_id,
            "curie": phenotype_id if ":" in phenotype_id else f"unknown:{phenotype_id}",
        },
    }


# Data parsing helpers
def _parse_gene_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    associations = []
    for record in data["records"]:
        associations.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
            },
            "score": record.get("score", 0.0),
            "evidence_count": record.get("evidence_count", 0),
            "sources": record.get("sources", []),
        })

    return associations


def _parse_variant_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse variant-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variants.append({
            "variant": record.get("rsid", "unknown"),
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
            },
            "p_value": record.get("p_value"),
            "odds_ratio": record.get("odds_ratio"),
            "trait": record.get("trait"),
        })

    return variants


def _parse_phenotype_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease-phenotype associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append({
            "phenotype": {
                "name": record.get("phenotype", "Unknown"),
                "curie": record.get("phenotype_id", "unknown:unknown"),
            },
            "frequency": record.get("frequency"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return phenotypes


def _parse_drug_therapies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug therapy data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append({
            "drug": {
                "name": record.get("drug", "Unknown"),
                "curie": record.get("drug_id", "unknown:unknown"),
            },
            "indication_type": record.get("indication_type", "unknown"),
            "max_phase": record.get("max_phase"),
            "status": record.get("status"),
        })

    return drugs


def _parse_clinical_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trial data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append({
            "nct_id": nct_id,
            "title": record.get("title", "Unknown Trial"),
            "phase": record.get("phase"),
            "status": record.get("status", "unknown"),
            "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
        })

    return trials


def _parse_disease_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append({
            "name": record.get("disease", "Unknown"),
            "curie": record.get("disease_id", "unknown:unknown"),
            "description": record.get("description"),
        })

    return diseases


async def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("INDRA CoGEx MCP Server (Low-Level) v1.0.0")
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
