"""
Integration tests for Tool 8/15 (cogex_query_clinical_trials) with live backends.

Note: This is Tool 8 in implementation but tested as Tool 15 in the sequence.

Tests complete flow: Tool → Entity Resolver → Adapter → Backends → Response

Critical validation pattern:
1. No errors
2. Parse response
3. Validate structure
4. Validate data exists
5. Validate data quality
"""

import json
import logging

import pytest

from cogex_mcp.schemas import ClinicalTrialsMode, ClinicalTrialsQuery, ResponseFormat
from cogex_mcp.tools.clinical_trials import cogex_query_clinical_trials

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15DrugTrials:
    """Test drug → clinical trials queries."""

    async def test_pembrolizumab_trials(self):
        """
        Get clinical trials for pembrolizumab (cancer immunotherapy).

        Validates:
        - Drug to trials lookup works
        - Returns trial data
        - Data structure is correct
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="pembrolizumab",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        # Step 1: No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Step 2: Parse response
        data = json.loads(result)

        # Step 3: Validate structure
        assert "trials" in data, "Response should have trials"
        assert "pagination" in data, "Response should have pagination"

        # Step 4: Validate data exists
        # Pembrolizumab is widely studied, should have trials
        assert len(data["trials"]) > 0, "Pembrolizumab should have clinical trials"

        # Step 5: Validate data quality
        for trial in data["trials"]:
            assert "nct_id" in trial, "Trial should have NCT ID"
            assert trial["nct_id"], "NCT ID should not be empty"
            assert trial["nct_id"].startswith("NCT"), f"NCT ID should start with 'NCT': {trial['nct_id']}"
            assert "title" in trial, "Trial should have title"
            assert "status" in trial, "Trial should have status"

        logger.info(f"✓ Pembrolizumab: {len(data['trials'])} trials found")

    async def test_aspirin_trials(self):
        """
        Get trials for aspirin.

        Tests common drug with many trials.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="aspirin",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Aspirin not found or no trials")

        data = json.loads(result)
        assert "trials" in data

        logger.info(f"✓ Aspirin: {len(data['trials'])} trials")

    async def test_drug_by_curie(self):
        """
        Query trials using drug CURIE.

        Validates CURIE resolution.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="CHEBI:6801",  # metformin
            limit=10,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Drug CURIE not supported or not found")

        data = json.loads(result)
        assert "trials" in data

        logger.info(f"✓ Drug CURIE query: {len(data['trials'])} trials")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15DiseaseTrials:
    """Test disease → clinical trials queries."""

    async def test_alzheimer_trials(self):
        """
        Get clinical trials for Alzheimer's disease.

        Well-studied disease with many trials.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="alzheimer disease",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "trials" in data
        assert "pagination" in data

        # Alzheimer's has many active trials
        assert len(data["trials"]) > 0, "Alzheimer's should have clinical trials"

        # Validate trial structure
        for trial in data["trials"]:
            assert "nct_id" in trial
            assert trial["nct_id"].startswith("NCT")
            assert "conditions" in trial or "title" in trial

        logger.info(f"✓ Alzheimer's disease: {len(data['trials'])} trials")

    async def test_breast_cancer_trials(self):
        """
        Get trials for breast cancer.

        Common cancer with extensive trials.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="breast cancer",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "trials" in data
        assert len(data["trials"]) > 0, "Breast cancer should have many trials"

        logger.info(f"✓ Breast cancer: {len(data['trials'])} trials")

    async def test_diabetes_trials(self):
        """
        Get trials for diabetes.

        Tests metabolic disease trials.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="diabetes mellitus",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Diabetes not found or no trials")

        data = json.loads(result)
        assert "trials" in data

        logger.info(f"✓ Diabetes: {len(data['trials'])} trials")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15TrialByID:
    """Test get_by_id mode for specific trial lookup."""

    async def test_get_trial_by_nct_id(self):
        """
        Get trial details by NCT ID.

        Tests direct trial lookup.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_BY_ID,
            trial_id="NCT02576431",  # Example trial
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Trial ID not found or mode not supported")

        data = json.loads(result)
        assert "trial" in data, "Response should have trial object"

        trial = data["trial"]
        assert "nct_id" in trial
        assert trial["nct_id"] == "NCT02576431"

        # Validate trial details
        expected_fields = ["title", "status", "conditions", "interventions"]
        for field in expected_fields:
            if field in trial:
                logger.info(f"  {field}: present")

        logger.info(f"✓ Trial NCT02576431 details retrieved")

    async def test_invalid_nct_id(self):
        """
        Invalid NCT ID should error or return not found.

        Validates error handling.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_BY_ID,
            trial_id="NCT99999999",  # Invalid
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            logger.info(f"✓ Invalid NCT ID error: {result}")
        else:
            # May return empty or not found response
            data = json.loads(result)
            logger.info("✓ Invalid NCT ID handled gracefully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15Filters:
    """Test trial filtering by phase and status."""

    async def test_filter_by_phase(self):
        """
        Filter trials by phase (3, 4).

        Validates phase filtering.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="cancer",
            phase=[3, 4],  # Only phase 3 and 4 trials
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:") and "not supported" in result.lower():
            pytest.skip("Phase filtering not supported")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "trials" in data

        # Verify phase filtering
        for trial in data["trials"]:
            if "phase" in trial and trial["phase"] is not None:
                assert trial["phase"] in [3, 4], f"Trial phase should be 3 or 4, got {trial['phase']}"

        logger.info(f"✓ Phase filter: {len(data['trials'])} phase 3/4 trials")

    async def test_filter_by_status(self):
        """
        Filter trials by recruitment status.

        Validates status filtering.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="alzheimer disease",
            status="recruiting",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:") and "not supported" in result.lower():
            pytest.skip("Status filtering not supported")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "trials" in data

        # Verify status filtering
        for trial in data["trials"]:
            if "status" in trial:
                # Status might be "recruiting" or "Recruiting" or similar
                assert "recruit" in trial["status"].lower(), f"Expected recruiting status, got {trial['status']}"

        logger.info(f"✓ Status filter: {len(data['trials'])} recruiting trials")

    async def test_combined_filters(self):
        """
        Test combining phase and status filters.

        Validates filter combination.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="pembrolizumab",
            phase=[3],
            status="recruiting",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:") and "not supported" in result.lower():
            pytest.skip("Combined filters not supported")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "trials" in data

        logger.info(f"✓ Combined filters: {len(data['trials'])} trials")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15DataQuality:
    """Test trial data quality and completeness."""

    async def test_trial_metadata_completeness(self):
        """
        Trial results should have complete metadata.

        Validates data quality.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="metformin",
            limit=5,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Drug not found")

        data = json.loads(result)

        if len(data["trials"]) > 0:
            for trial in data["trials"]:
                # Required fields
                assert "nct_id" in trial
                assert trial["nct_id"], "NCT ID should not be empty"

                # Check for expected fields
                expected_fields = ["title", "status", "conditions", "interventions", "url"]
                found_fields = [f for f in expected_fields if f in trial]

                logger.info(f"  Trial {trial['nct_id']}: {len(found_fields)}/{len(expected_fields)} fields")

                # URL should be valid ClinicalTrials.gov link
                if "url" in trial:
                    assert "clinicaltrials.gov" in trial["url"].lower()

            logger.info("✓ Trial metadata validated")

    async def test_trial_url_format(self):
        """
        Trial URLs should point to ClinicalTrials.gov.

        Validates URL construction.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="cancer",
            limit=3,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Disease not found")

        data = json.loads(result)

        for trial in data["trials"]:
            if "url" in trial:
                url = trial["url"]
                assert url.startswith("http"), "URL should be valid HTTP(S)"
                assert "clinicaltrials.gov" in url.lower(), "URL should be ClinicalTrials.gov"
                assert trial["nct_id"] in url, "URL should contain NCT ID"

                logger.info(f"✓ Valid URL: {url}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15EdgeCases:
    """Test edge cases and error handling."""

    async def test_unknown_drug(self):
        """
        Unknown drug should return error.

        Validates error handling.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="FAKEDRUG999",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        assert result.startswith("Error:"), "Unknown drug should error"
        assert "not found" in result.lower()

        logger.info(f"✓ Unknown drug error: {result}")

    async def test_unknown_disease(self):
        """
        Unknown disease should return error.

        Validates error handling.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="FAKEDISEASE999",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        assert result.startswith("Error:"), "Unknown disease should error"
        logger.info(f"✓ Unknown disease error: {result}")

    async def test_pagination(self):
        """
        Test pagination parameters.

        Validates limit and offset.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="cancer",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "trials" in data
        assert len(data["trials"]) <= 5, "Should respect limit parameter"

        # Check pagination metadata
        if "pagination" in data:
            assert "limit" in data["pagination"]
            assert "offset" in data["pagination"]

        logger.info(f"✓ Pagination: {len(data['trials'])} trials returned")

    async def test_markdown_format(self):
        """
        Test markdown output format.

        Validates alternative response format.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="alzheimer",
            limit=5,
            response_format=ResponseFormat.MARKDOWN
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Disease not found")

        # Should contain markdown formatting
        has_markdown = any(marker in result for marker in ["##", "**", "|", "-", "NCT"])
        assert has_markdown, "Markdown should contain formatting or NCT IDs"

        logger.info("✓ Markdown format validated")

    async def test_empty_results_handling(self):
        """
        Query with no results should return gracefully.

        Tests empty result handling.
        """
        # Use very specific/rare disease that may have no trials
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="extremely rare disease xyz",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            # Error is acceptable for unknown disease
            logger.info("✓ Unknown disease handled with error")
        else:
            # Or should return empty trials list
            data = json.loads(result)
            assert "trials" in data
            assert isinstance(data["trials"], list)
            logger.info(f"✓ Empty results: {len(data['trials'])} trials")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool15Statistics:
    """Test trial statistics and counts."""

    async def test_trial_count_accuracy(self):
        """
        Pagination should report accurate total counts.

        Validates pagination metadata.
        """
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="cancer",
            limit=10,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_clinical_trials(query)

        if result.startswith("Error:"):
            pytest.skip("Disease not found")

        data = json.loads(result)

        if "pagination" in data:
            pagination = data["pagination"]

            if "total_count" in pagination:
                assert pagination["total_count"] >= len(data["trials"]), \
                    "Total count should be >= current page count"

            logger.info(f"✓ Pagination stats: {pagination}")
