"""
Literature

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


# Tool 9: Literature Query
# ============================================================================

async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle literature query - Tool 9."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_statements_for_pmid":
            if not args.get("pmid"):
                return [types.TextContent(
                    type="text",
                    text="Error: pmid parameter required for get_statements_for_pmid mode"
                )]
            result = await _get_statements_for_pmid(args)
        elif mode == "get_evidence_for_statement":
            if not args.get("statement_hash"):
                return [types.TextContent(
                    type="text",
                    text="Error: statement_hash parameter required for get_evidence_for_statement mode"
                )]
            result = await _get_evidence_for_statement(args)
        elif mode == "search_by_mesh":
            if not args.get("mesh_terms") or len(args.get("mesh_terms", [])) == 0:
                return [types.TextContent(
                    type="text",
                    text="Error: mesh_terms parameter required for search_by_mesh mode"
                )]
            result = await _search_by_mesh(args)
        elif mode == "get_statements_by_hashes":
            if not args.get("statement_hashes") or len(args.get("statement_hashes", [])) == 0:
                return [types.TextContent(
                    type="text",
                    text="Error: statement_hashes parameter required for get_statements_by_hashes mode"
                )]
            result = await _get_statements_by_hashes(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown literature query mode '{mode}'"
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
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 9 Mode Handlers
async def _get_statements_for_pmid(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_statements_for_pmid - Retrieve INDRA statements from a specific PubMed publication."""
    pmid = args["pmid"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    include_evidence_text = args.get("include_evidence_text", True)
    max_evidence_per_statement = args.get("max_evidence_per_statement", 5)

    adapter = await get_adapter()
    query_params = {
        "pmid": pmid,
        "limit": limit,
        "offset": offset,
        "include_evidence": include_evidence_text,
        "max_evidence": max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    stmt_data = await adapter.query("get_statements_for_paper", **query_params)

    # Parse statements
    statements = _parse_literature_statements(stmt_data, include_evidence_text)

    # Build pagination
    total_count = stmt_data.get("total_count", len(statements))
    pagination = _build_literature_pagination(
        total_count=total_count,
        count=len(statements),
        offset=offset,
        limit=limit,
    )

    return {
        "pmid": pmid,
        "statements": statements,
        "pagination": pagination,
    }


async def _get_evidence_for_statement(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_evidence_for_statement - Retrieve evidence text snippets for a specific INDRA statement."""
    statement_hash = args["statement_hash"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    max_evidence_per_statement = args.get("max_evidence_per_statement", 5)

    adapter = await get_adapter()
    query_params = {
        "stmt_hash": statement_hash,
        "limit": limit,
        "offset": offset,
        "max_evidence": max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    evidence_data = await adapter.query("get_evidences_for_stmt_hash", **query_params)

    # Parse evidence
    evidence_list = _parse_literature_evidence(evidence_data)

    # Build pagination
    total_count = evidence_data.get("total_count", len(evidence_list))
    pagination = _build_literature_pagination(
        total_count=total_count,
        count=len(evidence_list),
        offset=offset,
        limit=limit,
    )

    return {
        "statement_hash": statement_hash,
        "evidence": evidence_list,
        "pagination": pagination,
    }


async def _search_by_mesh(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: search_by_mesh - Search PubMed publications by MeSH terms."""
    mesh_terms = args["mesh_terms"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    query_params = {
        "mesh_terms": mesh_terms,
        "limit": limit,
        "offset": offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    pub_data = await adapter.query("get_evidence_for_mesh", **query_params)

    # Parse publications
    publications = _parse_literature_publications(pub_data)

    # Build pagination
    total_count = pub_data.get("total_count", len(publications))
    pagination = _build_literature_pagination(
        total_count=total_count,
        count=len(publications),
        offset=offset,
        limit=limit,
    )

    return {
        "mesh_terms": mesh_terms,
        "publications": publications,
        "pagination": pagination,
    }


async def _get_statements_by_hashes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_statements_by_hashes - Batch retrieve INDRA statements by their hashes."""
    statement_hashes = args["statement_hashes"]
    include_evidence_text = args.get("include_evidence_text", True)
    max_evidence_per_statement = args.get("max_evidence_per_statement", 5)

    adapter = await get_adapter()
    query_params = {
        "stmt_hashes": statement_hashes,
        "include_evidence": include_evidence_text,
        "max_evidence": max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    stmt_data = await adapter.query("get_stmts_for_stmt_hashes", **query_params)

    # Parse statements
    statements = _parse_literature_statements(stmt_data, include_evidence_text)

    # Build pagination (batch retrieval doesn't use offset/limit)
    pagination = _build_literature_pagination(
        total_count=len(statements),
        count=len(statements),
        offset=0,
        limit=len(statements),
    )

    return {
        "statements": statements,
        "pagination": pagination,
    }


# Data parsing helpers for Tool 9
def _parse_literature_statements(data: dict[str, Any], include_evidence: bool = False) -> list[dict[str, Any]]:
    """Parse INDRA statements from backend response."""
    if not data.get("success") or not data.get("statements"):
        return []

    statements = []
    for record in data["statements"]:
        # Parse evidence if requested
        evidence = None
        if include_evidence and record.get("evidence"):
            evidence = record["evidence"]

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
            "evidence": evidence,
        }
        statements.append(stmt)

    return statements


def _parse_literature_evidence(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse evidence snippets from backend response."""
    if not data.get("success") or not data.get("evidence"):
        return []

    evidence_list = []
    for record in data["evidence"]:
        evidence = {
            "text": record.get("text", ""),
            "pmid": record.get("pmid"),
            "source_api": record.get("source_api", "unknown"),
            "annotations": record.get("annotations"),
        }
        evidence_list.append(evidence)

    return evidence_list


def _parse_literature_publications(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse PubMed publications from backend response."""
    if not data.get("success") or not data.get("publications"):
        return []

    publications = []
    for record in data["publications"]:
        pmid = record.get("pmid", "")
        pub = {
            "pmid": pmid,
            "title": record.get("title", ""),
            "authors": record.get("authors", []),
            "journal": record.get("journal", ""),
            "year": record.get("year", 0),
            "abstract": record.get("abstract"),
            "mesh_terms": record.get("mesh_terms", []),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
        publications.append(pub)

    return publications


def _build_literature_pagination(total_count: int, count: int, offset: int, limit: int) -> dict[str, Any]:
    """Build pagination metadata."""
    has_more = (offset + count) < total_count
    next_offset = offset + count if has_more else None

    return {
        "total_count": total_count,
        "count": count,
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": next_offset,
    }

async def _handle_variants_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle variants query - Tool 10."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_for_gene":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_for_gene mode"
                )]
            result = await _get_variants_for_gene(args)
        elif mode == "get_for_disease":
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for get_for_disease mode"
                )]
            result = await _get_variants_for_disease(args)
        elif mode == "get_for_phenotype":
            if not args.get("phenotype"):
                return [types.TextContent(
                    type="text",
                    text="Error: phenotype parameter required for get_for_phenotype mode"
                )]
            result = await _get_variants_for_phenotype(args)
        elif mode == "variant_to_genes":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for variant_to_genes mode"
                )]
            result = await _variant_to_genes(args)
        elif mode == "variant_to_phenotypes":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for variant_to_phenotypes mode"
                )]
            result = await _variant_to_phenotypes(args)
        elif mode == "check_association":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for check_association mode"
                )]
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for check_association mode"
                )]
            result = await _check_variant_association(args)
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


