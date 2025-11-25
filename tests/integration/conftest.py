"""
Pytest fixtures and configuration for integration tests.

Provides fixtures for:
- Production Neo4j connection via ClientAdapter
- Known-good test entities across all biomedical entity types
- Async test setup/teardown with proper connection cleanup
"""

import logging

import pytest

from cogex_mcp.clients.adapter import ClientAdapter, close_adapter, get_adapter
from cogex_mcp.config import settings

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
async def cleanup_adapter():
    """
    Cleanup adapter singleton after each test.

    Autouse ensures this runs for ALL tests, even those that don't
    explicitly use the integration_adapter fixture.
    """
    yield
    # Cleanup after test
    await close_adapter()


@pytest.fixture
async def integration_adapter() -> ClientAdapter:
    """
    Production ClientAdapter for integration tests.

    Uses credentials from .env.production file.
    Function-scoped to ensure each test has clean connection state
    in the correct event loop context.

    Yields:
        Initialized ClientAdapter connected to production CoGEx backend
    """
    logger.info("Initializing integration test adapter with production credentials")

    # Validate production configuration
    assert settings.has_neo4j_config, "Neo4j configuration required for integration tests"
    assert settings.neo4j_url, "NEO4J_URL must be set"
    assert settings.neo4j_user, "NEO4J_USER must be set"
    assert settings.neo4j_password, "NEO4J_PASSWORD must be set"

    # Get adapter (will initialize on first call)
    # This ensures initialization happens in the test's event loop
    adapter = await get_adapter()

    # Verify connection
    status = adapter.get_status()
    assert status["initialized"], "Adapter failed to initialize"
    logger.info(f"Adapter initialized: {status}")

    yield adapter

    # Cleanup after each test
    logger.info("Closing integration test adapter")
    await close_adapter()


@pytest.fixture(scope="session")
def known_entities() -> dict[str, list[str]]:
    """
    Known-good entities for testing across all tools.

    These are well-established entities guaranteed to exist in CoGEx
    and return substantial, verifiable results.

    Returns:
        Dictionary mapping entity types to lists of known entities
    """
    return {
        # Genes - well-studied with rich annotations
        "genes": [
            "TP53",  # Tumor suppressor - most studied gene
            "BRCA1",  # Breast cancer gene
            "EGFR",  # Receptor tyrosine kinase
            "MAPK1",  # MAP kinase
            "TNF",  # Cytokine
            "IL6",  # Interleukin
            "KRAS",  # Oncogene
            "MYC",  # Transcription factor
            "BCL2",  # Apoptosis regulator
            "PTEN",  # Tumor suppressor
        ],
        # Drugs - FDA approved with known targets
        "drugs": [
            "imatinib",  # BCR-ABL inhibitor
            "aspirin",  # NSAID
            "pembrolizumab",  # PD-1 inhibitor
            "metformin",  # Diabetes drug
            "paclitaxel",  # Chemotherapy
            "tamoxifen",  # Estrogen receptor modulator
        ],
        # Diseases - well-defined in ontologies
        "diseases": [
            "diabetes mellitus",
            "alzheimer disease",
            "breast cancer",
            "parkinson disease",
            "hypertension",
            "asthma",
        ],
        # Tissues - from tissue expression data
        "tissues": [
            "brain",
            "liver",
            "heart",
            "lung",
            "kidney",
            "blood",
            "muscle",
        ],
        # Pathways - major signaling pathways
        "pathways": [
            "p53 signaling",
            "MAPK signaling",
            "PI3K-Akt signaling",
            "apoptosis",
            "cell cycle",
        ],
        # GO terms - biological processes
        "go_terms": [
            "GO:0006915",  # apoptotic process
            "GO:0008283",  # cell population proliferation
            "GO:0006468",  # protein phosphorylation
            "GO:0006355",  # regulation of DNA-templated transcription
        ],
        # Cell lines - CCLE/DepMap
        "cell_lines": [
            "A549",  # Lung cancer
            "MCF7",  # Breast cancer
            "HeLa",  # Cervical cancer
            "HCT116",  # Colon cancer
            "K562",  # Leukemia
        ],
        # Variants - well-known SNPs
        "variants": [
            "rs7412",  # APOE variant
            "rs429358",  # APOE variant
            "rs1042522",  # TP53 variant
        ],
        # Phenotypes - HPO terms
        "phenotypes": [
            "HP:0001250",  # Seizure
            "HP:0002664",  # Neoplasm
            "HP:0000822",  # Hypertension
        ],
        # Cell types for markers
        "cell_types": [
            "T cell",
            "B cell",
            "NK cell",
            "macrophage",
        ],
        # Clinical trial IDs
        "trial_ids": [
            "NCT02576431",
            "NCT01234567",
        ],
        # PubMed IDs
        "pmids": [
            "12345678",
            "23456789",
        ],
    }


@pytest.fixture(scope="session")
def timeout_configs() -> dict[str, int]:
    """
    Recommended timeout values for different query types.

    Some CoGEx queries involve complex graph traversals and can take 20-30s.

    Returns:
        Dictionary mapping query types to timeout seconds
    """
    return {
        "simple_lookup": 5,  # Entity resolution, single-hop
        "feature_query": 15,  # Gene features, pathways, etc.
        "subnetwork": 30,  # Graph traversals, multiple hops
        "enrichment": 45,  # Statistical computation
        "complex_workflow": 60,  # Multi-tool E2E workflows
    }


@pytest.fixture
def test_pagination_params() -> dict[str, int]:
    """Standard pagination parameters for testing."""
    return {
        "limit": 10,
        "offset": 0,
    }


@pytest.fixture
async def tool_caller(integration_adapter):
    """
    Helper fixture for calling MCP tools through the adapter.

    Provides a convenient interface for test code to invoke tools
    without directly dealing with adapter internals.

    Args:
        integration_adapter: Session-scoped adapter fixture

    Yields:
        Async function to call tools
    """

    async def call_tool(tool_name: str, **params):
        """
        Call an MCP tool through the adapter.

        Args:
            tool_name: Name of the tool to call
            **params: Tool parameters

        Returns:
            Tool result

        Raises:
            Exception: If tool execution fails
        """
        # Map tool names to query operations
        # This is a simplified version - real implementation would
        # need proper routing through the MCP server
        return await integration_adapter.query(tool_name, **params)

    yield call_tool


# Mark all tests in this directory as integration tests
def pytest_collection_modifyitems(items):
    """Automatically mark all tests in integration/ as integration tests."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.asyncio)


# Configure logging for integration tests
@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Configure logging for integration tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Reduce noise from some libraries
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
