"""
Performance test fixtures.

Provides fixtures for performance testing including:
- Performance-optimized adapter
- Known entities for testing
- Profiler utilities
- Report generation
"""

import asyncio
import logging
import pytest
from pathlib import Path
from typing import Dict, Any

from cogex_mcp.clients.adapter import ClientAdapter, get_adapter
from cogex_mcp.config import settings
from tests.performance.profiler import PerformanceProfiler

# Configure logging for performance tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def performance_adapter():
    """
    Initialize adapter configured for performance testing.

    Uses production credentials with detailed timing logs.
    Cache is enabled for realistic performance measurement.
    """
    logger.info("Initializing performance adapter")

    # Get adapter (singleton)
    adapter = await get_adapter()

    # Verify connection
    status = adapter.get_status()
    logger.info(f"Adapter status: {status}")

    if not status["initialized"]:
        raise RuntimeError("Adapter initialization failed")

    yield adapter

    # Cleanup
    logger.info("Closing performance adapter")
    await adapter.close()


@pytest.fixture(scope="session")
def performance_profiler():
    """
    Initialize performance profiler for report generation.
    """
    reports_dir = Path(__file__).parent / "reports"
    profiler = PerformanceProfiler(reports_dir=reports_dir)
    logger.info(f"Performance profiler initialized (reports: {reports_dir})")
    return profiler


@pytest.fixture(scope="session")
def known_entities() -> Dict[str, Any]:
    """
    Known-good entities for performance testing.

    Returns:
        Dictionary of entities verified to exist in CoGEx database
    """
    return {
        "genes": [
            "TP53",      # Tumor protein p53
            "BRCA1",     # Breast cancer 1
            "EGFR",      # Epidermal growth factor receptor
            "KRAS",      # Kirsten rat sarcoma viral oncogene
            "MAPK1",     # Mitogen-activated protein kinase 1
            "AKT1",      # AKT serine/threonine kinase 1
            "PTEN",      # Phosphatase and tensin homolog
            "MYC",       # MYC proto-oncogene
            "BCL2",      # BCL2 apoptosis regulator
            "TNF",       # Tumor necrosis factor
        ],
        "drugs": [
            "imatinib",       # Gleevec
            "aspirin",        # Acetylsalicylic acid
            "pembrolizumab",  # Keytruda
            "metformin",      # Glucophage
            "doxorubicin",    # Adriamycin
        ],
        "diseases": [
            "diabetes mellitus",
            "alzheimer disease",
            "breast cancer",
            "parkinson disease",
            "hypertension",
        ],
        "tissues": [
            "brain",
            "liver",
            "heart",
            "lung",
            "blood",
        ],
        "pathways": [
            "p53 signaling",
            "MAPK signaling",
            "PI3K-Akt signaling",
            "apoptosis",
        ],
        "go_terms": [
            "GO:0006915",  # apoptosis
            "GO:0008283",  # cell proliferation
            "GO:0007165",  # signal transduction
        ],
        "variants": [
            "rs7412",      # APOE variant
            "rs429358",    # APOE variant
        ],
        "cell_lines": [
            "A549",        # Lung cancer cell line
            "MCF7",        # Breast cancer cell line
            "HeLa",        # Cervical cancer cell line
        ],
    }


@pytest.fixture(scope="session")
def performance_targets() -> Dict[str, Dict[str, float]]:
    """
    Performance targets for latency benchmarks.

    Returns:
        Dictionary mapping tool categories to target p95 latencies (ms)
    """
    return {
        "complex_queries": {
            "p95_target_ms": 5000,
            "tools": [
                "tool_01_gene_feature",
                "tool_02_subnetwork",
                "tool_03_enrichment",
                "tool_05_disease_phenotype",
                "tool_09_literature",
            ],
        },
        "moderate_queries": {
            "p95_target_ms": 2000,
            "tools": [
                "tool_04_drug_effect",
                "tool_06_pathway",
                "tool_07_cell_line",
                "tool_08_clinical_trials",
                "tool_10_variants",
            ],
        },
        "simple_queries": {
            "p95_target_ms": 1000,
            "tools": [
                "tool_11_identifier",
                "tool_12_relationship",
                "tool_13_ontology",
                "tool_14_cell_marker",
                "tool_15_kinase",
                "tool_16_protein_function",
            ],
        },
    }


@pytest.fixture(scope="function")
async def connection_pool_monitor(performance_adapter):
    """
    Monitor connection pool statistics during test execution.

    Yields:
        Function to get current pool statistics
    """
    stats_history = []

    def get_pool_stats() -> Dict[str, Any]:
        """Get current connection pool statistics."""
        # Get Neo4j client pool stats if available
        if performance_adapter.neo4j_client:
            # Note: This is a placeholder - actual implementation depends on
            # Neo4j driver's connection pool API
            return {
                "active_connections": 0,  # Would query from driver
                "idle_connections": 0,    # Would query from driver
                "total_connections": 0,   # Would query from driver
                "timestamp": asyncio.get_event_loop().time(),
            }
        return {}

    yield get_pool_stats

    # Save statistics history
    if stats_history:
        logger.info(f"Connection pool stats collected: {len(stats_history)} samples")


@pytest.fixture(autouse=True)
def log_test_duration(request):
    """Automatically log test duration for all performance tests."""
    import time

    start = time.time()
    test_name = request.node.name

    logger.info(f"Starting performance test: {test_name}")

    yield

    duration = time.time() - start
    logger.info(f"Completed {test_name} in {duration:.2f}s")


@pytest.fixture(scope="session", autouse=True)
def performance_test_session(request):
    """Session-level setup and teardown for performance tests."""
    logger.info("=" * 80)
    logger.info("STARTING PERFORMANCE TEST SESSION")
    logger.info("=" * 80)

    yield

    logger.info("=" * 80)
    logger.info("PERFORMANCE TEST SESSION COMPLETE")
    logger.info("=" * 80)
    logger.info("Reports available in: tests/performance/reports/")
