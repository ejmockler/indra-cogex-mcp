"""
Subnetwork

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
    """Handle subnetwork extraction - Tool 3."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "direct":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: direct mode requires at least 2 genes"
                )]
            result = await _extract_direct(args)
        elif mode == "mediated":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: mediated mode requires at least 2 genes"
                )]
            result = await _extract_mediated(args)
        elif mode == "shared_upstream":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: shared_upstream mode requires at least 2 genes"
                )]
            result = await _extract_shared_upstream(args)
        elif mode == "shared_downstream":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: shared_downstream mode requires at least 2 genes"
                )]
            result = await _extract_shared_downstream(args)
        elif mode == "source_to_targets":
            if not args.get("source_gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: source_to_targets mode requires source_gene parameter"
                )]
            result = await _extract_source_to_targets(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown subnetwork mode '{mode}'"
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


# Tool 3 Mode Handlers
async def _extract_direct(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: direct - Extract direct mechanistic edges between specified genes."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    adapter = await get_adapter()
    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "statement_types": args.get("statement_types"),
        "min_evidence": args.get("min_evidence_count", 1),
        "min_belief": args.get("min_belief_score", 0.0),
        "max_statements": args.get("max_statements", 100),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }
    if args.get("tissue_filter"):
        query_params["tissue"] = args["tissue_filter"]
    if args.get("go_filter"):
        query_params["go_term"] = args["go_filter"]

    stmt_data = await adapter.query("indra_subnetwork", **query_params)
    statements = _parse_subnetwork_statements(stmt_data, args.get("include_evidence", False))
    nodes = _extract_nodes_from_statements(statements, resolved_genes)
    statistics = _compute_network_statistics(nodes, statements)

    return {"nodes": nodes, "statements": statements, "statistics": statistics}


async def _extract_mediated(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: mediated - Find two-hop paths connecting genes through intermediates."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    adapter = await get_adapter()
    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "statement_types": args.get("statement_types"),
        "min_evidence": args.get("min_evidence_count", 1),
        "min_belief": args.get("min_belief_score", 0.0),
        "max_statements": args.get("max_statements", 100),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }
    if args.get("tissue_filter"):
        query_params["tissue"] = args["tissue_filter"]
    if args.get("go_filter"):
        query_params["go_term"] = args["go_filter"]

    stmt_data = await adapter.query("indra_mediated_subnetwork", **query_params)
    statements = _parse_subnetwork_statements(stmt_data, args.get("include_evidence", False))
    nodes = _extract_nodes_from_statements(statements, resolved_genes)
    statistics = _compute_network_statistics(nodes, statements)

    return {"nodes": nodes, "statements": statements, "statistics": statistics, "note": "Paths shown are two-hop"}


async def _extract_shared_upstream(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: shared_upstream - Find shared regulators."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    return {
        "nodes": [{"name": g.name, "curie": g.curie, "namespace": g.namespace, "identifier": g.identifier} for g in resolved_genes],
        "statements": [],
        "statistics": {"node_count": len(resolved_genes), "edge_count": 0, "statement_types": {}, "avg_evidence_per_statement": 0.0, "avg_belief_score": 0.0},
        "note": "Shared upstream queries not yet implemented in backend",
    }


async def _extract_shared_downstream(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: shared_downstream - Find shared targets."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    return {
        "nodes": [{"name": g.name, "curie": g.curie, "namespace": g.namespace, "identifier": g.identifier} for g in resolved_genes],
        "statements": [],
        "statistics": {"node_count": len(resolved_genes), "edge_count": 0, "statement_types": {}, "avg_evidence_per_statement": 0.0, "avg_belief_score": 0.0},
        "note": "Shared downstream queries not yet implemented in backend",
    }


async def _extract_source_to_targets(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: source_to_targets - Find all downstream targets of a source gene."""
    source_gene = args["source_gene"]
    resolver = get_resolver()
    source = await resolver.resolve_gene(source_gene)

    target_genes = []
    if args.get("target_genes"):
        for gene in args["target_genes"]:
            resolved = await resolver.resolve_gene(gene)
            target_genes.append(resolved)

    adapter = await get_adapter()
    query_params = {
        "source_gene_id": source.curie,
        "statement_types": args.get("statement_types"),
        "min_evidence": args.get("min_evidence_count", 1),
        "min_belief": args.get("min_belief_score", 0.0),
        "max_statements": args.get("max_statements", 100),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }
    if target_genes:
        query_params["target_gene_ids"] = [g.curie for g in target_genes]
    if args.get("tissue_filter"):
        query_params["tissue"] = args["tissue_filter"]
    if args.get("go_filter"):
        query_params["go_term"] = args["go_filter"]

    stmt_data = await adapter.query("source_target_analysis", **query_params)
    statements = _parse_subnetwork_statements(stmt_data, args.get("include_evidence", False))
    all_resolved = [source] + target_genes
    nodes = _extract_nodes_from_statements(statements, all_resolved)
    statistics = _compute_network_statistics(nodes, statements)

    return {
        "source_gene": {"name": source.name, "curie": source.curie, "namespace": source.namespace, "identifier": source.identifier},
        "nodes": nodes,
        "statements": statements,
        "statistics": statistics,
    }


def _parse_subnetwork_statements(data: dict[str, Any], include_evidence: bool = False) -> list[dict[str, Any]]:
    """Parse INDRA statements from backend response."""
    if not data.get("success") or not data.get("statements"):
        return []

    statements = []
    for record in data["statements"]:
        stmt = {
            "stmt_hash": record.get("hash", ""),
            "stmt_type": record.get("type", "Unknown"),
            "subject": {
                "name": record.get("subj_name", "Unknown"),
                "curie": record.get("subj_id", "unknown:unknown"),
                "namespace": record.get("subj_namespace", "unknown"),
                "identifier": record.get("subj_identifier", "unknown"),
            },
            "object": {
                "name": record.get("obj_name", "Unknown"),
                "curie": record.get("obj_id", "unknown:unknown"),
                "namespace": record.get("obj_namespace", "unknown"),
                "identifier": record.get("obj_identifier", "unknown"),
            },
            "residue": record.get("residue"),
            "position": record.get("position"),
            "evidence_count": record.get("evidence_count", 0),
            "belief_score": record.get("belief", 0.0),
            "sources": record.get("sources", []),
        }
        if include_evidence:
            stmt["evidence"] = record.get("evidence")
        statements.append(stmt)

    return statements


def _extract_nodes_from_statements(statements: list[dict[str, Any]], resolved_genes: list) -> list[dict[str, Any]]:
    """Extract unique nodes from statements and resolved genes."""
    nodes_dict: dict[str, dict[str, Any]] = {}
    for gene in resolved_genes:
        nodes_dict[gene.curie] = {"name": gene.name, "curie": gene.curie, "namespace": gene.namespace, "identifier": gene.identifier}

    for stmt in statements:
        if stmt["subject"]["curie"] not in nodes_dict:
            nodes_dict[stmt["subject"]["curie"]] = stmt["subject"]
        if stmt["object"]["curie"] not in nodes_dict:
            nodes_dict[stmt["object"]["curie"]] = stmt["object"]

    return list(nodes_dict.values())


def _compute_network_statistics(nodes: list[dict[str, Any]], statements: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute network-level statistics."""
    stmt_types: dict[str, int] = {}
    total_evidence = 0
    total_belief = 0.0

    for stmt in statements:
        stmt_type = stmt["stmt_type"]
        stmt_types[stmt_type] = stmt_types.get(stmt_type, 0) + 1
        total_evidence += stmt["evidence_count"]
        total_belief += stmt["belief_score"]

    return {
        "node_count": len(nodes),
        "edge_count": len(statements),
        "statement_types": stmt_types,
        "avg_evidence_per_statement": total_evidence / len(statements) if statements else 0.0,
        "avg_belief_score": total_belief / len(statements) if statements else 0.0,
    }


async def _handle_enrichment_analysis(args: dict[str, Any]) -> list[types.TextContent]:
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


