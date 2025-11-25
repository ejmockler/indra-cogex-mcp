"""
Tool 9: cogex_query_literature

Access PubMed literature and INDRA statement evidence.

Modes:
1. get_statements_for_pmid: PMID → INDRA statements from that paper
2. get_evidence_for_statement: Statement hash → evidence texts
3. search_by_mesh: MeSH terms → publications
4. get_statements_by_hashes: Batch retrieve statements by hashes
"""

import logging
from typing import Any

from mcp.server.fastmcp import Context

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    READONLY_ANNOTATIONS,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    EntityRef,
    Evidence,
    IndraStatement,
    LiteratureQuery,
    LiteratureQueryMode,
    PaginatedResponse,
    Publication,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.formatter import get_formatter

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_query_literature",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_query_literature(
    params: LiteratureQuery,
    ctx: Context,
) -> str:
    """
    Access PubMed literature and INDRA statement evidence.

    This tool provides access to scientific literature from PubMed and
    INDRA statement evidence, enabling literature-based queries and evidence
    retrieval for mechanistic statements.

    **Modes:**

    1. **get_statements_for_pmid**: Retrieve INDRA statements from a paper
       - Use when: "What statements come from PMID 12345678?"
       - Returns: INDRA statements extracted from that publication

    2. **get_evidence_for_statement**: Get evidence for a specific statement
       - Use when: "Show me evidence for this phosphorylation event"
       - Returns: Evidence text snippets supporting the statement

    3. **search_by_mesh**: Search publications by MeSH terms
       - Use when: "Papers about 'autophagy' and 'cancer'"
       - Returns: PubMed publications matching the MeSH terms

    4. **get_statements_by_hashes**: Batch retrieve statements by hashes
       - Use when: Need to fetch multiple statements at once
       - Returns: Complete statement details for provided hashes

    **Options:**
    - include_evidence_text: Include text snippets (default: True)
    - max_evidence_per_statement: Limit evidence per statement (1-20, default: 5)

    Args:
        params (LiteratureQuery): Query parameters including:
            - mode (LiteratureQueryMode): Query mode (required)
            - pmid (str): PubMed ID for get_statements_for_pmid
            - statement_hash (str): Statement hash for get_evidence_for_statement
            - mesh_terms (List[str]): MeSH terms for search_by_mesh
            - statement_hashes (List[str]): Hashes for get_statements_by_hashes
            - include_evidence_text (bool): Include evidence text (default: True)
            - max_evidence_per_statement (int): Max evidence (1-20, default: 5)
            - limit (int): Maximum results (1-100, default: 20)
            - offset (int): Pagination offset (default: 0)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Formatted literature data in requested format

        **Markdown format:**
        - Human-readable summaries
        - Statements with evidence snippets
        - Publication lists with links
        - Evidence text with PMIDs

        **JSON format:**
        ```
        # For get_statements_for_pmid / get_statements_by_hashes:
        {
            "statements": [
                {
                    "stmt_hash": "...",
                    "stmt_type": "Phosphorylation",
                    "subject": {...},
                    "object": {...},
                    "evidence_count": 12,
                    "belief_score": 0.95,
                    "sources": ["reach", "sparser"],
                    "evidence": [...]
                }
            ],
            "pagination": {...}
        }

        # For get_evidence_for_statement:
        {
            "statement_hash": "abc123...",
            "evidence": [
                {
                    "text": "...",
                    "pmid": "12345678",
                    "source_api": "reach",
                    "annotations": {...}
                }
            ],
            "pagination": {...}
        }

        # For search_by_mesh:
        {
            "publications": [
                {
                    "pmid": "12345678",
                    "title": "...",
                    "authors": ["Smith J", "Jones A"],
                    "journal": "Nature",
                    "year": 2023,
                    "abstract": "...",
                    "mesh_terms": ["autophagy", "cancer"],
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"
                }
            ],
            "pagination": {...}
        }
        ```

    Examples:
        - Statements from paper:
          mode="get_statements_for_pmid", pmid="12345678"

        - Evidence for statement:
          mode="get_evidence_for_statement", statement_hash="abc123..."

        - MeSH search:
          mode="search_by_mesh", mesh_terms=["autophagy", "cancer"]

        - Batch statement retrieval:
          mode="get_statements_by_hashes", statement_hashes=["hash1", "hash2"]

    Error Handling:
        - Returns actionable error messages for invalid PMIDs
        - Handles missing statements/evidence gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating parameters...")

        # Route to appropriate handler based on mode
        if params.mode == LiteratureQueryMode.GET_STATEMENTS_FOR_PMID:
            result = await _get_statements_for_pmid(params, ctx)
        elif params.mode == LiteratureQueryMode.GET_EVIDENCE_FOR_STATEMENT:
            result = await _get_evidence_for_statement(params, ctx)
        elif params.mode == LiteratureQueryMode.SEARCH_BY_MESH:
            result = await _search_by_mesh(params, ctx)
        elif params.mode == LiteratureQueryMode.GET_STATEMENTS_BY_HASHES:
            result = await _get_statements_by_hashes(params, ctx)
        else:
            return f"Error: Unknown literature query mode '{params.mode}'"

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Literature query complete")
        return response

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Mode Implementations
# ============================================================================


async def _get_statements_for_pmid(
    params: LiteratureQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_statements_for_pmid
    Retrieve INDRA statements extracted from a specific PubMed publication.
    """
    if not params.pmid:
        raise ValueError("get_statements_for_pmid mode requires pmid parameter")

    await ctx.report_progress(0.3, f"Querying statements for PMID {params.pmid}...")

    adapter = await get_adapter()

    query_params = {
        "pmid": params.pmid,
        "limit": params.limit,
        "offset": params.offset,
        "include_evidence": params.include_evidence_text,
        "max_evidence": params.max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    stmt_data = await adapter.query("get_statements_for_paper", **query_params)

    await ctx.report_progress(0.7, "Processing statements...")

    # Parse statements
    statements = _parse_statements(stmt_data, params.include_evidence_text)

    # Build pagination
    total_count = stmt_data.get("total_count", len(statements))
    pagination = _build_pagination(
        total_count=total_count,
        count=len(statements),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "pmid": params.pmid,
        "statements": [s.model_dump() for s in statements],
        "pagination": pagination.model_dump(),
    }


async def _get_evidence_for_statement(
    params: LiteratureQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_evidence_for_statement
    Retrieve evidence text snippets for a specific INDRA statement.
    """
    if not params.statement_hash:
        raise ValueError("get_evidence_for_statement mode requires statement_hash parameter")

    await ctx.report_progress(0.3, "Querying evidence for statement...")

    adapter = await get_adapter()

    query_params = {
        "stmt_hash": params.statement_hash,
        "limit": params.limit,
        "offset": params.offset,
        "max_evidence": params.max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    evidence_data = await adapter.query("get_evidences_for_stmt_hash", **query_params)

    await ctx.report_progress(0.7, "Processing evidence...")

    # Parse evidence
    evidence_list = _parse_evidence(evidence_data)

    # Build pagination
    total_count = evidence_data.get("total_count", len(evidence_list))
    pagination = _build_pagination(
        total_count=total_count,
        count=len(evidence_list),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "statement_hash": params.statement_hash,
        "evidence": [e.model_dump() for e in evidence_list],
        "pagination": pagination.model_dump(),
    }


async def _search_by_mesh(
    params: LiteratureQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: search_by_mesh
    Search PubMed publications by MeSH terms.
    """
    if not params.mesh_terms or len(params.mesh_terms) == 0:
        raise ValueError("search_by_mesh mode requires mesh_terms parameter")

    await ctx.report_progress(0.3, f"Searching {len(params.mesh_terms)} MeSH terms...")

    adapter = await get_adapter()

    query_params = {
        "mesh_terms": params.mesh_terms,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    pub_data = await adapter.query("get_evidence_for_mesh", **query_params)

    await ctx.report_progress(0.7, "Processing publications...")

    # Parse publications
    publications = _parse_publications(pub_data)

    # Build pagination
    total_count = pub_data.get("total_count", len(publications))
    pagination = _build_pagination(
        total_count=total_count,
        count=len(publications),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "mesh_terms": params.mesh_terms,
        "publications": [p.model_dump() for p in publications],
        "pagination": pagination.model_dump(),
    }


async def _get_statements_by_hashes(
    params: LiteratureQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_statements_by_hashes
    Batch retrieve INDRA statements by their hashes.
    """
    if not params.statement_hashes or len(params.statement_hashes) == 0:
        raise ValueError("get_statements_by_hashes mode requires statement_hashes parameter")

    await ctx.report_progress(0.3, f"Retrieving {len(params.statement_hashes)} statements...")

    adapter = await get_adapter()

    query_params = {
        "stmt_hashes": params.statement_hashes,
        "include_evidence": params.include_evidence_text,
        "max_evidence": params.max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    stmt_data = await adapter.query("get_stmts_for_stmt_hashes", **query_params)

    await ctx.report_progress(0.7, "Processing statements...")

    # Parse statements
    statements = _parse_statements(stmt_data, params.include_evidence_text)

    # Build pagination (batch retrieval doesn't use offset/limit)
    pagination = _build_pagination(
        total_count=len(statements),
        count=len(statements),
        offset=0,
        limit=len(statements),
    )

    return {
        "statements": [s.model_dump() for s in statements],
        "pagination": pagination.model_dump(),
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_statements(
    data: dict[str, Any],
    include_evidence: bool = False,
) -> list[IndraStatement]:
    """Parse INDRA statements from backend response."""
    if not data.get("success") or not data.get("statements"):
        return []

    statements = []
    for record in data["statements"]:
        # Parse evidence if requested
        evidence = None
        if include_evidence and record.get("evidence"):
            evidence = record["evidence"]

        stmt = IndraStatement(
            stmt_hash=record.get("hash", ""),
            stmt_type=record.get("type", "Unknown"),
            subject=EntityRef(
                name=record.get("subj_name", "Unknown"),
                curie=record.get("subj_id", "unknown:unknown"),
                namespace=record.get("subj_namespace", "unknown"),
                identifier=record.get("subj_identifier", "unknown"),
            ),
            object=EntityRef(
                name=record.get("obj_name", "Unknown"),
                curie=record.get("obj_id", "unknown:unknown"),
                namespace=record.get("obj_namespace", "unknown"),
                identifier=record.get("obj_identifier", "unknown"),
            ),
            residue=record.get("residue"),
            position=record.get("position"),
            evidence_count=record.get("evidence_count", 0),
            belief_score=record.get("belief", 0.0),
            sources=record.get("sources", []),
            evidence=evidence,
        )
        statements.append(stmt)

    return statements


def _parse_evidence(data: dict[str, Any]) -> list[Evidence]:
    """Parse evidence snippets from backend response."""
    if not data.get("success") or not data.get("evidence"):
        return []

    evidence_list = []
    for record in data["evidence"]:
        evidence = Evidence(
            text=record.get("text", ""),
            pmid=record.get("pmid"),
            source_api=record.get("source_api", "unknown"),
            annotations=record.get("annotations"),
        )
        evidence_list.append(evidence)

    return evidence_list


def _parse_publications(data: dict[str, Any]) -> list[Publication]:
    """Parse PubMed publications from backend response."""
    if not data.get("success") or not data.get("publications"):
        return []

    publications = []
    for record in data["publications"]:
        pmid = record.get("pmid", "")
        pub = Publication(
            pmid=pmid,
            title=record.get("title", ""),
            authors=record.get("authors", []),
            journal=record.get("journal", ""),
            year=record.get("year", 0),
            abstract=record.get("abstract"),
            mesh_terms=record.get("mesh_terms", []),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )
        publications.append(pub)

    return publications


def _build_pagination(
    total_count: int,
    count: int,
    offset: int,
    limit: int,
) -> PaginatedResponse:
    """Build pagination metadata."""
    has_more = (offset + count) < total_count
    next_offset = offset + count if has_more else None

    return PaginatedResponse(
        total_count=total_count,
        count=count,
        offset=offset,
        limit=limit,
        has_more=has_more,
        next_offset=next_offset,
    )


logger.info("✓ Tool 9 (cogex_query_literature) registered")
