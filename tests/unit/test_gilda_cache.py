"""
Comprehensive tests for GildaCache file-based caching system.

Tests cover:
- Basic cache set/get operations
- Cache expiration (age-based)
- LRU eviction (count-based)
- LRU eviction (size-based)
- Combined cleanup scenarios
- Corrupted file handling
- Error resilience

Run with: pytest tests/unit/test_gilda_cache.py -v
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

from cogex_mcp.services.gilda_cache import GildaCache


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for testing."""
    cache_dir = tmp_path / "gilda_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def cache(temp_cache_dir):
    """Create GildaCache instance with temporary directory."""
    return GildaCache(
        cache_dir=temp_cache_dir,
        max_entries=10,
        max_size_mb=1,  # 1 MB for testing
        max_age_days=7,
    )


def test_cache_initialization(temp_cache_dir):
    """Test cache initializes correctly."""
    cache = GildaCache(
        cache_dir=temp_cache_dir,
        max_entries=100,
        max_size_mb=10,
        max_age_days=3,
    )

    assert cache.cache_dir == temp_cache_dir
    assert cache.max_entries == 100
    assert cache.max_size_bytes == 10 * 1024 * 1024
    assert cache.max_age_days == 3
    assert temp_cache_dir.exists()


def test_cache_key_generation(cache):
    """Test MD5 hash generation for cache keys."""
    key1 = cache._cache_key("diabetes")
    key2 = cache._cache_key("DIABETES")  # Should be same (case-insensitive)
    key3 = cache._cache_key("ALS")

    # Check format
    assert len(key1) == 32  # MD5 hash is 32 hex chars
    assert key1.isalnum()

    # Check case insensitivity
    assert key1 == key2

    # Check different terms produce different keys
    assert key1 != key3


def test_cache_set_get(cache):
    """Test basic cache set and get operations."""
    term = "diabetes"
    results = [
        {"term": {"db": "mesh", "id": "D003920"}, "score": 0.85},
        {"term": {"db": "doid", "id": "9351"}, "score": 0.80},
    ]

    # Set cache
    cache.set(term, results)

    # Get cache
    cached_results = cache.get(term)

    assert cached_results is not None
    assert len(cached_results) == 2
    assert cached_results[0]["term"]["db"] == "mesh"
    assert cached_results[1]["score"] == 0.80


def test_cache_miss_nonexistent(cache):
    """Test cache miss for nonexistent term."""
    result = cache.get("nonexistent_term_xyz")
    assert result is None


def test_cache_expiration(cache, temp_cache_dir):
    """Test cache expiration based on age."""
    term = "old_term"
    results = [{"term": {"db": "mesh", "id": "D000001"}, "score": 0.90}]

    # Set cache
    cache.set(term, results)

    # Verify it exists
    assert cache.get(term, max_age_hours=24) is not None

    # Modify file mtime to make it old
    cache_file = temp_cache_dir / f"{cache._cache_key(term)}.json"
    old_time = (datetime.now() - timedelta(hours=25)).timestamp()
    cache_file.touch()
    import os

    os.utime(cache_file, (old_time, old_time))

    # Should be expired now
    assert cache.get(term, max_age_hours=24) is None

    # But should still be available with longer max_age
    assert cache.get(term, max_age_hours=48) is not None


def test_cache_lru_eviction_by_count(cache):
    """Test LRU eviction when max_entries is exceeded."""
    # Cache is configured with max_entries=10

    # Add 12 entries (should evict 2 oldest)
    for i in range(12):
        cache.set(f"term_{i}", [{"id": i}])
        time.sleep(0.01)  # Ensure different mtimes

    # Force cleanup
    cache._cleanup()

    # Should have at most 10 entries
    cache_files = list(cache.cache_dir.glob("*.json"))
    assert len(cache_files) <= 10

    # Oldest entries (term_0, term_1) should be evicted
    assert cache.get("term_0") is None
    assert cache.get("term_1") is None

    # Newest entries should still exist
    assert cache.get("term_10") is not None
    assert cache.get("term_11") is not None


def test_cache_lru_eviction_by_size(cache):
    """Test LRU eviction when max_size is exceeded."""
    # Create large results that will exceed 1MB limit
    large_results = [{"data": "x" * 100_000} for _ in range(5)]

    # Add multiple large entries
    for i in range(15):
        cache.set(f"large_term_{i}", large_results)
        time.sleep(0.01)

    # Force cleanup
    cache._cleanup()

    # Check total size is under limit
    total_size = sum(f.stat().st_size for f in cache.cache_dir.glob("*.json"))
    assert total_size <= cache.max_size_bytes

    # Some old entries should be evicted
    # (exact count depends on size, but first few should be gone)
    assert cache.get("large_term_0") is None


def test_cache_cleanup_by_age(cache, temp_cache_dir):
    """Test cleanup removes entries older than max_age_days."""
    # Create cache with short max_age
    short_cache = GildaCache(
        cache_dir=temp_cache_dir,
        max_entries=100,
        max_size_mb=10,
        max_age_days=1,  # 1 day max age
    )

    # Add entries
    for i in range(5):
        short_cache.set(f"term_{i}", [{"id": i}])

    # Make first 3 entries old
    import os

    for i in range(3):
        cache_file = temp_cache_dir / f"{short_cache._cache_key(f'term_{i}')}.json"
        old_time = (datetime.now() - timedelta(days=2)).timestamp()
        os.utime(cache_file, (old_time, old_time))

    # Force cleanup
    short_cache._cleanup()

    # Old entries should be removed
    assert short_cache.get(f"term_0") is None
    assert short_cache.get(f"term_1") is None
    assert short_cache.get(f"term_2") is None

    # Recent entries should remain
    assert short_cache.get(f"term_3") is not None
    assert short_cache.get(f"term_4") is not None


def test_cache_corrupted_file(cache, temp_cache_dir):
    """Test handling of corrupted cache files."""
    term = "corrupted_term"

    # Create corrupted JSON file
    cache_file = temp_cache_dir / f"{cache._cache_key(term)}.json"
    with open(cache_file, "w") as f:
        f.write("{ invalid json content }")

    # Should return None and not crash
    result = cache.get(term)
    assert result is None


def test_cache_missing_results_key(cache, temp_cache_dir):
    """Test handling of cache file missing 'results' key."""
    term = "incomplete_term"

    # Create file with missing 'results' key
    cache_file = temp_cache_dir / f"{cache._cache_key(term)}.json"
    with open(cache_file, "w") as f:
        json.dump({"term": term, "cached_at": datetime.now().isoformat()}, f)

    # Should return None
    result = cache.get(term)
    assert result is None


def test_cache_clear(cache):
    """Test clearing entire cache."""
    # Add multiple entries
    for i in range(5):
        cache.set(f"term_{i}", [{"id": i}])

    # Verify they exist
    assert len(list(cache.cache_dir.glob("*.json"))) == 5

    # Clear cache
    cache.clear()

    # All files should be removed
    assert len(list(cache.cache_dir.glob("*.json"))) == 0


def test_cache_probabilistic_cleanup(cache):
    """Test that cleanup mechanism works to enforce limits."""
    # Add more entries than the limit
    for i in range(20):
        cache.set(f"term_{i}", [{"id": i}])

    # Explicitly trigger cleanup
    cache._cleanup()

    # After cleanup, should be at or below max_entries
    cache_files = list(cache.cache_dir.glob("*.json"))
    assert len(cache_files) <= cache.max_entries

    # Verify newest entries are kept (LRU eviction)
    assert cache.get("term_19") is not None  # Most recent
    assert cache.get("term_18") is not None

    # Older entries should have been evicted
    assert cache.get("term_0") is None
    assert cache.get("term_1") is None


def test_cache_write_error_handling(tmp_path):
    """Test graceful handling of write errors."""
    # Create cache with read-only directory
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)  # Read-only

    cache = GildaCache(cache_dir=readonly_dir)

    # Set should not crash even if write fails
    try:
        cache.set("term", [{"id": 1}])
    finally:
        # Restore permissions for cleanup
        readonly_dir.chmod(0o755)

    # No exception should be raised


def test_cache_read_permission_error(tmp_path):
    """Test handling of read permission errors during cleanup."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    cache = GildaCache(cache_dir=cache_dir)

    # Add entry
    cache.set("term", [{"id": 1}])

    # Make directory unreadable
    cache_dir.chmod(0o000)

    try:
        # Cleanup should not crash
        cache._cleanup()
    finally:
        # Restore permissions
        cache_dir.chmod(0o755)


def test_cache_format_json(cache):
    """Test that cache files are valid JSON with correct format."""
    term = "test_format"
    results = [{"term": {"db": "mesh", "id": "D123"}, "score": 0.95}]

    cache.set(term, results)

    # Read file directly
    cache_file = cache.cache_dir / f"{cache._cache_key(term)}.json"
    with open(cache_file, "r") as f:
        data = json.load(f)

    # Check format
    assert "term" in data
    assert "results" in data
    assert "cached_at" in data
    assert data["term"] == term
    assert data["results"] == results
    assert isinstance(data["cached_at"], str)

    # Verify timestamp format (ISO8601)
    datetime.fromisoformat(data["cached_at"])  # Should not raise


def test_cache_concurrent_operations(cache):
    """Test that cache handles multiple operations gracefully."""
    # Add, get, and set multiple entries
    for i in range(20):
        cache.set(f"term_{i}", [{"id": i}])

        if i % 2 == 0:
            cache.get(f"term_{i // 2}")

    # Should not crash
    cache._cleanup()

    # Cache should still be functional
    cache.set("final_term", [{"id": 999}])
    assert cache.get("final_term") is not None


def test_cache_empty_results(cache):
    """Test caching empty results list."""
    term = "no_matches"
    empty_results = []

    cache.set(term, empty_results)

    cached = cache.get(term)
    assert cached is not None
    assert cached == []
    assert len(cached) == 0


def test_cache_large_results(cache):
    """Test caching large results."""
    term = "large_result"
    large_results = [{"data": f"entry_{i}" * 100} for i in range(100)]

    cache.set(term, large_results)

    cached = cache.get(term)
    assert cached is not None
    assert len(cached) == 100


def test_cache_special_characters_in_term(cache):
    """Test caching terms with special characters."""
    special_terms = [
        "p53",
        "IL-6",
        "NF-κB",
        "alpha-1 antitrypsin",
        "5-HT receptor",
        "CD4+ T cells",
    ]

    for term in special_terms:
        results = [{"term": {"db": "test", "id": "123"}, "score": 0.8}]
        cache.set(term, results)

        cached = cache.get(term)
        assert cached is not None
        assert len(cached) == 1


def test_cache_default_directory():
    """Test that default cache directory is created correctly."""
    cache = GildaCache()

    expected_dir = Path.home() / ".cache" / "gilda"
    assert cache.cache_dir == expected_dir


def test_cache_stats_after_operations(cache):
    """Test cache statistics and state after various operations."""
    # Add entries
    for i in range(5):
        cache.set(f"term_{i}", [{"id": i}])

    # Check initial state
    initial_count = len(list(cache.cache_dir.glob("*.json")))
    assert initial_count == 5

    # Perform gets
    for i in range(3):
        cache.get(f"term_{i}")

    # Add more to trigger cleanup
    for i in range(5, 20):
        cache.set(f"term_{i}", [{"id": i}])

    cache._cleanup()

    # Should be at or below max_entries
    final_count = len(list(cache.cache_dir.glob("*.json")))
    assert final_count <= cache.max_entries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
