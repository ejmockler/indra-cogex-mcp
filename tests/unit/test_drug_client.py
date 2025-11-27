"""
Unit tests for DrugClient.

Tests all methods with mocked Neo4j client and CoGEx functions.
Achieves >90% code coverage without requiring real Neo4j connection.

Run with: pytest tests/unit/test_drug_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for testing."""
    mock_client = MagicMock()
    mock_client.query_tx = MagicMock(return_value=[])
    return mock_client


@pytest.fixture
def drug_client(mock_neo4j_client):
    """DrugClient instance with mocked Neo4j."""
    from cogex_mcp.clients.drug_client import DrugClient

    return DrugClient(neo4j_client=mock_neo4j_client)


@pytest.fixture
def imatinib_targets_data():
    """
    Mock data for imatinib (Gleevec) targets.

    Known targets: ABL1 (BCR-ABL fusion), KIT (c-Kit), PDGFR
    """
    return [
        {
            "target": "ABL1",
            "target_id": "hgnc:76",
            "target_namespace": "hgnc",
            "action_type": "inhibitor",
            "evidence_count": 150,
        },
        {
            "target": "KIT",
            "target_id": "hgnc:6342",
            "target_namespace": "hgnc",
            "action_type": "inhibitor",
            "evidence_count": 89,
        },
        {
            "target": "PDGFRA",
            "target_id": "hgnc:8803",
            "target_namespace": "hgnc",
            "action_type": "inhibitor",
            "evidence_count": 72,
        },
    ]


@pytest.fixture
def imatinib_indications_data():
    """Mock data for imatinib indications."""
    return [
        {
            "disease": "chronic myeloid leukemia",
            "disease_id": "mondo:0011996",
            "disease_namespace": "mondo",
            "indication_type": "approved",
            "max_phase": 4,
        },
        {
            "disease": "gastrointestinal stromal tumor",
            "disease_id": "mondo:0011719",
            "disease_namespace": "mondo",
            "indication_type": "approved",
            "max_phase": 4,
        },
    ]


@pytest.fixture
def aspirin_side_effects_data():
    """Mock data for aspirin side effects."""
    return [
        {
            "effect": "gastrointestinal hemorrhage",
            "effect_id": "umls:C0017181",
            "effect_namespace": "umls",
            "frequency": "common",
        },
        {
            "effect": "peptic ulcer",
            "effect_id": "umls:C0030920",
            "effect_namespace": "umls",
            "frequency": "uncommon",
        },
        {
            "effect": "tinnitus",
            "effect_id": "umls:C0040264",
            "effect_namespace": "umls",
            "frequency": "rare",
        },
    ]


@pytest.fixture
def pembrolizumab_profile_data():
    """
    Complete profile for pembrolizumab (Keytruda).

    Immune checkpoint inhibitor targeting PD-1.
    """
    return {
        "targets": [
            {
                "target": "PDCD1",
                "target_id": "hgnc:8760",
                "target_namespace": "hgnc",
                "action_type": "antibody",
                "evidence_count": 200,
            }
        ],
        "indications": [
            {
                "disease": "melanoma",
                "disease_id": "mondo:0005012",
                "disease_namespace": "mondo",
                "indication_type": "approved",
                "max_phase": 4,
            },
            {
                "disease": "non-small cell lung cancer",
                "disease_id": "mondo:0005233",
                "disease_namespace": "mondo",
                "indication_type": "approved",
                "max_phase": 4,
            },
        ],
        "side_effects": [
            {
                "effect": "fatigue",
                "effect_id": "umls:C0015672",
                "effect_namespace": "umls",
                "frequency": "very common",
            },
            {
                "effect": "diarrhea",
                "effect_id": "umls:C0011991",
                "effect_namespace": "umls",
                "frequency": "common",
            },
        ],
    }


class TestDrugClientInit:
    """Test DrugClient initialization."""

    def test_init_with_client(self, mock_neo4j_client):
        """Test initialization with provided Neo4j client."""
        from cogex_mcp.clients.drug_client import DrugClient

        client = DrugClient(neo4j_client=mock_neo4j_client)
        assert client.client == mock_neo4j_client

    def test_init_without_client(self):
        """Test initialization without Neo4j client (uses autoclient)."""
        from cogex_mcp.clients.drug_client import DrugClient

        client = DrugClient()
        assert client.client is None


class TestParsingMethods:
    """Test helper methods for parsing drug/target identifiers."""

    def test_parse_drug_curie(self, drug_client):
        """Test parsing drug CURIE to tuple."""
        curie = "chebi:45783"
        namespace, identifier = drug_client._parse_curie(curie)

        assert namespace == "CHEBI"
        assert identifier == "45783"

    def test_parse_drug_curie_drugbank(self, drug_client):
        """Test parsing DrugBank CURIE."""
        curie = "drugbank:DB00619"
        namespace, identifier = drug_client._parse_curie(curie)

        assert namespace == "DRUGBANK"
        assert identifier == "DB00619"

    def test_parse_curie_uppercase_namespace(self, drug_client):
        """Test that namespace is uppercased."""
        curie = "mesh:D001241"
        namespace, identifier = drug_client._parse_curie(curie)

        assert namespace == "MESH"
        assert identifier == "D001241"

    def test_parse_curie_invalid_raises_error(self, drug_client):
        """Test that invalid CURIE raises ValueError."""
        with pytest.raises(ValueError, match="Invalid CURIE format"):
            drug_client._parse_curie("invalid_curie_no_colon")

    def test_parse_target_id_with_curie(self, drug_client):
        """Test parsing target gene CURIE."""
        target_id = "hgnc:76"
        namespace, identifier = drug_client._parse_target_id(target_id)

        assert namespace == "HGNC"
        assert identifier == "76"

    def test_parse_target_id_bare_symbol(self, drug_client):
        """Test parsing bare gene symbol (assumes HGNC)."""
        target_id = "ABL1"
        namespace, identifier = drug_client._parse_target_id(target_id)

        assert namespace == "HGNC"
        assert identifier == "ABL1"


class TestGetDrugTargets:
    """Test getting targets for a drug."""

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_get_targets_basic(self, mock_get_targets, drug_client, imatinib_targets_data):
        """Test basic drug target retrieval."""
        mock_get_targets.return_value = imatinib_targets_data

        result = drug_client.get_targets(drug_id="chebi:45783")

        assert result["success"] is True
        assert len(result["targets"]) == 3
        assert result["drug_curie"] == "chebi:45783"

        # Verify ABL1 is in targets
        abl1_target = next(t for t in result["targets"] if t["name"] == "ABL1")
        assert abl1_target["curie"] == "hgnc:76"
        assert abl1_target["action_type"] == "inhibitor"
        assert abl1_target["evidence_count"] == 150

        # Verify CoGEx function called correctly
        mock_get_targets.assert_called_once()
        call_kwargs = mock_get_targets.call_args[1]
        assert call_kwargs["drug_id"] == ("CHEBI", "45783")

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_get_targets_with_action_filter(self, mock_get_targets, drug_client, imatinib_targets_data):
        """Test filtering targets by action type."""
        mock_get_targets.return_value = imatinib_targets_data

        result = drug_client.get_targets(
            drug_id="chebi:45783",
            action_type="inhibitor",
        )

        assert result["success"] is True
        assert len(result["targets"]) == 3  # All are inhibitors

        # All should be inhibitors
        for target in result["targets"]:
            assert target["action_type"] == "inhibitor"

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_get_targets_empty_result(self, mock_get_targets, drug_client):
        """Test handling of drug with no known targets."""
        mock_get_targets.return_value = []

        result = drug_client.get_targets(drug_id="chebi:99999")

        assert result["success"] is True
        assert len(result["targets"]) == 0

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_get_targets_sorted_by_evidence(self, mock_get_targets, drug_client, imatinib_targets_data):
        """Test that targets are sorted by evidence count."""
        mock_get_targets.return_value = imatinib_targets_data

        result = drug_client.get_targets(drug_id="chebi:45783")

        # Should be sorted descending by evidence_count
        evidence_counts = [t["evidence_count"] for t in result["targets"]]
        assert evidence_counts == sorted(evidence_counts, reverse=True)
        assert evidence_counts == [150, 89, 72]


class TestGetDrugsForTarget:
    """Test getting drugs for a target gene."""

    @patch("cogex_mcp.clients.drug_client.get_drugs_for_target")
    def test_get_drugs_for_target_basic(self, mock_get_drugs, drug_client):
        """Test basic target-to-drugs retrieval."""
        mock_drugs_data = [
            {
                "drug": "imatinib",
                "drug_id": "chebi:45783",
                "drug_namespace": "chebi",
                "action_type": "inhibitor",
                "evidence_count": 150,
            },
            {
                "drug": "nilotinib",
                "drug_id": "chebi:52172",
                "drug_namespace": "chebi",
                "action_type": "inhibitor",
                "evidence_count": 95,
            },
        ]
        mock_get_drugs.return_value = mock_drugs_data

        result = drug_client.get_drugs_for_target(target_id="hgnc:76")

        assert result["success"] is True
        assert len(result["drugs"]) == 2
        assert result["target_curie"] == "hgnc:76"

        # Verify imatinib is in results
        imatinib = next(d for d in result["drugs"] if d["name"] == "imatinib")
        assert imatinib["curie"] == "chebi:45783"
        assert imatinib["action_type"] == "inhibitor"

        # Verify CoGEx function called
        mock_get_drugs.assert_called_once()
        call_kwargs = mock_get_drugs.call_args[1]
        assert call_kwargs["target_id"] == ("HGNC", "76")

    @patch("cogex_mcp.clients.drug_client.get_drugs_for_target")
    def test_get_drugs_with_pagination(self, mock_get_drugs, drug_client):
        """Test pagination for drug results."""
        # Create 50 mock drugs
        mock_drugs_data = [
            {
                "drug": f"drug_{i}",
                "drug_id": f"chebi:{10000 + i}",
                "drug_namespace": "chebi",
                "action_type": "inhibitor",
                "evidence_count": 100 - i,
            }
            for i in range(50)
        ]
        mock_get_drugs.return_value = mock_drugs_data

        result = drug_client.get_drugs_for_target(
            target_id="hgnc:76",
            limit=20,
            offset=0,
        )

        assert result["success"] is True
        assert len(result["drugs"]) <= 20
        assert result["pagination"]["total_count"] == 50
        assert result["pagination"]["offset"] == 0
        assert result["pagination"]["limit"] == 20


class TestGetDrugIndications:
    """Test getting indications for a drug."""

    @patch("cogex_mcp.clients.drug_client.get_indications_for_drug")
    def test_get_indications_basic(self, mock_get_indications, drug_client, imatinib_indications_data):
        """Test basic indication retrieval."""
        mock_get_indications.return_value = imatinib_indications_data

        result = drug_client.get_indications(drug_id="chebi:45783")

        assert result["success"] is True
        assert len(result["indications"]) == 2
        assert result["drug_curie"] == "chebi:45783"

        # Verify CML indication
        cml = next(i for i in result["indications"] if "leukemia" in i["disease_name"])
        assert cml["disease_curie"] == "mondo:0011996"
        assert cml["indication_type"] == "approved"
        assert cml["max_phase"] == 4

    @patch("cogex_mcp.clients.drug_client.get_indications_for_drug")
    def test_get_indications_filter_by_phase(self, mock_get_indications, drug_client):
        """Test filtering indications by clinical phase."""
        mock_data = [
            {
                "disease": "disease1",
                "disease_id": "mondo:0001",
                "disease_namespace": "mondo",
                "indication_type": "approved",
                "max_phase": 4,
            },
            {
                "disease": "disease2",
                "disease_id": "mondo:0002",
                "disease_namespace": "mondo",
                "indication_type": "clinical",
                "max_phase": 2,
            },
            {
                "disease": "disease3",
                "disease_id": "mondo:0003",
                "disease_namespace": "mondo",
                "indication_type": "clinical",
                "max_phase": 1,
            },
        ]
        mock_get_indications.return_value = mock_data

        result = drug_client.get_indications(
            drug_id="chebi:45783",
            min_phase=2,
        )

        assert result["success"] is True
        assert len(result["indications"]) == 2  # Only phase 4 and phase 2
        for indication in result["indications"]:
            assert indication["max_phase"] >= 2


class TestGetSideEffects:
    """Test getting side effects for a drug."""

    @patch("cogex_mcp.clients.drug_client.get_side_effects_for_drug")
    def test_get_side_effects_basic(self, mock_get_effects, drug_client, aspirin_side_effects_data):
        """Test basic side effect retrieval."""
        mock_get_effects.return_value = aspirin_side_effects_data

        result = drug_client.get_side_effects(drug_id="chebi:15365")

        assert result["success"] is True
        assert len(result["side_effects"]) == 3
        assert result["drug_curie"] == "chebi:15365"

        # Verify GI hemorrhage
        gi_bleed = next(e for e in result["side_effects"] if "hemorrhage" in e["effect_name"])
        assert gi_bleed["effect_curie"] == "umls:C0017181"
        assert gi_bleed["frequency"] == "common"

    @patch("cogex_mcp.clients.drug_client.get_side_effects_for_drug")
    def test_get_side_effects_sorted_by_frequency(self, mock_get_effects, drug_client, aspirin_side_effects_data):
        """Test that side effects are sorted by frequency."""
        mock_get_effects.return_value = aspirin_side_effects_data

        result = drug_client.get_side_effects(drug_id="chebi:15365")

        # Should be ordered: very common > common > uncommon > rare
        frequencies = [e["frequency"] for e in result["side_effects"]]
        assert frequencies == ["common", "uncommon", "rare"]

    @patch("cogex_mcp.clients.drug_client.get_side_effects_for_drug")
    def test_get_side_effects_empty(self, mock_get_effects, drug_client):
        """Test drug with no known side effects."""
        mock_get_effects.return_value = []

        result = drug_client.get_side_effects(drug_id="chebi:99999")

        assert result["success"] is True
        assert len(result["side_effects"]) == 0


class TestGetDrugProfile:
    """Test getting complete drug profile."""

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    @patch("cogex_mcp.clients.drug_client.get_indications_for_drug")
    @patch("cogex_mcp.clients.drug_client.get_side_effects_for_drug")
    def test_get_profile_complete(
        self,
        mock_get_effects,
        mock_get_indications,
        mock_get_targets,
        drug_client,
        pembrolizumab_profile_data,
    ):
        """Test getting complete drug profile (all features)."""
        mock_get_targets.return_value = pembrolizumab_profile_data["targets"]
        mock_get_indications.return_value = pembrolizumab_profile_data["indications"]
        mock_get_effects.return_value = pembrolizumab_profile_data["side_effects"]

        result = drug_client.get_profile(
            drug_id="chebi:164898",
            include_targets=True,
            include_indications=True,
            include_side_effects=True,
        )

        assert result["success"] is True
        assert result["drug_curie"] == "chebi:164898"
        assert "targets" in result
        assert "indications" in result
        assert "side_effects" in result

        # Verify target
        assert len(result["targets"]) == 1
        assert result["targets"][0]["name"] == "PDCD1"

        # Verify indications
        assert len(result["indications"]) == 2
        indication_names = [i["disease_name"] for i in result["indications"]]
        assert "melanoma" in indication_names

        # Verify side effects
        assert len(result["side_effects"]) == 2

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_get_profile_targets_only(self, mock_get_targets, drug_client, imatinib_targets_data):
        """Test getting profile with only targets."""
        mock_get_targets.return_value = imatinib_targets_data

        result = drug_client.get_profile(
            drug_id="chebi:45783",
            include_targets=True,
            include_indications=False,
            include_side_effects=False,
        )

        assert result["success"] is True
        assert "targets" in result
        assert "indications" not in result
        assert "side_effects" not in result

    @patch("cogex_mcp.clients.drug_client.get_indications_for_drug")
    def test_get_profile_indications_only(self, mock_get_indications, drug_client, imatinib_indications_data):
        """Test getting profile with only indications."""
        mock_get_indications.return_value = imatinib_indications_data

        result = drug_client.get_profile(
            drug_id="chebi:45783",
            include_targets=False,
            include_indications=True,
            include_side_effects=False,
        )

        assert result["success"] is True
        assert "targets" not in result
        assert "indications" in result
        assert "side_effects" not in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_drug_name_without_curie(self, drug_client):
        """Test handling of bare drug name (should be resolved elsewhere)."""
        # DrugClient expects CURIEs, resolution happens in entity_resolver
        # This tests that we handle non-CURIE gracefully
        with pytest.raises(ValueError):
            drug_client._parse_curie("imatinib")

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_targets_with_missing_fields(self, mock_get_targets, drug_client):
        """Test handling of target data with missing fields."""
        incomplete_data = [
            {
                "target": "ABL1",
                "target_id": "hgnc:76",
                # Missing action_type and evidence_count
            }
        ]
        mock_get_targets.return_value = incomplete_data

        result = drug_client.get_targets(drug_id="chebi:45783")

        assert result["success"] is True
        assert len(result["targets"]) == 1
        target = result["targets"][0]
        assert target["action_type"] is None or target["action_type"] == "unknown"
        assert target["evidence_count"] == 0

    @patch("cogex_mcp.clients.drug_client.get_indications_for_drug")
    def test_indications_with_null_phase(self, mock_get_indications, drug_client):
        """Test handling of indication without clinical phase."""
        data_with_null_phase = [
            {
                "disease": "test disease",
                "disease_id": "mondo:0001",
                "disease_namespace": "mondo",
                "indication_type": "preclinical",
                "max_phase": None,
            }
        ]
        mock_get_indications.return_value = data_with_null_phase

        result = drug_client.get_indications(drug_id="chebi:45783")

        assert result["success"] is True
        assert len(result["indications"]) == 1
        assert result["indications"][0]["max_phase"] is None


class TestResponseFormatting:
    """Test response formatting and structure."""

    @patch("cogex_mcp.clients.drug_client.get_targets_for_drug")
    def test_target_response_structure(self, mock_get_targets, drug_client, imatinib_targets_data):
        """Test complete target response structure."""
        mock_get_targets.return_value = imatinib_targets_data

        result = drug_client.get_targets(drug_id="chebi:45783")

        # Check top-level structure
        assert "success" in result
        assert "drug_curie" in result
        assert "targets" in result
        assert "count" in result

        # Check target structure
        for target in result["targets"]:
            assert "name" in target
            assert "curie" in target
            assert "namespace" in target
            assert "identifier" in target
            assert "action_type" in target
            assert "evidence_count" in target

    @patch("cogex_mcp.clients.drug_client.get_drugs_for_target")
    def test_drugs_response_with_pagination(self, mock_get_drugs, drug_client):
        """Test response includes pagination metadata."""
        mock_drugs = [
            {
                "drug": f"drug_{i}",
                "drug_id": f"chebi:{i}",
                "drug_namespace": "chebi",
                "action_type": "inhibitor",
                "evidence_count": 10,
            }
            for i in range(25)
        ]
        mock_get_drugs.return_value = mock_drugs

        result = drug_client.get_drugs_for_target(
            target_id="hgnc:76",
            limit=10,
            offset=0,
        )

        # Check pagination structure
        assert "pagination" in result
        pagination = result["pagination"]
        assert "total_count" in pagination
        assert "offset" in pagination
        assert "limit" in pagination
        assert "has_more" in pagination
        assert pagination["total_count"] == 25
        assert pagination["offset"] == 0
        assert pagination["limit"] == 10
        assert pagination["has_more"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=cogex_mcp.clients.drug_client", "--cov-report=term-missing"])
