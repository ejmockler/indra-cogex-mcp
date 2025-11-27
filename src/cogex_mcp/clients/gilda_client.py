"""GILDA API client for biomedical entity grounding."""

import httpx
import logging
from typing import Optional

from cogex_mcp.services.gilda_cache import GildaCache
from cogex_mcp.services.curie_normalizer import normalize_gilda_results


logger = logging.getLogger(__name__)


class GildaClient:
    """
    Client for GILDA (Grounding of biomedical named entities) API.

    Features:
    - Async HTTP client with timeout
    - File-based caching with LRU eviction
    - CURIE normalization for CoGEx compatibility
    - Graceful degradation on errors
    """

    BASE_URL = "http://grounding.indra.bio"
    DEFAULT_TIMEOUT = 5.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        cache: Optional[GildaCache] = None,
    ):
        """
        Initialize GILDA client.

        Args:
            base_url: GILDA API base URL (default: grounding.indra.bio)
            timeout: HTTP timeout in seconds
            cache: Cache instance (default: creates new GildaCache)
        """
        self.base_url = base_url or self.BASE_URL
        self.cache = cache or GildaCache()
        self.client = httpx.AsyncClient(timeout=timeout)

    async def ground(
        self,
        text: str,
        organism: str = "human",
        use_cache: bool = True,
    ) -> list[dict]:
        """
        Ground text to CURIEs using GILDA.

        Args:
            text: Text to ground (e.g., "diabetes", "ALS", "p53")
            organism: Filter to organism (default: "human")
            use_cache: Whether to use cache (default: True)

        Returns:
            List of grounding results with normalized CURIEs
            Format:
                [
                    {
                        "term": {
                            "db": "mesh",      # lowercase namespace
                            "id": "D000690",   # normalized ID
                            "text": "Amyotrophic Lateral Sclerosis",
                            "entry_name": "...",
                        },
                        "score": 0.85,
                        "match": {
                            "exact": False,
                            ...
                        }
                    },
                    ...
                ]
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(text)
            if cached is not None:
                logger.debug(f"GILDA cache hit: '{text}'")
                return cached

        # Call GILDA API
        try:
            response = await self.client.post(
                f"{self.base_url}/ground",
                json={"text": text, "organism": organism}
            )
            response.raise_for_status()
            results = response.json()

            # Normalize CURIEs for CoGEx compatibility
            results = normalize_gilda_results(results)

            # Cache results
            if use_cache:
                self.cache.set(text, results)

            logger.info(
                f"GILDA grounding: '{text}' → {len(results)} matches "
                f"(top score: {results[0]['score']:.3f})"
                if results else
                f"GILDA grounding: '{text}' → no matches"
            )

            return results

        except Exception as e:
            # Graceful degradation: return empty results for ANY error
            # This includes: network errors, timeouts, invalid URLs, JSON parse errors, etc.
            logger.warning(f"GILDA API error for '{text}': {e}")
            return []

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
