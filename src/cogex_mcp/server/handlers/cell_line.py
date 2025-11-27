"""
Cell Line

Extracted from monolithic server.py - Updated to use unified adapter pattern
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver, EntityResolutionError
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    STANDARD_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle cell line query - Tool 7."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Get adapter
        adapter = await get_adapter()

        # Execute unified cell_line_query
        result = await adapter.query(
            "cell_line_query",
            mode=mode,
            cell_line=args.get("cell_line"),
            gene=args.get("gene"),
            gene_id=args.get("gene"),  # Also accept gene_id
            include_mutations=args.get("include_mutations", True),
            include_copy_number=args.get("include_copy_number", False),
            include_dependencies=args.get("include_dependencies", False),
            include_expression=args.get("include_expression", False),
            limit=args.get("limit", 20),
            offset=args.get("offset", 0),
            timeout=STANDARD_QUERY_TIMEOUT,
        )

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
