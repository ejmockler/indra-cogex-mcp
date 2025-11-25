"""
Pagination service for consistent pagination across all tools.

Provides standard pagination metadata and helpers.
"""

from typing import Any

from cogex_mcp.schemas import PaginatedResponse


class PaginationService:
    """
    Service for handling pagination consistently.

    Creates standard pagination metadata for all paginated tools.
    """

    @staticmethod
    def paginate(
        items: list[Any],
        total_count: int,
        offset: int,
        limit: int,
    ) -> PaginatedResponse:
        """
        Create pagination metadata.

        Args:
            items: List of items in current page
            total_count: Total number of items available
            offset: Current offset
            limit: Maximum items per page

        Returns:
            PaginatedResponse with metadata
        """
        count = len(items)
        has_more = offset + count < total_count
        next_offset = offset + count if has_more else None

        return PaginatedResponse(
            total_count=total_count,
            count=count,
            offset=offset,
            limit=limit,
            has_more=has_more,
            next_offset=next_offset,
        )

    @staticmethod
    def slice_results(
        items: list[Any],
        offset: int,
        limit: int,
    ) -> list[Any]:
        """
        Slice list to pagination window.

        Args:
            items: Full list of items
            offset: Offset to start from
            limit: Maximum items to return

        Returns:
            Sliced list
        """
        return items[offset : offset + limit]


# Singleton instance
_pagination: PaginationService | None = None


def get_pagination() -> PaginationService:
    """Get global pagination service instance."""
    global _pagination
    if _pagination is None:
        _pagination = PaginationService()
    return _pagination
