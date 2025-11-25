"""
Integration tests for Tool 4: cogex_query_drug_or_effect

Tests 2 modes with smoke, happy path, edge case, and pagination tests.

Run with: pytest tests/integration/test_tool04_drug_integration.py -v -m integration
"""

import pytest

from cogex_mcp.schemas import DrugEffectQuery, DrugQueryMode, ResponseFormat


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool4DrugToProfile:
    """Test drug_to_profile mode: Drug → Targets/Indications/Side Effects"""

    async def test_smoke_aspirin(self, integration_adapter):
        """Smoke test: Aspirin drug profile"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.DRUG_TO_PROFILE,
            drug="aspirin",
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("drug_to_profile", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_imatinib_full_profile(self, integration_adapter):
        """Happy path: Imatinib with full profile"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.DRUG_TO_PROFILE,
            drug="imatinib",
            include_targets=True,
            include_indications=True,
            include_side_effects=True,
            include_trials=True,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("drug_to_profile", **query.model_dump(exclude_none=True))

        # Validate
        assert result is not None
        assert isinstance(result, dict)
        # Imatinib should have known targets (BCR-ABL, etc.)
        assert len(str(result)) > 500

    async def test_edge_case_unknown_drug(self, integration_adapter):
        """Edge case: Unknown/fake drug"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.DRUG_TO_PROFILE,
            drug="fakedrug123456",
            response_format=ResponseFormat.JSON,
        )

        try:
            result = await integration_adapter.query("drug_to_profile", **query.model_dump(exclude_none=True))
            # Should return empty or minimal results
            assert result is not None
        except Exception as e:
            # Should have informative error
            assert "not found" in str(e).lower() or "drug" in str(e).lower()

    async def test_pagination_targets(self, integration_adapter):
        """Pagination: Limit targets in profile"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.DRUG_TO_PROFILE,
            drug="metformin",
            include_targets=True,
            include_indications=False,
            include_side_effects=False,
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("drug_to_profile", **query.model_dump(exclude_none=True))
        assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool4SideEffectToDrugs:
    """Test side_effect_to_drugs mode: Side Effect → Drugs"""

    async def test_smoke_nausea(self, integration_adapter):
        """Smoke test: Nausea side effect"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.SIDE_EFFECT_TO_DRUGS,
            side_effect="nausea",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("side_effect_to_drugs", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_happy_path_headache(self, integration_adapter):
        """Happy path: Headache side effect (common)"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.SIDE_EFFECT_TO_DRUGS,
            side_effect="headache",
            limit=50,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("side_effect_to_drugs", **query.model_dump(exclude_none=True))

        assert result is not None
        assert isinstance(result, dict)

    async def test_edge_case_rare_side_effect(self, integration_adapter):
        """Edge case: Very rare/specific side effect"""
        query = DrugEffectQuery(
            mode=DrugQueryMode.SIDE_EFFECT_TO_DRUGS,
            side_effect="angioedema",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await integration_adapter.query("side_effect_to_drugs", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_pagination_offset(self, integration_adapter):
        """Pagination: Test offset for common side effect"""
        # First page
        query1 = DrugEffectQuery(
            mode=DrugQueryMode.SIDE_EFFECT_TO_DRUGS,
            side_effect="dizziness",
            limit=10,
            offset=0,
            response_format=ResponseFormat.JSON,
        )
        result1 = await integration_adapter.query("side_effect_to_drugs", **query1.model_dump(exclude_none=True))

        # Second page
        query2 = DrugEffectQuery(
            mode=DrugQueryMode.SIDE_EFFECT_TO_DRUGS,
            side_effect="dizziness",
            limit=10,
            offset=10,
            response_format=ResponseFormat.JSON,
        )
        result2 = await integration_adapter.query("side_effect_to_drugs", **query2.model_dump(exclude_none=True))

        assert result1 is not None
        assert result2 is not None
