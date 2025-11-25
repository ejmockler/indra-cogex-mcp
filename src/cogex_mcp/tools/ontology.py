"""
Tool 13: cogex_get_ontology_hierarchy

Navigate ontology parent/child relationships with ASCII tree visualization.

Modes:
1. parents: Get parent/ancestor terms in ontology
2. children: Get child/descendant terms in ontology
3. both: Get both parents and children
"""

import logging
from typing import Any, Dict, List, Optional
from collections import deque

from mcp.server.fastmcp import Context

from cogex_mcp.server import mcp
from cogex_mcp.schemas import (
    HierarchyDirection,
    OntologyHierarchyQuery,
    OntologyTerm,
)
from cogex_mcp.constants import (
    INTERNAL_ANNOTATIONS,
    ResponseFormat,
    STANDARD_QUERY_TIMEOUT,
    CHARACTER_LIMIT,
)
from cogex_mcp.services.entity_resolver import get_resolver, EntityResolutionError
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.clients.adapter import get_adapter

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_get_ontology_hierarchy",
    annotations=INTERNAL_ANNOTATIONS,
)
async def cogex_get_ontology_hierarchy(
    params: OntologyHierarchyQuery,
    ctx: Context,
) -> str:
    """
    Navigate ontology hierarchies (GO, HPO, MONDO, etc.).

    This tool supports 3 query modes for exploring ontology relationships:

    **Parents Mode:**
    - parents: Get parent/ancestor terms moving up the ontology

    **Children Mode:**
    - children: Get child/descendant terms moving down the ontology

    **Both Directions:**
    - both: Get both parents and children in a single query

    Args:
        params (OntologyHierarchyQuery): Query parameters including:
            - term (str | tuple): Ontology term identifier (e.g., 'GO:0006915' or ('go', 'GO:0006915'))
            - direction (HierarchyDirection): Query direction (parents, children, both)
            - max_depth (int): Maximum levels to traverse (1-5, default 2)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **Markdown response:**
        ASCII tree visualization showing hierarchical relationships with indentation

        **JSON response:**
        {
            "root_term": { "name": "apoptotic process", "curie": "GO:0006915", ... },
            "parents": [{ "name": "programmed cell death", "depth": 1, ... }, ...],
            "children": [{ "name": "intrinsic apoptotic signaling", "depth": 1, ... }, ...],
            "hierarchy_tree": "ASCII tree string (markdown only)"
        }

    Examples:
        - Get parents of apoptosis:
          term="GO:0006915", direction="parents", max_depth=3

        - Get children of cellular process:
          term=("go", "GO:0009987"), direction="children", max_depth=2

        - Get full hierarchy:
          term="apoptosis", direction="both", max_depth=2

    Error Handling:
        - Returns actionable error messages for invalid identifiers
        - Suggests alternatives for ambiguous terms
        - Handles missing ontology terms gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating parameters...")

        # Route to appropriate handler based on direction
        if params.direction == HierarchyDirection.PARENTS:
            result = await _get_ontology_parents(params, ctx)
        elif params.direction == HierarchyDirection.CHILDREN:
            result = await _get_ontology_children(params, ctx)
        elif params.direction == HierarchyDirection.BOTH:
            result = await _get_ontology_hierarchy(params, ctx)
        else:
            return f"Error: Unknown direction '{params.direction}'"

        # Generate ASCII tree for markdown format
        if params.response_format == ResponseFormat.MARKDOWN:
            result["hierarchy_tree"] = _generate_ascii_tree(
                result.get("root_term"),
                result.get("parents", []),
                result.get("children", []),
                params.direction,
            )

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Query complete")
        return response

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return f"Error: {str(e)}"

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Mode Implementations
# ============================================================================


async def _get_ontology_parents(
    params: OntologyHierarchyQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: parents
    Get parent/ancestor terms in ontology.
    """
    await ctx.report_progress(0.2, "Resolving ontology term...")

    # Resolve ontology term
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    await ctx.report_progress(0.3, f"Fetching parents for {term.name}...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
    }

    parent_data = await adapter.query(
        "get_ontology_parents",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse parents
    parents = _parse_ontology_terms(parent_data)

    return {
        "root_term": term.model_dump(),
        "parents": parents,
        "children": None,
    }


async def _get_ontology_children(
    params: OntologyHierarchyQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: children
    Get child/descendant terms in ontology.
    """
    await ctx.report_progress(0.2, "Resolving ontology term...")

    # Resolve ontology term
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    await ctx.report_progress(0.3, f"Fetching children for {term.name}...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
    }

    child_data = await adapter.query(
        "get_ontology_children",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse children
    children = _parse_ontology_terms(child_data)

    return {
        "root_term": term.model_dump(),
        "parents": None,
        "children": children,
    }


async def _get_ontology_hierarchy(
    params: OntologyHierarchyQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: both
    Get both parents and children in a single query.
    """
    await ctx.report_progress(0.2, "Resolving ontology term...")

    # Resolve ontology term
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    await ctx.report_progress(0.3, f"Fetching full hierarchy for {term.name}...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
    }

    hierarchy_data = await adapter.query(
        "get_ontology_hierarchy",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse both parents and children
    parents = _parse_ontology_terms(hierarchy_data.get("parents", {}))
    children = _parse_ontology_terms(hierarchy_data.get("children", {}))

    return {
        "root_term": term.model_dump(),
        "parents": parents,
        "children": children,
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_ontology_terms(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse ontology terms from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    terms = []
    for record in data["records"]:
        terms.append({
            "name": record.get("name", record.get("term", "Unknown")),
            "curie": record.get("curie", record.get("term_id", "unknown:unknown")),
            "namespace": record.get("namespace", "unknown"),
            "definition": record.get("definition"),
            "depth": record.get("depth", 0),
            "relationship": record.get("relationship", "is_a"),
        })

    return terms


# ============================================================================
# ASCII Tree Generation
# ============================================================================


def _generate_ascii_tree(
    root_term: Optional[Dict[str, Any]],
    parents: Optional[List[Dict[str, Any]]],
    children: Optional[List[Dict[str, Any]]],
    direction: HierarchyDirection,
) -> str:
    """
    Generate ASCII tree visualization for markdown output.

    Args:
        root_term: Root ontology term
        parents: List of parent terms (with depth)
        children: List of child terms (with depth)
        direction: Query direction

    Returns:
        ASCII tree string with box-drawing characters
    """
    if not root_term:
        return "No hierarchy data available."

    lines = []

    # Build parent tree (bottom-up)
    if parents and direction in (HierarchyDirection.PARENTS, HierarchyDirection.BOTH):
        # Group parents by depth
        parents_by_depth = {}
        for parent in parents:
            depth = parent.get("depth", 1)
            if depth not in parents_by_depth:
                parents_by_depth[depth] = []
            parents_by_depth[depth].append(parent)

        # Sort depths in reverse (farthest first)
        sorted_depths = sorted(parents_by_depth.keys(), reverse=True)

        for depth in sorted_depths:
            indent = "  " * (depth - 1)
            for parent in parents_by_depth[depth]:
                rel = parent.get("relationship", "is_a")
                lines.append(f"{indent}├─ {parent['name']} ({parent['curie']}) [{rel}]")

    # Add root term
    lines.append(f"● {root_term['name']} ({root_term['curie']}) [ROOT]")

    # Build children tree (top-down)
    if children and direction in (HierarchyDirection.CHILDREN, HierarchyDirection.BOTH):
        # Group children by depth
        children_by_depth = {}
        for child in children:
            depth = child.get("depth", 1)
            if depth not in children_by_depth:
                children_by_depth[depth] = []
            children_by_depth[depth].append(child)

        # Sort depths in order (nearest first)
        sorted_depths = sorted(children_by_depth.keys())

        for depth in sorted_depths:
            indent = "  " * depth
            for i, child in enumerate(children_by_depth[depth]):
                rel = child.get("relationship", "is_a")
                # Use different symbol for last child
                is_last = i == len(children_by_depth[depth]) - 1 and depth == max(sorted_depths)
                symbol = "└─" if is_last else "├─"
                lines.append(f"{indent}{symbol} {child['name']} ({child['curie']}) [{rel}]")

    return "\n".join(lines)


logger.info("✓ Tool 13 (cogex_get_ontology_hierarchy) registered")
