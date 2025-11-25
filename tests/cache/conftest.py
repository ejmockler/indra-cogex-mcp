"""
Cache test fixtures and utilities.

Provides fixtures for cache testing including:
- Isolated cache instances
- Test data generators
- Mock query adapters
"""

import asyncio
from typing import Any

import pytest

from cogex_mcp.services.cache import CacheService


@pytest.fixture
async def cache_service():
    """
    Create isolated cache service for testing.

    Returns:
        CacheService instance with test configuration
    """
    cache = CacheService(
        max_size=100,
        ttl_seconds=3600,
        enabled=True,
    )
    yield cache
    await cache.clear()


@pytest.fixture
async def small_cache():
    """
    Create small cache for eviction testing.

    Returns:
        CacheService with limited capacity
    """
    cache = CacheService(
        max_size=10,
        ttl_seconds=3600,
        enabled=True,
    )
    yield cache
    await cache.clear()


@pytest.fixture
async def short_ttl_cache():
    """
    Create cache with short TTL for expiration testing.

    Returns:
        CacheService with 5-second TTL
    """
    cache = CacheService(
        max_size=100,
        ttl_seconds=5,
        enabled=True,
    )
    yield cache
    await cache.clear()


@pytest.fixture
def known_entities():
    """
    Provide known-good test entities.

    Returns:
        Dictionary of test entities by type
    """
    return {
        "genes": ["TP53", "BRCA1", "EGFR", "MAPK1", "AKT1"],
        "drugs": ["imatinib", "aspirin", "pembrolizumab", "paclitaxel"],
        "diseases": ["diabetes", "alzheimer disease", "breast cancer"],
        "pathways": ["R-HSA-109581", "R-HSA-194315", "R-HSA-5663202"],
        "tissues": ["brain", "liver", "blood", "heart"],
    }


@pytest.fixture
async def mock_query_adapter(cache_service):
    """
    Create mock query adapter with cache integration.

    Returns:
        MockQueryAdapter instance
    """
    adapter = MockQueryAdapter(cache_service)
    return adapter


class MockQueryAdapter:
    """
    Mock query adapter for cache testing.

    Simulates tool queries with deterministic responses.
    """

    def __init__(self, cache: CacheService):
        """
        Initialize mock adapter.

        Args:
            cache: CacheService instance to use
        """
        self.cache = cache
        self.query_count = 0
        self.backend_calls = 0

    async def query_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute mock tool query with caching.

        Args:
            tool_name: Name of tool to query
            params: Query parameters

        Returns:
            Mock query results
        """
        self.query_count += 1

        # Create cache key
        cache_key = self.cache.make_key(tool_name, str(sorted(params.items())))

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Simulate backend call
        self.backend_calls += 1
        await asyncio.sleep(0.01)  # Simulate network latency

        # Generate mock response
        result = self._generate_mock_response(tool_name, params)

        # Cache result
        await self.cache.set(cache_key, result)

        return result

    def _generate_mock_response(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate deterministic mock response.

        Args:
            tool_name: Tool name
            params: Query parameters

        Returns:
            Mock response data
        """
        # Generate consistent response based on params
        if "gene" in params:
            gene = params["gene"]
            return {
                "gene": gene,
                "description": f"Mock data for {gene}",
                "pathways": [f"pathway_{i}" for i in range(5)],
                "interactions": [f"interaction_{i}" for i in range(10)],
            }
        elif "drug" in params:
            drug = params["drug"]
            return {
                "drug": drug,
                "targets": [f"target_{i}" for i in range(3)],
                "indications": [f"indication_{i}" for i in range(5)],
            }
        elif "pathway_id" in params:
            pathway = params["pathway_id"]
            return {
                "pathway_id": pathway,
                "genes": [f"gene_{i}" for i in range(20)],
                "description": f"Mock pathway {pathway}",
            }
        else:
            return {"data": "mock_response"}

    def get_metrics(self) -> dict[str, Any]:
        """
        Get adapter metrics.

        Returns:
            Dictionary of metrics
        """
        stats = self.cache.get_detailed_stats()
        return {
            "total_queries": self.query_count,
            "backend_calls": self.backend_calls,
            "cache_hits": stats["hits"],
            "cache_misses": stats["misses"],
            "cache_savings": (
                (self.query_count - self.backend_calls) / self.query_count * 100
                if self.query_count > 0
                else 0
            ),
        }


async def simulate_realistic_workload(
    adapter: MockQueryAdapter,
    duration: int = 60,
) -> float:
    """
    Simulate realistic query workload.

    Args:
        adapter: Query adapter to test
        duration: Duration in seconds

    Returns:
        Average hit rate achieved
    """
    import random
    import time

    # Query patterns with realistic distribution
    queries = [
        # Hot queries (80% of traffic)
        ("cogex_query_gene_or_feature", {"gene": "TP53"}),
        ("cogex_query_gene_or_feature", {"gene": "BRCA1"}),
        ("cogex_query_drug_or_effect", {"drug": "imatinib"}),
        ("cogex_query_pathway", {"pathway_id": "R-HSA-109581"}),
        # Warm queries (15% of traffic)
        ("cogex_query_gene_or_feature", {"gene": "EGFR"}),
        ("cogex_query_gene_or_feature", {"gene": "MAPK1"}),
        ("cogex_query_drug_or_effect", {"drug": "aspirin"}),
        # Cold queries (5% of traffic)
        ("cogex_query_gene_or_feature", {"gene": f"GENE{random.randint(1, 1000)}"}),
    ]

    # Weighted selection
    weights = [20, 20, 20, 20, 5, 5, 5, 5]

    start_time = time.time()
    query_count = 0

    while time.time() - start_time < duration:
        # Select query based on weights
        tool, params = random.choices(queries, weights=weights)[0]

        # Execute query
        await adapter.query_tool(tool, params)
        query_count += 1

        # Realistic query rate: ~10 queries/second
        await asyncio.sleep(0.1)

    # Calculate hit rate
    stats = adapter.cache.get_detailed_stats()
    return stats["hit_rate"]
