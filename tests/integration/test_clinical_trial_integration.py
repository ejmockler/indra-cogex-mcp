"""
Integration tests for ClinicalTrialClient.

Tests real queries against live CoGEx Neo4j database.
Validates scientific accuracy and performance.

Run with: pytest tests/integration/test_clinical_trial_integration.py -v --run-integration
"""

import pytest
import time
from typing import List, Dict, Any

# Skip all tests if --run-integration flag not provided
pytestmark = pytest.mark.skipif(
    not pytest.config.getoption("--run-integration", default=False),
    reason="Integration tests require --run-integration flag",
)


@pytest.fixture(scope="module")
def clinical_trial_client():
    """Real ClinicalTrialClient with CoGEx connection."""
    from cogex_mcp.clients.clinical_trial_client import ClinicalTrialClient

    client = ClinicalTrialClient()
    return client


class TestPembrolizumabTrials:
    """Test pembrolizumab (Keytruda) clinical trials."""

    def test_pembrolizumab_trials_basic(self, clinical_trial_client):
        """
        Validate pembrolizumab has clinical trials.

        Expected: Pembrolizumab (PD-1 inhibitor) should have many trials
        for melanoma, NSCLC, etc.
        """
        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",  # Pembrolizumab
        )

        assert result["success"] is True
        assert "trials" in result
        assert result["total_trials"] > 0

        # Should have multiple trials
        assert result["total_trials"] >= 10, "Pembrolizumab should have many trials"

    def test_pembrolizumab_phase3_trials(self, clinical_trial_client):
        """
        Validate pembrolizumab Phase 3 trials.

        Expected: Should have multiple Phase 3 trials for various cancers.
        """
        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",
            phase=[3],
        )

        assert result["success"] is True
        assert result["total_trials"] > 0

        # Verify all are Phase 3
        for trial in result["trials"]:
            assert trial["phase"] is not None
            assert "3" in str(trial["phase"]).lower()

    def test_pembrolizumab_recruiting_trials(self, clinical_trial_client):
        """
        Validate pembrolizumab recruiting trials.

        Expected: Should have some currently recruiting trials.
        """
        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",
            status="Recruiting",
        )

        assert result["success"] is True
        # May or may not have recruiting trials (time-dependent)
        # Just verify query works and returns valid format
        assert "trials" in result
        assert "total_trials" in result


class TestImatinibTrials:
    """Test imatinib (Gleevec) clinical trials."""

    def test_imatinib_trials_basic(self, clinical_trial_client):
        """
        Validate imatinib has clinical trials.

        Expected: Imatinib (BCR-ABL inhibitor) should have trials for CML, GIST.
        """
        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:45783",  # Imatinib
        )

        assert result["success"] is True
        assert result["total_trials"] > 0

        # Should have multiple trials
        assert result["total_trials"] >= 5, "Imatinib should have multiple trials"

    def test_imatinib_phase4_trials(self, clinical_trial_client):
        """
        Validate imatinib Phase 4 trials.

        Expected: Approved drug should have Phase 4 post-marketing trials.
        """
        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:45783",
            phase=[4],
        )

        assert result["success"] is True
        # Should have at least 1 Phase 4 trial
        assert result["total_trials"] >= 1


class TestDiseaseTrials:
    """Test disease-based trial queries."""

    def test_melanoma_trials(self, clinical_trial_client):
        """
        Validate melanoma clinical trials.

        Expected: Melanoma should have many trials (common cancer with active research).
        """
        result = clinical_trial_client.get_disease_trials(
            disease_id="mesh:D008545",  # Melanoma
        )

        assert result["success"] is True
        assert result["total_trials"] > 0

        # Should have many trials
        assert result["total_trials"] >= 20, "Melanoma should have many trials"

    def test_alzheimers_trials(self, clinical_trial_client):
        """
        Validate Alzheimer's disease clinical trials.

        Expected: AD should have many trials (major research area).
        """
        result = clinical_trial_client.get_disease_trials(
            disease_id="mesh:D000544",  # Alzheimer's Disease
        )

        assert result["success"] is True
        assert result["total_trials"] > 0

        # Should have many trials
        assert result["total_trials"] >= 50, "AD should have many trials"

    def test_cml_trials(self, clinical_trial_client):
        """
        Validate CML clinical trials.

        Expected: CML should have trials (well-studied with targeted therapies).
        """
        result = clinical_trial_client.get_disease_trials(
            disease_id="mondo:0011996",  # Chronic Myeloid Leukemia
        )

        assert result["success"] is True
        assert result["total_trials"] > 0


class TestTrialDetails:
    """Test trial details retrieval."""

    def test_known_trial_details(self, clinical_trial_client):
        """
        Test retrieving details for a known trial.

        Note: This test may need to be updated with a current NCT ID.
        """
        # Using a well-known completed trial
        # KEYNOTE-006: Pembrolizumab in Melanoma
        result = clinical_trial_client.get_trial_details(
            trial_id="NCT01866319",
        )

        assert result["success"] is True
        assert result["trial_id"] == "NCT01866319"

        # Should have drugs and diseases
        assert "drugs" in result
        assert "diseases" in result
        assert result["total_drugs"] >= 0  # May be 0 if not in CoGEx
        assert result["total_diseases"] >= 0

    def test_trial_details_lowercase_nct(self, clinical_trial_client):
        """Test trial details with lowercase NCT ID."""
        result = clinical_trial_client.get_trial_details(
            trial_id="nct01866319",  # Lowercase
        )

        assert result["success"] is True
        assert result["trial_id"] == "NCT01866319"  # Should be normalized


class TestPerformance:
    """Test query performance."""

    def test_drug_trials_performance(self, clinical_trial_client):
        """
        Validate drug trials query completes in reasonable time.

        Expected: Query should complete in <3 seconds.
        """
        start_time = time.time()

        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",  # Pembrolizumab
        )

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed < 3.0, f"Query took {elapsed:.2f}s (should be <3s)"

    def test_disease_trials_performance(self, clinical_trial_client):
        """
        Validate disease trials query completes in reasonable time.

        Expected: Query should complete in <3 seconds.
        """
        start_time = time.time()

        result = clinical_trial_client.get_disease_trials(
            disease_id="mesh:D008545",  # Melanoma
        )

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed < 3.0, f"Query took {elapsed:.2f}s (should be <3s)"

    def test_trial_details_performance(self, clinical_trial_client):
        """
        Validate trial details query completes in reasonable time.

        Expected: Query should complete in <2 seconds.
        """
        start_time = time.time()

        result = clinical_trial_client.get_trial_details(
            trial_id="NCT01866319",
        )

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed < 2.0, f"Query took {elapsed:.2f}s (should be <2s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-integration"])
