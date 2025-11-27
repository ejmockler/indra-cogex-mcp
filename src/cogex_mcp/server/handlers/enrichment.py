"""
Enrichment

Extracted from monolithic server.py
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver, EntityResolutionError
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    ENRICHMENT_TIMEOUT,
    STANDARD_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle enrichment analysis - Tool 4."""
    try:
        analysis_type = args.get("analysis_type")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on analysis type
        if analysis_type == "discrete":
            result = await _analyze_discrete(args)
        elif analysis_type == "continuous":
            result = await _analyze_continuous(args)
        elif analysis_type == "signed":
            result = await _analyze_signed(args)
        elif analysis_type == "metabolite":
            result = await _analyze_metabolite(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown analysis type '{analysis_type}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 4 Mode Handlers
async def _analyze_discrete(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: discrete - Overrepresentation analysis using Fisher's exact test."""
    if not args.get("gene_list"):
        raise ValueError("gene_list parameter required for discrete analysis")

    # Resolve gene identifiers
    resolver = get_resolver()
    resolved_genes = []
    failed_genes = []

    for gene in args["gene_list"]:
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_genes.append(resolved)
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_genes:
        raise ValueError(f"No genes could be resolved. Failed: {', '.join(failed_genes)}")

    if failed_genes:
        logger.info(
            f"Proceeding with {len(resolved_genes)}/{len(args['gene_list'])} genes. "
            f"Failed: {', '.join(failed_genes[:5])}{'...' if len(failed_genes) > 5 else ''}"
        )

    # Optionally resolve background genes
    background_gene_ids = None
    if args.get("background_genes"):
        background_resolved = []
        for gene in args["background_genes"]:
            try:
                resolved = await resolver.resolve_gene(gene)
                background_resolved.append(resolved)
            except EntityResolutionError:
                pass
        background_gene_ids = [g.curie for g in background_resolved]

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "analysis_type": "discrete",
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    if background_gene_ids:
        query_params["background_genes"] = background_gene_ids

    # Add INDRA-specific parameters if applicable
    source = args.get("source", "go")
    if source in ["indra-upstream", "indra-downstream"]:
        query_params["min_evidence_count"] = args.get("min_evidence_count", 1)
        query_params["min_belief_score"] = args.get("min_belief_score", 0.0)

    enrichment_data = await adapter.query("enrichment_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="discrete")
    statistics = _compute_enrichment_statistics(results, args, len(resolved_genes))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "resolved_genes": len(resolved_genes),
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_continuous(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: continuous - Gene Set Enrichment Analysis (GSEA) with ranked gene list."""
    if not args.get("ranked_genes"):
        raise ValueError("ranked_genes parameter required for continuous analysis")

    # Resolve gene identifiers and preserve scores
    resolver = get_resolver()
    resolved_ranking: dict[str, float] = {}
    failed_genes = []

    for gene, score in args["ranked_genes"].items():
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_ranking[resolved.curie] = score
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_ranking:
        raise ValueError(f"No genes could be resolved. Failed: {', '.join(failed_genes)}")

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "ranked_genes": resolved_ranking,
        "analysis_type": "continuous",
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "permutations": args.get("permutations", 1000),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    # Add INDRA-specific parameters if applicable
    source = args.get("source", "go")
    if source in ["indra-upstream", "indra-downstream"]:
        query_params["min_evidence_count"] = args.get("min_evidence_count", 1)
        query_params["min_belief_score"] = args.get("min_belief_score", 0.0)

    enrichment_data = await adapter.query("enrichment_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="continuous")
    statistics = _compute_enrichment_statistics(results, args, len(resolved_ranking))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "resolved_genes": len(resolved_ranking),
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_signed(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: signed - Directional enrichment analysis (separate up/down regulation)."""
    if not args.get("ranked_genes"):
        raise ValueError("ranked_genes parameter required for signed analysis")

    # Resolve gene identifiers and preserve signed scores
    resolver = get_resolver()
    resolved_ranking: dict[str, float] = {}
    failed_genes = []

    for gene, score in args["ranked_genes"].items():
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_ranking[resolved.curie] = score
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_ranking:
        raise ValueError(f"No genes could be resolved. Failed: {', '.join(failed_genes)}")

    # Count up/down regulated genes
    upregulated = sum(1 for score in resolved_ranking.values() if score > 0)
    downregulated = sum(1 for score in resolved_ranking.values() if score < 0)

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "ranked_genes": resolved_ranking,
        "analysis_type": "signed",
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "permutations": args.get("permutations", 1000),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    # Add INDRA-specific parameters if applicable
    source = args.get("source", "go")
    if source in ["indra-upstream", "indra-downstream"]:
        query_params["min_evidence_count"] = args.get("min_evidence_count", 1)
        query_params["min_belief_score"] = args.get("min_belief_score", 0.0)

    enrichment_data = await adapter.query("enrichment_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="signed")
    statistics = _compute_enrichment_statistics(results, args, len(resolved_ranking))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "resolved_genes": len(resolved_ranking),
        "upregulated_count": upregulated,
        "downregulated_count": downregulated,
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_metabolite(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: metabolite - Metabolite set enrichment analysis."""
    if not args.get("gene_list"):
        raise ValueError("gene_list parameter required for metabolite analysis")

    # For metabolite analysis, we don't resolve through gene resolver
    # Metabolites have their own identifier format (e.g., HMDB, ChEBI)
    # Pass them directly to backend
    metabolite_ids = args["gene_list"]

    # Optionally resolve background metabolites
    background_metabolite_ids = args.get("background_genes") if args.get("background_genes") else None

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "gene_ids": metabolite_ids,  # Backend expects gene_ids parameter
        "analysis_type": "metabolite",
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    if background_metabolite_ids:
        query_params["background_genes"] = background_metabolite_ids

    enrichment_data = await adapter.query("enrichment_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="metabolite")
    statistics = _compute_enrichment_statistics(results, args, len(metabolite_ids))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "total_metabolites": len(metabolite_ids),
    }


# Data parsing helpers for Tool 4
def _parse_enrichment_results(data: dict[str, Any], analysis_type: str) -> list[dict[str, Any]]:
    """Parse enrichment results from backend response."""
    if not data.get("success") or not data.get("results"):
        return []

    results = []
    for record in data["results"]:
        # Parse term entity
        term = {
            "name": record.get("term_name", "Unknown"),
            "curie": record.get("term_id", "unknown:unknown"),
            "namespace": record.get("term_namespace", "unknown"),
            "identifier": record.get("term_identifier", "unknown"),
        }

        # Build result object
        result_dict = {
            "term": term,
            "term_name": record.get("term_name", "Unknown"),
            "p_value": record.get("p_value", 1.0),
            "adjusted_p_value": record.get("adjusted_p_value", 1.0),
            "gene_count": record.get("gene_count", 0),
            "term_size": record.get("term_size", 0),
            "genes": record.get("genes", []),
            "background_count": record.get("background_count"),
        }

        # Add GSEA-specific fields for continuous/signed analysis
        if analysis_type in ["continuous", "signed"]:
            result_dict["enrichment_score"] = record.get("enrichment_score")
            result_dict["normalized_enrichment_score"] = record.get("normalized_enrichment_score")

        results.append(result_dict)

    return results


def _compute_enrichment_statistics(results: list[dict[str, Any]], args: dict[str, Any], total_genes: int) -> dict[str, Any]:
    """Compute overall enrichment statistics."""
    # Count significant results
    alpha = args.get("alpha", 0.05)
    significant_results = sum(1 for r in results if r.get("adjusted_p_value", 1.0) <= alpha)

    return {
        "total_results": len(results),
        "significant_results": significant_results,
        "total_genes_analyzed": total_genes,
        "correction_method": args.get("correction_method", "fdr_bh"),
        "alpha": alpha,
    }


def _parse_disease_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append({
            "disease": {
                "name": record.get("disease", "Unknown"),
                "curie": record.get("disease_id", "unknown:unknown"),
            },
            "score": record.get("score", 0.0),
            "evidence_count": record.get("evidence_count", 0),
        })

    return diseases


async def _handle_drug_effect_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle drug/effect query - Tool 5."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "drug_to_profile":
            if not args.get("drug"):
                return [types.TextContent(
                    type="text",
                    text="Error: drug parameter required for drug_to_profile mode"
                )]
            result = await _drug_to_profile(args)
        elif mode == "side_effect_to_drugs":
            if not args.get("side_effect"):
                return [types.TextContent(
                    type="text",
                    text="Error: side_effect parameter required for side_effect_to_drugs mode"
                )]
            result = await _side_effect_to_drugs(args)
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

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


