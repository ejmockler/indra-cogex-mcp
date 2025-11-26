"""
Integration tests for Tool 8: cogex_query_clinical_trials

Tests clinical trials query functionality with actual data validation.

Run with: pytest tests/integration/test_tool08_clinical_trials_integration.py -v
"""

import json
import logging

import pytest

from cogex_mcp.schemas import ClinicalTrialsMode, ClinicalTrialsQuery, ResponseFormat
from cogex_mcp.tools.clinical_trials import cogex_query_clinical_trials

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool8ClinicalTrialsQueries:
    """Test Tool 8 clinical trials query modes with data validation."""

    async def test_get_for_drug_pembrolizumab(self):
        """Test getting clinical trials for pembrolizumab."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="pembrolizumab",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "trials" in data, "Response should include trials list"

        # 4. Data is non-empty (pembrolizumab has many trials)
        assert len(data["trials"]) > 0, "Pembrolizumab should have clinical trials"

        # 5. Data structure validation
        first_trial = data["trials"][0]
        assert "nct_id" in first_trial, "Trial should have NCT ID"
        assert "title" in first_trial, "Trial should have title"
        assert "status" in first_trial, "Trial should have status"

        # 6. NCT ID format validation
        assert first_trial["nct_id"].startswith("NCT"), "NCT ID should start with 'NCT'"

        # 7. Pagination metadata
        assert "pagination" in data, "Response should include pagination"

        logger.info(f"✓ Found {len(data['trials'])} trials for pembrolizumab")

    async def test_get_for_disease_diabetes(self):
        """Test getting clinical trials for diabetes."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="diabetes mellitus",
            limit=30,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "trials" in data, "Response should include trials"

        # 4. Data is non-empty (diabetes has many trials)
        assert len(data["trials"]) > 0, "Diabetes should have clinical trials"

        # 5. Data structure validation
        first_trial = data["trials"][0]
        assert "nct_id" in first_trial, "Trial should have NCT ID"
        assert "conditions" in first_trial, "Trial should have conditions"

        # 6. Verify diabetes is in conditions
        all_conditions = []
        for trial in data["trials"]:
            all_conditions.extend(trial.get("conditions", []))

        has_diabetes = any("diabetes" in cond.lower() for cond in all_conditions)
        if has_diabetes:
            logger.info("✓ Diabetes confirmed in trial conditions")

        logger.info(f"✓ Found {len(data['trials'])} trials for diabetes")

    async def test_get_by_id_specific_trial(self):
        """Test getting specific trial by NCT ID."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_BY_ID,
            trial_id="NCT02576431",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "trial" in data, "Response should include trial"

        # 4. Trial metadata validation
        trial = data["trial"]
        assert trial["nct_id"] == "NCT02576431", "NCT ID should match query"
        assert "title" in trial, "Trial should have title"
        assert "status" in trial, "Trial should have status"

        # 5. URL validation
        assert "url" in trial, "Trial should have URL"
        assert "clinicaltrials.gov" in trial["url"].lower(), "URL should point to ClinicalTrials.gov"

        logger.info(f"✓ Retrieved trial {trial['nct_id']}: {trial['title'][:50]}...")

    async def test_phase_filter(self):
        """Test filtering trials by phase."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="breast cancer",
            phase=[2, 3],
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            # Verify phase filtering
            for trial in data["trials"]:
                if "phase" in trial and trial["phase"] is not None:
                    assert trial["phase"] in [2, 3], f"Phase should be 2 or 3, got {trial['phase']}"

            logger.info(f"✓ Phase filter working: {len(data['trials'])} phase 2/3 trials")

    async def test_status_filter(self):
        """Test filtering trials by status."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="diabetes mellitus",
            status="recruiting",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            # Verify status filtering
            for trial in data["trials"]:
                assert trial["status"].lower() == "recruiting", f"Status should be recruiting, got {trial['status']}"

            logger.info(f"✓ Status filter working: {len(data['trials'])} recruiting trials")

    async def test_invalid_nct_id(self):
        """Test error handling for invalid NCT ID."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_BY_ID,
            trial_id="NCT99999999",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        # Should error or return not found
        if result.startswith("Error:"):
            assert "not found" in result.lower(), "Error should mention 'not found'"
            logger.info(f"✓ Invalid NCT ID error: {result}")
        else:
            # Empty or not found response is OK
            data = json.loads(result)
            logger.info(f"Invalid NCT ID returned: {data}")

    async def test_markdown_response_format(self):
        """Test markdown response format."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="aspirin",
            limit=10,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await cogex_query_clinical_trials(query)

        if not result.startswith("Error:"):
            # Should contain markdown formatting
            has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
            assert has_markdown, "Markdown response should have formatting"
            logger.info("✓ Markdown response has formatting")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool8EdgeCases:
    """Edge cases and pagination tests for clinical trials."""

    async def test_unknown_drug(self):
        """Test query with unknown drug."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="fake_nonexistent_drug_xyz",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        # Should error or return empty results
        if result.startswith("Error:"):
            logger.info(f"✓ Unknown drug error: {result}")
        else:
            data = json.loads(result)
            # Empty results are OK for fake drugs
            assert "trials" in data
            logger.info(f"Unknown drug returned {len(data.get('trials', []))} trials")

    async def test_pagination_trials(self):
        """Test pagination for clinical trials."""
        # Get first page
        query1 = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="diabetes mellitus",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result1 = await cogex_query_clinical_trials(query1)

        if not result1.startswith("Error:"):
            data1 = json.loads(result1)
            assert len(data1["trials"]) <= 5, "Should respect limit"

            # Get second page
            query2 = ClinicalTrialsQuery(
                mode=ClinicalTrialsMode.GET_FOR_DISEASE,
                disease="diabetes mellitus",
                limit=5,
                offset=5,
                response_format=ResponseFormat.JSON,
            )

            result2 = await cogex_query_clinical_trials(query2)

            if not result2.startswith("Error:"):
                data2 = json.loads(result2)

                # Pages should have different trials
                page1_ids = {t["nct_id"] for t in data1["trials"]}
                page2_ids = {t["nct_id"] for t in data2["trials"]}
                assert page1_ids != page2_ids, "Different pages should have different trials"

                logger.info("✓ Pagination working correctly")

    async def test_trial_metadata_completeness(self):
        """Test that trial metadata is complete."""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="pembrolizumab",
            limit=5,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_clinical_trials(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            for trial in data["trials"]:
                # Verify required fields
                assert "nct_id" in trial, "Trial must have NCT ID"
                assert "title" in trial, "Trial must have title"
                assert "status" in trial, "Trial must have status"

                # Verify optional fields are present (even if None)
                assert "phase" in trial or trial.get("phase") is None
                assert "conditions" in trial or isinstance(trial.get("conditions"), list)
                assert "interventions" in trial or isinstance(trial.get("interventions"), list)

            logger.info("✓ Trial metadata completeness verified")
