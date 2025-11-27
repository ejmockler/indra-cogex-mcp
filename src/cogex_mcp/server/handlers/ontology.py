"""
Ontology

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
    """Handle ontology hierarchy - Tool 13."""
    try:
        # Parse params
        from cogex_mcp.schemas import OntologyHierarchyQuery, HierarchyDirection
        params = OntologyHierarchyQuery(**args)

        # Route to appropriate handler based on direction
        if params.direction == HierarchyDirection.PARENTS:
            result = await _get_ontology_parents(params)
        elif params.direction == HierarchyDirection.CHILDREN:
            result = await _get_ontology_children(params)
        elif params.direction == HierarchyDirection.BOTH:
            result = await _get_ontology_hierarchy(params)
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown direction '{params.direction}'")]

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

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Ontology Hierarchy Mode Implementations

async def _get_ontology_parents(params) -> dict[str, Any]:
    """Mode: parents - Get parent/ancestor terms in ontology."""
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    adapter = await get_adapter()

    # Build query parameters for ontology hierarchy query
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
        "direction": "parents",
    }

    # Execute via unified ontology query in neo4j_client
    result = await adapter.query(
        "ontology_query",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Transform result to expected format
    parents = result.get("parents", []) if result.get("success") else []

    return {
        "root_term": term.model_dump(),
        "parents": parents,
        "children": None,
    }


async def _get_ontology_children(params) -> dict[str, Any]:
    """Mode: children - Get child/descendant terms in ontology."""
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    adapter = await get_adapter()

    # Build query parameters for ontology hierarchy query
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
        "direction": "children",
    }

    # Execute via unified ontology query in neo4j_client
    result = await adapter.query(
        "ontology_query",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Transform result to expected format
    children = result.get("children", []) if result.get("success") else []

    return {
        "root_term": term.model_dump(),
        "parents": None,
        "children": children,
    }


async def _get_ontology_hierarchy(params) -> dict[str, Any]:
    """Mode: both - Get both parents and children in a single query."""
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    adapter = await get_adapter()

    # Build query parameters for ontology hierarchy query
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
        "direction": "both",
    }

    # Execute via unified ontology query in neo4j_client
    result = await adapter.query(
        "ontology_query",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Transform result to expected format
    parents = result.get("parents", []) if result.get("success") else []
    children = result.get("children", []) if result.get("success") else []

    return {
        "root_term": term.model_dump(),
        "parents": parents,
        "children": children,
    }


def _generate_ascii_tree(
    root_term: dict[str, Any] | None,
    parents: list[dict[str, Any]] | None,
    children: list[dict[str, Any]] | None,
    direction,
) -> str:
    """Generate ASCII tree visualization for markdown output."""
    if not root_term:
        return "No hierarchy data available."

    from cogex_mcp.schemas import HierarchyDirection
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


