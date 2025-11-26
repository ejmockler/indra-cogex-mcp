"""
Kinase

Extracted from monolithic server.py
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    ENRICHMENT_TIMEOUT,
    STANDARD_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle kinase enrichment - Tool 15."""
    try:
        # Validate phosphosites
        phosphosites = args.get("phosphosites", [])
        if not phosphosites:
            return [types.TextContent(
                type="text",
                text="Error: phosphosites parameter is required and cannot be empty"
            )]

        # Validate phosphosite format
        pattern = re.compile(r"^[A-Z0-9]+_[STY]\d+$", re.IGNORECASE)
        invalid_sites = [site for site in phosphosites if not pattern.match(site)]
        if invalid_sites:
            return [types.TextContent(
                type="text",
                text=f"Error: Invalid phosphosite format: {', '.join(invalid_sites[:5])}. "
                     f"Expected format: GENE_S123 (serine), GENE_T456 (threonine), or GENE_Y789 (tyrosine)"
            )]

        # Count unique genes in phosphosites
        unique_genes = set(site.split("_")[0] for site in phosphosites)

        # Prepare background phosphosites if provided
        background_sites = args.get("background")
        if background_sites:
            invalid_bg = [site for site in background_sites if not pattern.match(site)]
            if invalid_bg:
                return [types.TextContent(
                    type="text",
                    text=f"Error: Invalid background phosphosite format: {', '.join(invalid_bg[:5])}"
                )]

        # Query backend
        adapter = await get_adapter()

        query_params = {
            "phosphosites": phosphosites,
            "alpha": args.get("alpha", 0.05),
            "correction_method": args.get("correction_method", "fdr_bh"),
            "timeout": ENRICHMENT_TIMEOUT,
        }

        if background_sites:
            query_params["background"] = background_sites

        enrichment_data = await adapter.query("kinase_analysis", **query_params)

        # Parse results
        results = _parse_kinase_results(enrichment_data)
        statistics = _compute_kinase_statistics(results, args, len(unique_genes))

        # Build response
        response_data = {
            "results": [r for r in results],
            "statistics": statistics,
            "total_phosphosites": len(phosphosites),
            "unique_genes": len(unique_genes),
        }

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=response_data,
            format_type=args.get("response_format", "markdown"),
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


def _parse_kinase_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse kinase enrichment results from backend response."""
    if not data.get("success") or not data.get("results"):
        return []

    results = []
    for record in data["results"]:
        # Parse kinase entity
        kinase = {
            "name": record.get("kinase_name", "Unknown"),
            "curie": record.get("kinase_id", "unknown:unknown"),
            "namespace": record.get("kinase_namespace", "hgnc"),
            "identifier": record.get("kinase_identifier", "unknown"),
        }

        # Determine confidence level based on substrate count and evidence
        substrate_count = record.get("substrate_count", 0)
        total_substrates = record.get("total_substrates", 0)
        p_value = record.get("adjusted_p_value", 1.0)

        # Confidence heuristics:
        # - high: 5+ substrates, p < 0.01, or >20% of known substrates
        # - medium: 3-4 substrates, p < 0.05
        # - low: 1-2 substrates
        if (
            substrate_count >= 5
            or p_value < 0.01
            or (total_substrates > 0 and substrate_count / total_substrates > 0.2)
        ):
            confidence = "high"
        elif substrate_count >= 3 and p_value < 0.05:
            confidence = "medium"
        else:
            confidence = "low"

        result = {
            "kinase": kinase,
            "p_value": record.get("p_value", 1.0),
            "adjusted_p_value": record.get("adjusted_p_value", 1.0),
            "substrate_count": substrate_count,
            "total_substrates": total_substrates,
            "phosphosites": record.get("phosphosites", []),
            "prediction_confidence": record.get("confidence", confidence),
        }

        results.append(result)

    # Sort by adjusted p-value (most significant first)
    results.sort(key=lambda x: x["adjusted_p_value"])

    return results


def _compute_kinase_statistics(
    results: list[dict[str, Any]],
    args: dict[str, Any],
    total_genes: int,
) -> dict[str, Any]:
    """Compute overall kinase enrichment statistics."""
    # Count significant results
    alpha = args.get("alpha", 0.05)
    significant_results = sum(1 for r in results if r["adjusted_p_value"] <= alpha)

    return {
        "total_results": len(results),
        "significant_results": significant_results,
        "total_genes_analyzed": total_genes,
        "correction_method": args.get("correction_method", "fdr_bh"),
        "alpha": alpha,
    }


