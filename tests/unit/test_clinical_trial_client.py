"""
Unit tests for ClinicalTrialClient.

Tests all methods with mocked Neo4j client and CoGEx functions.
Achieves >90% code coverage without requiring real Neo4j connection.

Run with: pytest tests/unit/test_clinical_trial_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for testing."""
    mock_client = MagicMock()
    mock_client.query_tx = MagicMock(return_value=[])
    return mock_client


@pytest.fixture
def clinical_trial_client(mock_neo4j_client):
    """ClinicalTrialClient instance with mocked Neo4j."""
    from cogex_mcp.clients.clinical_trial_client import ClinicalTrialClient

    return ClinicalTrialClient(neo4j_client=mock_neo4j_client)


@pytest.fixture
def pembrolizumab_trials_data():
    """
    Mock data for pembrolizumab (Keytruda) clinical trials.

    Immune checkpoint inhibitor for various cancers.
    """
    return [
        {
            "nct_id": "NCT02603432",
            "title": "Pembrolizumab in Melanoma",
            "phase": "Phase 3",
            "status": "Completed",
            "conditions": ["Melanoma"],
            "interventions": ["Pembrolizumab"],
            "enrollment": 834,
            "start_date": "2015-11-01",
            "completion_date": "2018-06-30",
        },
        {
            "nct_id": "NCT02142738",
            "title": "Pembrolizumab vs Chemotherapy in NSCLC",
            "phase": "Phase 3",
            "status": "Completed",
            "conditions": ["Non-small Cell Lung Cancer"],
            "interventions": ["Pembrolizumab", "Chemotherapy"],
            "enrollment": 305,
            "start_date": "2014-05-01",
            "completion_date": "2016-12-31",
        },
        {
            "nct_id": "NCT03475004",
            "title": "Pembrolizumab in Early Triple-Negative Breast Cancer",
            "phase": "Phase 3",
            "status": "Recruiting",
            "conditions": ["Triple Negative Breast Cancer"],
            "interventions": ["Pembrolizumab", "Chemotherapy"],
            "enrollment": 1174,
            "start_date": "2018-03-01",
        },
    ]


@pytest.fixture
def imatinib_trials_data():
    """Mock data for imatinib (Gleevec) clinical trials."""
    return [
        {
            "nct_id": "NCT00070499",
            "title": "Imatinib in Chronic Myeloid Leukemia",
            "phase": "Phase 4",
            "status": "Completed",
            "conditions": ["Chronic Myeloid Leukemia"],
            "interventions": ["Imatinib"],
            "enrollment": 1106,
            "start_date": "2003-10-01",
            "completion_date": "2012-03-31",
        },
        {
            "nct_id": "NCT00373022",
            "title": "Imatinib in GIST",
            "phase": "Phase 3",
            "status": "Completed",
            "conditions": ["Gastrointestinal Stromal Tumor"],
            "interventions": ["Imatinib"],
            "enrollment": 908,
            "start_date": "2006-09-01",
            "completion_date": "2014-06-30",
        },
    ]


@pytest.fixture
def trial_details_data():
    """Mock data for trial details (drugs and diseases)."""
    return {
        "drugs": [
            {
                "namespace": "chebi",
                "identifier": "164898",
                "name": "Pembrolizumab",
            }
        ],
        "diseases": [
            {
                "namespace": "mesh",
                "identifier": "D008545",
                "name": "Melanoma",
            },
            {
                "namespace": "mesh",
                "identifier": "D018358",
                "name": "Neuroendocrine Tumors",
            },
        ],
    }


class TestClinicalTrialClientInit:
    """Test ClinicalTrialClient initialization."""

    def test_init_with_client(self, mock_neo4j_client):
        """Test initialization with provided Neo4j client."""
        from cogex_mcp.clients.clinical_trial_client import ClinicalTrialClient

        client = ClinicalTrialClient(neo4j_client=mock_neo4j_client)
        assert client.client == mock_neo4j_client

    def test_init_without_client(self):
        """Test initialization without Neo4j client (uses autoclient)."""
        from cogex_mcp.clients.clinical_trial_client import ClinicalTrialClient

        client = ClinicalTrialClient()
        assert client.client is None


class TestParsingMethods:
    """Test helper methods for parsing trial identifiers."""

    def test_parse_trial_id_chebi(self, clinical_trial_client):
        """Test parsing drug CURIE."""
        curie = "chebi:164898"
        namespace, identifier = clinical_trial_client._parse_trial_id(curie)

        assert namespace == "CHEBI"
        assert identifier == "164898"

    def test_parse_trial_id_mesh(self, clinical_trial_client):
        """Test parsing disease CURIE."""
        curie = "mesh:D008545"
        namespace, identifier = clinical_trial_client._parse_trial_id(curie)

        assert namespace == "MESH"
        assert identifier == "D008545"

    def test_parse_nct_id_uppercase(self, clinical_trial_client):
        """Test parsing uppercase NCT ID."""
        nct_id = clinical_trial_client._parse_nct_id("NCT02603432")
        assert nct_id == "NCT02603432"

    def test_parse_nct_id_lowercase(self, clinical_trial_client):
        """Test parsing lowercase NCT ID."""
        nct_id = clinical_trial_client._parse_nct_id("nct02603432")
        assert nct_id == "NCT02603432"

    def test_parse_nct_id_numbers_only(self, clinical_trial_client):
        """Test parsing NCT ID without prefix."""
        nct_id = clinical_trial_client._parse_nct_id("02603432")
        assert nct_id == "NCT02603432"

    def test_parse_nct_id_with_whitespace(self, clinical_trial_client):
        """Test parsing NCT ID with whitespace."""
        nct_id = clinical_trial_client._parse_nct_id("  NCT02603432  ")
        assert nct_id == "NCT02603432"


class TestGetDrugTrials:
    """Test getting clinical trials for a drug."""

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_drug")
    def test_get_drug_trials_basic(
        self, mock_get_trials, clinical_trial_client, pembrolizumab_trials_data
    ):
        """Test basic drug trials retrieval."""
        mock_get_trials.return_value = pembrolizumab_trials_data

        result = clinical_trial_client.get_drug_trials(drug_id="chebi:164898")

        assert result["success"] is True
        assert len(result["trials"]) == 3
        assert result["drug_id"] == "chebi:164898"
        assert result["total_trials"] == 3

        # Verify first trial
        first_trial = result["trials"][0]
        assert first_trial["nct_id"] == "NCT02603432"
        assert first_trial["title"] == "Pembrolizumab in Melanoma"
        assert first_trial["phase"] == "Phase 3"
        assert first_trial["status"] == "Completed"

        # Verify CoGEx function called correctly
        mock_get_trials.assert_called_once()

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_drug")
    def test_get_drug_trials_with_phase_filter(
        self, mock_get_trials, clinical_trial_client, pembrolizumab_trials_data
    ):
        """Test filtering drug trials by phase."""
        mock_get_trials.return_value = pembrolizumab_trials_data

        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",
            phase=[3],
        )

        assert result["success"] is True
        assert len(result["trials"]) == 3  # All are Phase 3
        assert result["total_trials"] == 3

        # All should be Phase 3
        for trial in result["trials"]:
            assert "3" in trial["phase"]

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_drug")
    def test_get_drug_trials_with_status_filter(
        self, mock_get_trials, clinical_trial_client, pembrolizumab_trials_data
    ):
        """Test filtering drug trials by status."""
        mock_get_trials.return_value = pembrolizumab_trials_data

        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",
            status="Completed",
        )

        assert result["success"] is True
        assert len(result["trials"]) == 2  # 2 completed trials
        assert result["total_trials"] == 2

        # All should be Completed
        for trial in result["trials"]:
            assert "Completed" in trial["status"]

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_drug")
    def test_get_drug_trials_with_both_filters(
        self, mock_get_trials, clinical_trial_client, pembrolizumab_trials_data
    ):
        """Test filtering drug trials by both phase and status."""
        mock_get_trials.return_value = pembrolizumab_trials_data

        result = clinical_trial_client.get_drug_trials(
            drug_id="chebi:164898",
            phase=[3],
            status="Recruiting",
        )

        assert result["success"] is True
        assert len(result["trials"]) == 1  # Only 1 Phase 3 recruiting trial
        assert result["trials"][0]["nct_id"] == "NCT03475004"

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_drug")
    def test_get_drug_trials_empty_result(self, mock_get_trials, clinical_trial_client):
        """Test handling of drug with no clinical trials."""
        mock_get_trials.return_value = []

        result = clinical_trial_client.get_drug_trials(drug_id="chebi:99999")

        assert result["success"] is True
        assert len(result["trials"]) == 0
        assert result["total_trials"] == 0


class TestGetDiseaseTrials:
    """Test getting clinical trials for a disease."""

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_disease")
    def test_get_disease_trials_basic(
        self, mock_get_trials, clinical_trial_client, pembrolizumab_trials_data
    ):
        """Test basic disease trials retrieval."""
        mock_get_trials.return_value = pembrolizumab_trials_data

        result = clinical_trial_client.get_disease_trials(disease_id="mesh:D008545")

        assert result["success"] is True
        assert len(result["trials"]) == 3
        assert result["disease_id"] == "mesh:D008545"
        assert result["total_trials"] == 3

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_disease")
    def test_get_disease_trials_with_phase_filter(
        self, mock_get_trials, clinical_trial_client, imatinib_trials_data
    ):
        """Test filtering disease trials by phase."""
        mock_get_trials.return_value = imatinib_trials_data

        result = clinical_trial_client.get_disease_trials(
            disease_id="mondo:0011996",
            phase=[4],
        )

        assert result["success"] is True
        assert len(result["trials"]) == 1  # Only 1 Phase 4 trial
        assert result["trials"][0]["nct_id"] == "NCT00070499"

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_disease")
    def test_get_disease_trials_with_status_filter(
        self, mock_get_trials, clinical_trial_client, imatinib_trials_data
    ):
        """Test filtering disease trials by status."""
        mock_get_trials.return_value = imatinib_trials_data

        result = clinical_trial_client.get_disease_trials(
            disease_id="mondo:0011996",
            status="Completed",
        )

        assert result["success"] is True
        assert len(result["trials"]) == 2  # Both are completed

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_disease")
    def test_get_disease_trials_empty_result(
        self, mock_get_trials, clinical_trial_client
    ):
        """Test handling of disease with no clinical trials."""
        mock_get_trials.return_value = []

        result = clinical_trial_client.get_disease_trials(disease_id="mesh:D999999")

        assert result["success"] is True
        assert len(result["trials"]) == 0
        assert result["total_trials"] == 0


class TestGetTrialDetails:
    """Test getting details for a specific trial."""

    @patch("cogex_mcp.clients.clinical_trial_client.get_diseases_for_trial")
    @patch("cogex_mcp.clients.clinical_trial_client.get_drugs_for_trial")
    def test_get_trial_details_basic(
        self,
        mock_get_drugs,
        mock_get_diseases,
        clinical_trial_client,
        trial_details_data,
    ):
        """Test basic trial details retrieval."""
        mock_get_drugs.return_value = trial_details_data["drugs"]
        mock_get_diseases.return_value = trial_details_data["diseases"]

        result = clinical_trial_client.get_trial_details(trial_id="NCT02603432")

        assert result["success"] is True
        assert result["trial_id"] == "NCT02603432"
        assert len(result["drugs"]) == 1
        assert len(result["diseases"]) == 2
        assert result["total_drugs"] == 1
        assert result["total_diseases"] == 2

        # Verify drug
        drug = result["drugs"][0]
        assert drug["drug_id"] == "chebi:164898"
        assert drug["drug_name"] == "Pembrolizumab"

        # Verify diseases
        disease_ids = [d["disease_id"] for d in result["diseases"]]
        assert "mesh:D008545" in disease_ids
        assert "mesh:D018358" in disease_ids

    @patch("cogex_mcp.clients.clinical_trial_client.get_diseases_for_trial")
    @patch("cogex_mcp.clients.clinical_trial_client.get_drugs_for_trial")
    def test_get_trial_details_lowercase_nct(
        self,
        mock_get_drugs,
        mock_get_diseases,
        clinical_trial_client,
        trial_details_data,
    ):
        """Test trial details with lowercase NCT ID."""
        mock_get_drugs.return_value = trial_details_data["drugs"]
        mock_get_diseases.return_value = trial_details_data["diseases"]

        result = clinical_trial_client.get_trial_details(trial_id="nct02603432")

        assert result["success"] is True
        assert result["trial_id"] == "NCT02603432"  # Should be normalized

    @patch("cogex_mcp.clients.clinical_trial_client.get_diseases_for_trial")
    @patch("cogex_mcp.clients.clinical_trial_client.get_drugs_for_trial")
    def test_get_trial_details_empty_drugs(
        self, mock_get_drugs, mock_get_diseases, clinical_trial_client
    ):
        """Test trial with no drugs (e.g., behavioral intervention)."""
        mock_get_drugs.return_value = []
        mock_get_diseases.return_value = trial_details_data["diseases"]

        result = clinical_trial_client.get_trial_details(trial_id="NCT02603432")

        assert result["success"] is True
        assert len(result["drugs"]) == 0
        assert result["total_drugs"] == 0

    @patch("cogex_mcp.clients.clinical_trial_client.get_diseases_for_trial")
    @patch("cogex_mcp.clients.clinical_trial_client.get_drugs_for_trial")
    def test_get_trial_details_empty_diseases(
        self, mock_get_drugs, mock_get_diseases, clinical_trial_client
    ):
        """Test trial with no diseases (e.g., healthy volunteer study)."""
        mock_get_drugs.return_value = trial_details_data["drugs"]
        mock_get_diseases.return_value = []

        result = clinical_trial_client.get_trial_details(trial_id="NCT02603432")

        assert result["success"] is True
        assert len(result["diseases"]) == 0
        assert result["total_diseases"] == 0


class TestHelperMethods:
    """Test helper methods."""

    def test_filter_by_phase_numeric(self, clinical_trial_client):
        """Test filtering by phase with numeric phase values."""
        trials = [
            {"nct_id": "NCT001", "phase": 1},
            {"nct_id": "NCT002", "phase": 2},
            {"nct_id": "NCT003", "phase": 3},
        ]

        filtered = clinical_trial_client._filter_by_phase(trials, [2, 3])

        assert len(filtered) == 2
        assert filtered[0]["nct_id"] == "NCT002"
        assert filtered[1]["nct_id"] == "NCT003"

    def test_filter_by_phase_string(self, clinical_trial_client):
        """Test filtering by phase with string phase values."""
        trials = [
            {"nct_id": "NCT001", "phase": "Phase 1"},
            {"nct_id": "NCT002", "phase": "Phase 2"},
            {"nct_id": "NCT003", "phase": "Phase 3"},
        ]

        filtered = clinical_trial_client._filter_by_phase(trials, [3])

        assert len(filtered) == 1
        assert filtered[0]["nct_id"] == "NCT003"

    def test_filter_by_status_case_insensitive(self, clinical_trial_client):
        """Test status filtering is case-insensitive."""
        trials = [
            {"nct_id": "NCT001", "status": "Recruiting"},
            {"nct_id": "NCT002", "status": "RECRUITING"},
            {"nct_id": "NCT003", "status": "Completed"},
        ]

        filtered = clinical_trial_client._filter_by_status(trials, "recruiting")

        assert len(filtered) == 2

    def test_format_trial_dict_complete(self, clinical_trial_client):
        """Test formatting complete trial dict."""
        trial = {
            "nct_id": "NCT02603432",
            "title": "Test Trial",
            "phase": "Phase 3",
            "status": "Recruiting",
            "conditions": ["Melanoma"],
            "interventions": ["Pembrolizumab"],
            "enrollment": 100,
            "start_date": "2020-01-01",
            "completion_date": "2022-12-31",
            "sponsor": "Test Sponsor",
        }

        formatted = clinical_trial_client._format_trial_dict(trial)

        assert formatted["nct_id"] == "NCT02603432"
        assert formatted["title"] == "Test Trial"
        assert formatted["phase"] == "Phase 3"
        assert formatted["status"] == "Recruiting"
        assert formatted["conditions"] == ["Melanoma"]
        assert formatted["interventions"] == ["Pembrolizumab"]
        assert formatted["enrollment"] == 100
        assert formatted["start_date"] == "2020-01-01"
        assert formatted["completion_date"] == "2022-12-31"
        assert formatted["sponsor"] == "Test Sponsor"

    def test_format_trial_dict_minimal(self, clinical_trial_client):
        """Test formatting minimal trial dict."""
        trial = {
            "nct_id": "NCT02603432",
            "title": "Test Trial",
        }

        formatted = clinical_trial_client._format_trial_dict(trial)

        assert formatted["nct_id"] == "NCT02603432"
        assert formatted["title"] == "Test Trial"
        assert formatted["phase"] is None
        assert formatted["status"] == "unknown"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_trial_id_no_colon(self, clinical_trial_client):
        """Test parsing identifier without namespace."""
        namespace, identifier = clinical_trial_client._parse_trial_id("164898")

        assert namespace == "UNKNOWN"
        assert identifier == "164898"

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_drug")
    def test_get_drug_trials_with_missing_fields(
        self, mock_get_trials, clinical_trial_client
    ):
        """Test handling of trial data with missing fields."""
        incomplete_data = [
            {
                "nct_id": "NCT001",
                # Missing title, phase, status
            }
        ]
        mock_get_trials.return_value = incomplete_data

        result = clinical_trial_client.get_drug_trials(drug_id="chebi:164898")

        assert result["success"] is True
        assert len(result["trials"]) == 1
        trial = result["trials"][0]
        assert trial["title"] == "Unknown"
        assert trial["phase"] is None
        assert trial["status"] == "unknown"

    @patch("cogex_mcp.clients.clinical_trial_client.get_trials_for_disease")
    def test_get_disease_trials_with_null_phase(
        self, mock_get_trials, clinical_trial_client
    ):
        """Test handling of trial without phase."""
        data_with_null_phase = [
            {
                "nct_id": "NCT001",
                "title": "Test",
                "phase": None,
                "status": "Recruiting",
            }
        ]
        mock_get_trials.return_value = data_with_null_phase

        result = clinical_trial_client.get_disease_trials(
            disease_id="mesh:D008545",
            phase=[3],
        )

        # Should filter out trial with null phase
        assert result["success"] is True
        assert len(result["trials"]) == 0


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--cov=cogex_mcp.clients.clinical_trial_client",
        "--cov-report=term-missing",
    ])
