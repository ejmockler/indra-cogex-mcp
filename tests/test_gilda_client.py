"""Tests for GILDA client implementation."""

import pytest
import httpx
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from cogex_mcp.clients.gilda_client import GildaClient
from cogex_mcp.services.gilda_cache import GildaCache
from cogex_mcp.services.curie_normalizer import normalize_curie, normalize_gilda_results


# Sample GILDA API response (realistic structure)
SAMPLE_GILDA_RESPONSE = [
    {
        "term": {
            "db": "MESH",
            "id": "D000690",
            "text": "Amyotrophic Lateral Sclerosis",
            "entry_name": "Amyotrophic Lateral Sclerosis",
        },
        "score": 0.9,
        "match": {
            "exact": True,
            "alias": "ALS",
        },
    },
    {
        "term": {
            "db": "DOID",
            "id": "DOID:332",
            "text": "amyotrophic lateral sclerosis",
            "entry_name": "amyotrophic lateral sclerosis",
        },
        "score": 0.85,
        "match": {
            "exact": False,
            "alias": "ALS",
        },
    },
]


class TestCurieNormalizer:
    """Test CURIE normalization functions."""

    def test_normalize_curie_with_redundant_prefix(self):
        """Test normalizing CURIE with redundant namespace prefix."""
        assert normalize_curie("CHEBI", "CHEBI:8863") == "chebi:8863"
        assert normalize_curie("DOID", "DOID:332") == "doid:332"
        assert normalize_curie("HGNC", "HGNC:5468") == "hgnc:5468"
        assert normalize_curie("GO", "GO:0005783") == "go:0005783"

    def test_normalize_curie_without_prefix(self):
        """Test normalizing CURIE without redundant prefix."""
        assert normalize_curie("MESH", "D000690") == "mesh:D000690"
        assert normalize_curie("mesh", "D003920") == "mesh:D003920"

    def test_normalize_curie_case_insensitive(self):
        """Test case-insensitive prefix removal."""
        assert normalize_curie("chebi", "CHEBI:8863") == "chebi:8863"
        assert normalize_curie("CHEBI", "chebi:8863") == "chebi:8863"

    def test_normalize_curie_already_normalized(self):
        """Test normalizing already-normalized CURIEs."""
        assert normalize_curie("chebi", "8863") == "chebi:8863"
        assert normalize_curie("doid", "332") == "doid:332"

    def test_normalize_gilda_results(self):
        """Test normalizing full GILDA response."""
        results = [
            {
                "term": {"db": "CHEBI", "id": "CHEBI:8863", "text": "Propranolol"},
                "score": 0.95,
            },
            {
                "term": {"db": "MESH", "id": "D000690", "text": "ALS"},
                "score": 0.88,
            },
        ]

        normalized = normalize_gilda_results(results)

        # Check in-place modification
        assert normalized is results

        # Check normalized values
        assert results[0]["term"]["db"] == "chebi"
        assert results[0]["term"]["id"] == "8863"
        assert results[1]["term"]["db"] == "mesh"
        assert results[1]["term"]["id"] == "D000690"  # No prefix to remove

    def test_normalize_gilda_results_empty(self):
        """Test normalizing empty results."""
        results = []
        normalized = normalize_gilda_results(results)
        assert normalized == []

    def test_normalize_gilda_results_missing_fields(self):
        """Test normalizing results with missing fields (graceful handling)."""
        results = [
            {"term": {}},  # Missing db and id
            {"score": 0.5},  # Missing term
        ]

        normalized = normalize_gilda_results(results)
        # Should not crash, just skip normalization
        assert normalized is results


class TestGildaCache:
    """Test GILDA cache implementation."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create temporary cache directory for testing."""
        return tmp_path / "gilda_cache"

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create GildaCache instance with temporary directory."""
        return GildaCache(
            cache_dir=temp_cache_dir,
            max_entries=5,
            max_size_mb=1,
            max_age_days=1,
        )

    def test_cache_init_creates_directory(self, temp_cache_dir):
        """Test that cache initialization creates directory."""
        cache = GildaCache(cache_dir=temp_cache_dir)
        assert temp_cache_dir.exists()
        assert temp_cache_dir.is_dir()

    def test_cache_set_and_get(self, cache):
        """Test basic cache set and get operations."""
        term = "diabetes"
        results = [{"term": {"db": "mesh", "id": "D003920"}, "score": 0.9}]

        # Set cache
        cache.set(term, results)

        # Get cache
        cached = cache.get(term)
        assert cached is not None
        assert cached == results

    def test_cache_miss_nonexistent(self, cache):
        """Test cache miss for nonexistent term."""
        cached = cache.get("nonexistent_term")
        assert cached is None

    def test_cache_expiration(self, cache, temp_cache_dir):
        """Test cache expiration based on age."""
        term = "diabetes"
        results = [{"term": {"db": "mesh", "id": "D003920"}}]

        # Set cache
        cache.set(term, results)

        # Should be cached with default max_age_hours=24
        assert cache.get(term, max_age_hours=24) is not None

        # Should expire with max_age_hours=0
        assert cache.get(term, max_age_hours=0) is None

    def test_cache_key_hashing(self, cache):
        """Test that cache keys are MD5 hashed."""
        term = "diabetes"
        cache_key = cache._cache_key(term)

        # MD5 hash is 32 characters
        assert len(cache_key) == 32
        assert cache_key.isalnum()

        # Same term produces same hash
        assert cache._cache_key(term) == cache._cache_key(term)

        # Case-insensitive
        assert cache._cache_key("Diabetes") == cache._cache_key("diabetes")

    def test_cache_lru_eviction_by_count(self, cache):
        """Test LRU eviction when max_entries limit is reached."""
        # Add 6 entries (cache max_entries=5)
        for i in range(6):
            cache.set(f"term_{i}", [{"result": i}])

        # Trigger cleanup
        cache._cleanup()

        # Should have at most 5 entries
        cache_files = list(cache.cache_dir.glob("*.json"))
        assert len(cache_files) <= 5

    def test_cache_clear(self, cache):
        """Test clearing entire cache."""
        # Add some entries
        for i in range(3):
            cache.set(f"term_{i}", [{"result": i}])

        # Verify entries exist
        assert len(list(cache.cache_dir.glob("*.json"))) == 3

        # Clear cache
        cache.clear()

        # Verify all entries removed
        assert len(list(cache.cache_dir.glob("*.json"))) == 0

    def test_cache_graceful_error_handling(self, cache, monkeypatch):
        """Test that cache errors don't crash (graceful degradation)."""
        # Mock file operations to raise errors
        def mock_open_error(*args, **kwargs):
            raise OSError("Mock file error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        # Set should not crash
        cache.set("term", [{"result": 1}])

        # Get should return None (not crash)
        result = cache.get("term")
        assert result is None


class TestGildaClient:
    """Test GildaClient implementation."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create temporary cache directory for testing."""
        return tmp_path / "gilda_cache"

    @pytest.fixture
    def client(self, temp_cache_dir):
        """Create GildaClient instance with temporary cache."""
        cache = GildaCache(cache_dir=temp_cache_dir)
        return GildaClient(cache=cache)

    @pytest.mark.asyncio
    async def test_gilda_client_ground_success(self, client):
        """Test successful GILDA API call with mocked response."""
        # Mock httpx response
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_GILDA_RESPONSE.copy()
        mock_response.raise_for_status = Mock()

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            results = await client.ground("ALS", use_cache=False)

            # Check results are normalized
            assert len(results) == 2
            assert results[0]["term"]["db"] == "mesh"  # lowercase
            assert results[0]["term"]["id"] == "D000690"  # no MESH: prefix
            assert results[1]["term"]["db"] == "doid"
            assert results[1]["term"]["id"] == "332"  # DOID: prefix removed

    @pytest.mark.asyncio
    async def test_gilda_client_cache_hit(self, client):
        """Test cache hit (should not call API)."""
        # Pre-populate cache
        cached_results = [{"term": {"db": "mesh", "id": "D003920"}, "score": 0.9}]
        client.cache.set("diabetes", cached_results)

        # Mock API call (should not be called)
        with patch.object(client.client, "post", new=AsyncMock()) as mock_post:
            results = await client.ground("diabetes", use_cache=True)

            # Verify cache hit (API not called)
            mock_post.assert_not_called()

            # Verify results from cache
            assert results == cached_results

    @pytest.mark.asyncio
    async def test_gilda_client_curie_normalization(self, client):
        """Test that GILDA results are normalized correctly."""
        # Mock response with redundant prefixes
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "term": {
                    "db": "CHEBI",
                    "id": "CHEBI:8863",
                    "text": "Propranolol",
                },
                "score": 0.95,
            }
        ]
        mock_response.raise_for_status = Mock()

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            results = await client.ground("propranolol", use_cache=False)

            # Verify normalization
            assert results[0]["term"]["db"] == "chebi"
            assert results[0]["term"]["id"] == "8863"  # Prefix removed

    @pytest.mark.asyncio
    async def test_gilda_client_error_handling(self, client):
        """Test graceful degradation on API errors."""
        # Mock HTTP error
        with patch.object(
            client.client,
            "post",
            new=AsyncMock(side_effect=httpx.HTTPError("Mock error")),
        ):
            results = await client.ground("invalid_term")

            # Should return empty list (not crash)
            assert results == []

    @pytest.mark.asyncio
    async def test_gilda_client_timeout_error(self, client):
        """Test timeout handling."""
        # Mock timeout
        with patch.object(
            client.client,
            "post",
            new=AsyncMock(side_effect=httpx.TimeoutException("Timeout")),
        ):
            results = await client.ground("slow_term")

            # Should return empty list (graceful degradation)
            assert results == []

    @pytest.mark.asyncio
    async def test_gilda_client_context_manager(self, temp_cache_dir):
        """Test async context manager support."""
        async with GildaClient(cache=GildaCache(cache_dir=temp_cache_dir)) as client:
            # Mock response
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status = Mock()

            with patch.object(
                client.client, "post", new=AsyncMock(return_value=mock_response)
            ):
                results = await client.ground("test")
                assert results == []

        # Client should be closed after exiting context manager
        # (httpx client closed)

    @pytest.mark.asyncio
    async def test_gilda_client_empty_results(self, client):
        """Test handling of empty GILDA results."""
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            results = await client.ground("nonexistent_term", use_cache=False)

            assert results == []

    @pytest.mark.asyncio
    async def test_gilda_client_organism_parameter(self, client):
        """Test that organism parameter is passed to API."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await client.ground("TP53", organism="mouse", use_cache=False)

            # Verify API called with correct parameters
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["text"] == "TP53"
            assert call_args[1]["json"]["organism"] == "mouse"

    @pytest.mark.asyncio
    async def test_gilda_client_close(self, client):
        """Test explicit client close."""
        # Mock aclose
        with patch.object(client.client, "aclose", new=AsyncMock()) as mock_aclose:
            await client.close()
            mock_aclose.assert_called_once()


# Integration tests (require real GILDA API)
class TestGildaClientIntegration:
    """Integration tests with real GILDA API (marked as integration)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_gilda_api_call(self, tmp_path):
        """Test real GILDA API call (requires network)."""
        cache = GildaCache(cache_dir=tmp_path / "gilda_cache")
        async with GildaClient(cache=cache, timeout=10.0) as client:
            # Test with well-known term
            results = await client.ground("diabetes mellitus", use_cache=False)

            # Should get results from real API
            assert len(results) > 0

            # Check result structure
            first_result = results[0]
            assert "term" in first_result
            assert "db" in first_result["term"]
            assert "id" in first_result["term"]
            assert "score" in first_result

            # Check normalization (lowercase namespace)
            assert first_result["term"]["db"].islower()

            # Score should be between 0 and 1
            assert 0 <= first_result["score"] <= 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_gilda_api_ambiguous_term(self, tmp_path):
        """Test GILDA API with ambiguous term."""
        cache = GildaCache(cache_dir=tmp_path / "gilda_cache")
        async with GildaClient(cache=cache, timeout=10.0) as client:
            # "ER" is ambiguous (gene, organelle, receptor)
            results = await client.ground("ER", use_cache=False)

            # Should get multiple results
            assert len(results) > 1

            # Check variety of namespaces
            namespaces = {r["term"]["db"] for r in results}
            assert len(namespaces) > 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_gilda_api_cache_behavior(self, tmp_path):
        """Test cache behavior with real API."""
        cache = GildaCache(cache_dir=tmp_path / "gilda_cache")
        async with GildaClient(cache=cache, timeout=10.0) as client:
            term = "ALS"

            # First call - cache miss (API call)
            results1 = await client.ground(term, use_cache=True)
            assert len(results1) > 0

            # Second call - cache hit (no API call)
            results2 = await client.ground(term, use_cache=True)

            # Results should be identical
            assert results1 == results2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
