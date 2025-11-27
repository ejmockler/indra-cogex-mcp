"""
Integration tests for Tool 5: cogex_query_disease_or_phenotype

Tests 3 modes with smoke, happy path, edge case, and pagination tests.

Run with: pytest tests/integration/test_tool05_disease_integration.py -v -m integration
"""

import pytest

from cogex_mcp.schemas import DiseasePhenotypeQuery, DiseaseQueryMode, ResponseFormat
from tests.integration.utils import assert_json, assert_keys, assert_non_empty


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool5DiseaseToMechanisms:
    """Test disease_to_mechanisms mode: Disease → Genes/Variants/Drugs"""

    async def test_smoke_diabetes(self, integration_adapter):
        """Smoke test: Diabetes disease mechanisms"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.DISEASE_TO_MECHANISMS,
            disease="diabetes mellitus",
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("disease_to_mechanisms", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_alzheimer_full(self, integration_adapter):
        """Happy path: Alzheimer's with full mechanism data"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.DISEASE_TO_MECHANISMS,
            disease="alzheimer disease",
            include_genes=True,
            include_variants=True,
            include_phenotypes=True,
            include_drugs=True,
            include_trials=True,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("disease_to_mechanisms", **query.model_dump(exclude_none=True))

        data = assert_json(result)
        assert_keys(data, ["disease"])
        assert_non_empty(data, "genes")

    async def test_edge_case_rare_disease(self, integration_adapter):
        """Edge case: Very rare disease with limited data"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.DISEASE_TO_MECHANISMS,
            disease="progeria",
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("disease_to_mechanisms", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_pagination_genes(self, integration_adapter):
        """Pagination: Limit genes for disease"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.DISEASE_TO_MECHANISMS,
            disease="breast cancer",
            include_genes=True,
            include_variants=False,
            include_drugs=False,
            limit=10,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("disease_to_mechanisms", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool5PhenotypeToDiseases:
    """Test phenotype_to_diseases mode: Phenotype → Diseases"""

    async def test_smoke_seizure(self, integration_adapter):
        """Smoke test: Seizure phenotype to diseases"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.PHENOTYPE_TO_DISEASES,
            phenotype="HP:0001250",  # Seizure
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("phenotype_to_diseases", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_hypertension(self, integration_adapter):
        """Happy path: Hypertension phenotype"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.PHENOTYPE_TO_DISEASES,
            phenotype="HP:0000822",  # Hypertension
            limit=30,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("phenotype_to_diseases", **query.model_dump(exclude_none=True))

        data = assert_json(result)
        assert_non_empty(data, "diseases")

    async def test_edge_case_rare_phenotype(self, integration_adapter):
        """Edge case: Very specific/rare phenotype"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.PHENOTYPE_TO_DISEASES,
            phenotype="HP:0000007",  # Autosomal recessive inheritance
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("phenotype_to_diseases", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_pagination_phenotype(self, integration_adapter):
        """Pagination: Phenotype with many associated diseases"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.PHENOTYPE_TO_DISEASES,
            phenotype="HP:0002664",  # Neoplasm
            limit=15,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("phenotype_to_diseases", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool5CheckPhenotype:
    """Test check_phenotype mode: Check if disease has phenotype"""

    async def test_smoke_diabetes_hyperglycemia(self, integration_adapter):
        """Smoke test: Diabetes + hyperglycemia check"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.CHECK_PHENOTYPE,
            disease="diabetes mellitus",
            phenotype="HP:0003074",  # Hyperglycemia
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("check_phenotype", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_alzheimer_cognitive(self, integration_adapter):
        """Happy path: Alzheimer's + cognitive impairment (should exist)"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.CHECK_PHENOTYPE,
            disease="alzheimer disease",
            phenotype="HP:0100543",  # Cognitive impairment
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("check_phenotype", **query.model_dump(exclude_none=True))

        assert result is not None
        assert isinstance(result, dict)
        # Should indicate relationship exists

    async def test_edge_case_no_relationship(self, integration_adapter):
        """Edge case: Disease-phenotype with no relationship"""
        query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.CHECK_PHENOTYPE,
            disease="diabetes mellitus",
            phenotype="HP:0001250",  # Seizure (unlikely for diabetes)
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("check_phenotype", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should indicate no relationship or very weak

    async def test_multiple_checks(self, integration_adapter):
        """Test multiple phenotype checks for same disease"""
        disease = "parkinson disease"
        phenotypes = [
            "HP:0001337",  # Tremor
            "HP:0002067",  # Bradykinesia
            "HP:0002063",  # Rigidity
        ]

        for phenotype in phenotypes:
            query = DiseasePhenotypeQuery(
                mode=DiseaseQueryMode.CHECK_PHENOTYPE,
                disease=disease,
                phenotype=phenotype,
                response_format=ResponseFormat.JSON,
            )

            result = await integration_adapter.query("check_phenotype", **query.model_dump(exclude_none=True))
            assert result is not None
