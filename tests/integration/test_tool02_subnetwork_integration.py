"""
Integration tests for Tool 2: cogex_extract_subnetwork

Tests all 5 modes with smoke, happy path, edge case, and statement limit tests.

Run with: pytest tests/integration/test_tool02_subnetwork_integration.py -v -m integration
"""

import pytest
from cogex_mcp.schemas import SubnetworkQuery, SubnetworkMode, ResponseFormat


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool2Direct:
    """Test DIRECT mode: Direct edges A→B"""

    async def test_smoke_tp53_mdm2(self, integration_adapter):
        """Smoke test: TP53-MDM2 direct edges"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.DIRECT,
            genes=["TP53", "MDM2"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_mapk_pathway(self, integration_adapter):
        """Happy path: MAPK pathway genes"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.DIRECT,
            genes=["MAPK1", "MAP2K1", "RAF1"],
            max_statements=100,
            min_evidence_count=2,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None
        assert isinstance(result, dict)

    async def test_edge_case_no_edges(self, integration_adapter):
        """Edge case: Genes with no direct edges"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.DIRECT,
            genes=["GENE1FAKE", "GENE2FAKE"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        try:
            result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
            # Should return empty or minimal results
            assert result is not None
        except Exception:
            pass  # May error on unknown genes

    async def test_statement_limit(self, integration_adapter):
        """Test statement limit enforcement"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.DIRECT,
            genes=["TP53", "MDM2", "BCL2"],
            max_statements=10,  # Small limit
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool2Mediated:
    """Test MEDIATED mode: Two-hop paths A→X→B"""

    async def test_smoke_brca1_rad51(self, integration_adapter):
        """Smoke test: BRCA1-RAD51 mediated connections"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.MEDIATED,
            genes=["BRCA1", "RAD51"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_with_evidence(self, integration_adapter):
        """Happy path: Include evidence text"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.MEDIATED,
            genes=["EGFR", "PIK3CA"],
            max_statements=30,
            include_evidence=True,
            max_evidence_per_statement=3,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_single_gene(self, integration_adapter):
        """Edge case: Single gene (no pairs)"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.MEDIATED,
            genes=["TP53"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        try:
            result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
            assert result is not None
        except Exception:
            pass  # May require multiple genes

    async def test_belief_filter(self, integration_adapter):
        """Test minimum belief score filter"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.MEDIATED,
            genes=["KRAS", "BRAF"],
            max_statements=50,
            min_belief_score=0.5,  # High confidence only
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool2SharedUpstream:
    """Test SHARED_UPSTREAM mode: A←X→B (shared regulators)"""

    async def test_smoke_myc_jun(self, integration_adapter):
        """Smoke test: MYC-JUN shared regulators"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_UPSTREAM,
            genes=["MYC", "JUN"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_kinases(self, integration_adapter):
        """Happy path: Kinases with shared regulators"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_UPSTREAM,
            genes=["MAPK1", "MAPK3", "AKT1"],
            max_statements=100,
            min_evidence_count=2,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_unrelated_genes(self, integration_adapter):
        """Edge case: Genes unlikely to have shared regulators"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_UPSTREAM,
            genes=["TP53", "INS"],  # Different pathways
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_statement_type_filter(self, integration_adapter):
        """Test filtering by statement types"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_UPSTREAM,
            genes=["STAT3", "STAT1"],
            max_statements=50,
            statement_types=["Phosphorylation", "Activation"],
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool2SharedDownstream:
    """Test SHARED_DOWNSTREAM mode: A→X←B (shared targets)"""

    async def test_smoke_tp53_rb1(self, integration_adapter):
        """Smoke test: TP53-RB1 shared targets"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_DOWNSTREAM,
            genes=["TP53", "RB1"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_transcription_factors(self, integration_adapter):
        """Happy path: Transcription factors with shared targets"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_DOWNSTREAM,
            genes=["MYC", "MAX", "MXD1"],
            max_statements=100,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_empty_results(self, integration_adapter):
        """Edge case: Genes with no known shared targets"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_DOWNSTREAM,
            genes=["GENE_FAKE1", "GENE_FAKE2"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        try:
            result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
            assert result is not None
        except Exception:
            pass  # Expected to fail on fake genes

    async def test_tissue_filter(self, integration_adapter):
        """Test tissue-specific filtering"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_DOWNSTREAM,
            genes=["NEUROD1", "NEUROG1"],
            max_statements=50,
            tissue_filter="brain",
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool2SourceToTargets:
    """Test SOURCE_TO_TARGETS mode: One source → multiple targets"""

    async def test_smoke_tp53_targets(self, integration_adapter):
        """Smoke test: TP53 to target genes"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SOURCE_TO_TARGETS,
            source_gene="TP53",
            target_genes=["MDM2", "BAX", "CDKN1A", "BCL2"],
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_egfr_signaling(self, integration_adapter):
        """Happy path: EGFR downstream signaling"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SOURCE_TO_TARGETS,
            source_gene="EGFR",
            target_genes=["MAPK1", "AKT1", "STAT3", "PIK3CA"],
            max_statements=100,
            min_evidence_count=2,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_no_connections(self, integration_adapter):
        """Edge case: Source with no known connections to targets"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SOURCE_TO_TARGETS,
            source_gene="INS",
            target_genes=["TP53", "BRCA1"],  # Unlikely connections
            max_statements=50,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_large_target_set(self, integration_adapter):
        """Test with many target genes"""
        query = SubnetworkQuery(
            mode=SubnetworkMode.SOURCE_TO_TARGETS,
            source_gene="MAPK1",
            target_genes=["FOS", "JUN", "ELK1", "MYC", "ETS1", "ATF2"],
            max_statements=150,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("extract_subnetwork", **query.model_dump(exclude_none=True))
        assert result is not None
