"""
Integration tests for Tool 3: cogex_enrichment_analysis

Tests all 4 enrichment types across different sources.

Run with: pytest tests/integration/test_tool03_enrichment_integration.py -v -m integration
"""

import pytest

from cogex_mcp.schemas import EnrichmentQuery, EnrichmentSource, EnrichmentType, ResponseFormat


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool3DiscreteEnrichment:
    """Test DISCRETE enrichment: Overrepresentation analysis"""

    async def test_smoke_go_enrichment(self, integration_adapter):
        """Smoke test: GO enrichment for gene list"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.DISCRETE,
            gene_list=["TP53", "MDM2", "BAX", "BCL2", "CDKN1A"],
            source=EnrichmentSource.GO,
            alpha=0.05,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_reactome(self, integration_adapter):
        """Happy path: Reactome pathway enrichment"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.DISCRETE,
            gene_list=["MAPK1", "MAPK3", "RAF1", "MAP2K1", "MAP2K2", "HRAS", "KRAS"],
            source=EnrichmentSource.REACTOME,
            alpha=0.05,
            correction_method="fdr_bh",
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None
        assert isinstance(result, dict)

    async def test_edge_case_single_gene(self, integration_adapter):
        """Edge case: Single gene (minimal enrichment)"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.DISCRETE,
            gene_list=["TP53"],
            source=EnrichmentSource.GO,
            alpha=0.05,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_keep_insignificant(self, integration_adapter):
        """Test keeping insignificant results"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.DISCRETE,
            gene_list=["TP53", "BRCA1", "EGFR"],
            source=EnrichmentSource.GO,
            alpha=0.05,
            keep_insignificant=True,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool3ContinuousEnrichment:
    """Test CONTINUOUS enrichment: GSEA with ranked genes"""

    async def test_smoke_gsea(self, integration_adapter):
        """Smoke test: GSEA with ranked gene list"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.CONTINUOUS,
            ranked_genes={
                "TP53": 2.5,
                "MDM2": 1.8,
                "BCL2": -1.2,
                "BAX": 1.5,
                "CDKN1A": 2.0,
            },
            source=EnrichmentSource.GO,
            permutations=1000,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_reactome_gsea(self, integration_adapter):
        """Happy path: Reactome GSEA"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.CONTINUOUS,
            ranked_genes={
                "MAPK1": 3.2,
                "MAPK3": 2.8,
                "RAF1": 2.1,
                "MAP2K1": 1.9,
                "HRAS": -1.5,
                "KRAS": -2.0,
            },
            source=EnrichmentSource.REACTOME,
            permutations=1000,
            alpha=0.05,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_uniform_scores(self, integration_adapter):
        """Edge case: All genes same score (no ranking)"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.CONTINUOUS,
            ranked_genes={
                "TP53": 1.0,
                "BRCA1": 1.0,
                "EGFR": 1.0,
            },
            source=EnrichmentSource.GO,
            permutations=100,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_fewer_permutations(self, integration_adapter):
        """Test with fewer permutations for speed"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.CONTINUOUS,
            ranked_genes={
                "TP53": 2.0,
                "MDM2": 1.5,
                "BCL2": -1.0,
                "BAX": 1.2,
            },
            source=EnrichmentSource.WIKIPATHWAYS,
            permutations=100,  # Faster
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool3SignedEnrichment:
    """Test SIGNED enrichment: Directional enrichment"""

    async def test_smoke_signed(self, integration_adapter):
        """Smoke test: Signed enrichment"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.SIGNED,
            ranked_genes={
                "TP53": 3.0,   # Up
                "MDM2": 2.5,   # Up
                "BCL2": -2.0,  # Down
                "BAX": -1.5,   # Down
            },
            source=EnrichmentSource.GO,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_indra_upstream(self, integration_adapter):
        """Happy path: INDRA upstream regulators"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.SIGNED,
            ranked_genes={
                "MAPK1": 2.5,
                "MAPK3": 2.0,
                "AKT1": 1.8,
                "GSK3B": -1.5,
            },
            source=EnrichmentSource.INDRA_UPSTREAM,
            min_evidence_count=2,
            min_belief_score=0.3,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_all_upregulated(self, integration_adapter):
        """Edge case: All genes upregulated (no negative scores)"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.SIGNED,
            ranked_genes={
                "TP53": 3.0,
                "BRCA1": 2.5,
                "EGFR": 2.0,
            },
            source=EnrichmentSource.GO,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_indra_downstream(self, integration_adapter):
        """Test INDRA downstream targets enrichment"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.SIGNED,
            ranked_genes={
                "EGFR": 3.0,
                "ERBB2": 2.5,
                "MET": 2.0,
            },
            source=EnrichmentSource.INDRA_DOWNSTREAM,
            min_evidence_count=1,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool3MetaboliteEnrichment:
    """Test METABOLITE enrichment: Metabolite set enrichment"""

    async def test_smoke_metabolite(self, integration_adapter):
        """Smoke test: Metabolite enrichment"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.METABOLITE,
            gene_list=["PFKM", "PFKL", "PFKP", "ALDOA", "PKM"],
            source=EnrichmentSource.REACTOME,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_metabolism_genes(self, integration_adapter):
        """Happy path: Metabolism-related genes"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.METABOLITE,
            gene_list=["HK1", "HK2", "GCK", "PFKM", "ALDOA", "TPI1", "PKM"],
            source=EnrichmentSource.REACTOME,
            alpha=0.05,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_edge_case_non_metabolic_genes(self, integration_adapter):
        """Edge case: Non-metabolic genes (should have fewer results)"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.METABOLITE,
            gene_list=["TP53", "BRCA1", "EGFR"],
            source=EnrichmentSource.REACTOME,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_bonferroni_correction(self, integration_adapter):
        """Test Bonferroni correction (more stringent)"""
        query = EnrichmentQuery(
            analysis_type=EnrichmentType.METABOLITE,
            gene_list=["PFKM", "ALDOA", "PKM", "ENO1", "GAPDH"],
            source=EnrichmentSource.REACTOME,
            alpha=0.05,
            correction_method="bonferroni",
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("enrichment_analysis", **query.model_dump(exclude_none=True))
        assert result is not None
