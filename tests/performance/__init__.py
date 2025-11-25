"""
Performance testing framework for INDRA CoGEx MCP server.

Provides:
- Latency benchmarking for all 16 tools
- Concurrency testing (10x, 60x)
- Connection pool efficiency analysis
- Cache performance measurement
- Performance profiling utilities
"""

__all__ = [
    "profiler",
    "conftest",
]
