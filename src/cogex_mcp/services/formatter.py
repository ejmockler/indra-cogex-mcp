"""
Response formatting service.

Handles conversion between Markdown and JSON formats with:
- Intelligent truncation to character limits
- Human-readable vs machine-readable formatting
- Consistent field naming and structure
"""

import json
import logging
from datetime import datetime
from typing import Any

from cogex_mcp.constants import CHARACTER_LIMIT, TRUNCATION_MESSAGE, ResponseFormat
from cogex_mcp.schemas import EntityRef, PaginatedResponse

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Format responses in Markdown or JSON with intelligent truncation.

    Features:
    - Markdown: Human-readable with headers, lists, formatting
    - JSON: Machine-readable with complete metadata
    - Character limit enforcement with smart truncation
    - Consistent formatting across all tools
    """

    @staticmethod
    def format_response(
        data: Any,
        format_type: ResponseFormat,
        max_chars: int = CHARACTER_LIMIT,
    ) -> str:
        """
        Format data in requested format with character limit.

        Args:
            data: Data to format
            format_type: Output format (MARKDOWN or JSON)
            max_chars: Maximum character limit

        Returns:
            Formatted string
        """
        if format_type == ResponseFormat.JSON:
            result = ResponseFormatter._format_json(data)
        else:
            result = ResponseFormatter._format_markdown(data)

        # Enforce character limit
        if len(result) > max_chars:
            result = ResponseFormatter._truncate_intelligently(result, max_chars)
            result += TRUNCATION_MESSAGE.format(limit=max_chars)

        return result

    @staticmethod
    def _format_json(data: Any) -> str:
        """
        Format data as JSON.

        Args:
            data: Data to format

        Returns:
            JSON string
        """
        # Handle Pydantic models
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()

        return json.dumps(data, indent=2, default=ResponseFormatter._json_serializer)

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "dict"):
            return obj.dict()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return str(obj)

    @staticmethod
    def _format_markdown(data: Any) -> str:
        """
        Format data as Markdown.

        Args:
            data: Data to format

        Returns:
            Markdown string
        """
        # This is a simplified implementation
        # Real implementation would handle specific data types
        if isinstance(data, dict):
            return ResponseFormatter._dict_to_markdown(data)
        elif isinstance(data, list):
            return ResponseFormatter._list_to_markdown(data)
        else:
            return str(data)

    @staticmethod
    def _dict_to_markdown(data: dict[str, Any], level: int = 1) -> str:
        """Convert dictionary to Markdown."""
        lines = []

        for key, value in data.items():
            # Format key as header
            key_formatted = key.replace("_", " ").title()

            if isinstance(value, dict):
                lines.append(f"{'#' * level} {key_formatted}\n")
                lines.append(ResponseFormatter._dict_to_markdown(value, level + 1))
            elif isinstance(value, list):
                lines.append(f"{'#' * level} {key_formatted}\n")
                lines.append(ResponseFormatter._list_to_markdown(value))
            else:
                lines.append(f"**{key_formatted}**: {value}\n")

        return "\n".join(lines)

    @staticmethod
    def _list_to_markdown(data: list[Any]) -> str:
        """Convert list to Markdown."""
        if not data:
            return "_No items_\n"

        lines = []
        for item in data:
            if isinstance(item, dict):
                lines.append(ResponseFormatter._dict_to_markdown(item, 3))
            else:
                lines.append(f"- {item}")

        return "\n".join(lines)

    @staticmethod
    def _truncate_intelligently(text: str, max_chars: int) -> str:
        """
        Truncate text intelligently at natural breakpoints.

        Args:
            text: Text to truncate
            max_chars: Maximum characters

        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text

        # Try to truncate at paragraph break
        truncate_at = max_chars
        for break_point in ["\n\n", "\n", ". ", ", ", " "]:
            pos = text.rfind(break_point, 0, max_chars)
            if pos > max_chars * 0.8:  # At least 80% of limit
                truncate_at = pos
                break

        return text[:truncate_at]

    @staticmethod
    def format_entity_ref(entity: EntityRef) -> str:
        """Format entity reference for display."""
        return f"{entity.name} ({entity.curie})"

    @staticmethod
    def format_pagination(pagination: PaginatedResponse) -> str:
        """Format pagination info."""
        parts = [
            f"Showing {pagination.count} of {pagination.total_count} results",
            f"(offset {pagination.offset})",
        ]

        if pagination.has_more:
            parts.append(f"More available (next_offset: {pagination.next_offset})")

        return " ".join(parts)

    @staticmethod
    def format_gene_info_markdown(gene_data: dict[str, Any]) -> str:
        """
        Format gene information as Markdown.

        Args:
            gene_data: Gene data dictionary

        Returns:
            Formatted Markdown string
        """
        lines = [
            f"# {gene_data['name']} ({gene_data.get('curie', 'N/A')})",
            "",
        ]

        if gene_data.get("description"):
            lines.extend(["## Description", gene_data["description"], ""])

        if gene_data.get("synonyms"):
            lines.extend(
                [
                    "## Synonyms",
                    ", ".join(gene_data["synonyms"]),
                    "",
                ]
            )

        # Expression data
        if gene_data.get("expression"):
            lines.append("## Expression")
            for expr in gene_data["expression"]:
                tissue = expr.get("tissue", {})
                lines.append(
                    f"- **{tissue.get('name', 'Unknown')}**: "
                    f"{expr.get('confidence', 'unknown')} confidence "
                    f"({expr.get('evidence_count', 0)} evidences)"
                )
            lines.append("")

        # GO terms
        if gene_data.get("go_terms"):
            lines.append("## Gene Ontology")
            for go in gene_data["go_terms"]:
                term = go.get("go_term", {})
                lines.append(
                    f"- **{term.get('name', 'Unknown')}** ({go.get('aspect', 'unknown')}): "
                    f"{go.get('evidence_code', 'N/A')}"
                )
            lines.append("")

        # Pathways
        if gene_data.get("pathways"):
            lines.append("## Pathways")
            for pathway in gene_data["pathways"]:
                pw = pathway.get("pathway", {})
                lines.append(
                    f"- **{pw.get('name', 'Unknown')}** ({pathway.get('source', 'unknown')})"
                )
            lines.append("")

        # Diseases
        if gene_data.get("diseases"):
            lines.append("## Disease Associations")
            for disease in gene_data["diseases"]:
                dis = disease.get("disease", {})
                score = disease.get("score", 0.0)
                sources = ", ".join(disease.get("sources", []))
                lines.append(f"- **{dis.get('name', 'Unknown')}**: score={score:.3f} ({sources})")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_enrichment_results_markdown(results: list[dict[str, Any]]) -> str:
        """
        Format enrichment results as Markdown table.

        Args:
            results: List of enrichment results

        Returns:
            Formatted Markdown string
        """
        if not results:
            return "_No enriched terms found_"

        lines = [
            "# Enrichment Results",
            "",
            "| Term | P-value | Adj. P-value | Genes | Term Size |",
            "|------|---------|--------------|-------|-----------|",
        ]

        for result in results[:50]:  # Limit to top 50
            term = result.get("term_name", "Unknown")
            p_val = result.get("p_value", 1.0)
            adj_p = result.get("adjusted_p_value", 1.0)
            gene_count = result.get("gene_count", 0)
            term_size = result.get("term_size", 0)

            lines.append(f"| {term} | {p_val:.2e} | {adj_p:.2e} | {gene_count} | {term_size} |")

        if len(results) > 50:
            lines.append("")
            lines.append(f"_Showing top 50 of {len(results)} results_")

        return "\n".join(lines)


# Global formatter instance
_formatter: ResponseFormatter | None = None


def get_formatter() -> ResponseFormatter:
    """
    Get global formatter instance (singleton).

    Returns:
        ResponseFormatter instance
    """
    global _formatter

    if _formatter is None:
        _formatter = ResponseFormatter()

    return _formatter
