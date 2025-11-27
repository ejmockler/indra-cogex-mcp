"""
Integration tests for DrugClient with real Neo4j database.

Tests scientific accuracy using known drug-target relationships and clinical data.
Validates against gold-standard examples from ChEMBL and DrugBank.

Run with: pytest tests/integration/test_drug_integration.py -v -s
"""

import pytest
import time
from cogex_mcp.clients.drug_client import DrugClient


@pytest.fixture(scope="module")
def drug_client():
    """DrugClient instance with real Neo4j connection."""
    # Uses autoclient from indra_cogex
    return DrugClient()


class TestKnownDrugTargets:
    """Test known drug-target relationships from literature."""

    def test_imatinib_targets_abl1_and_kit(self, drug_client):
        """
        Test imatinib (Gleevec) targets ABL1 and KIT.

        Scientific validation:
        - Imatinib is BCR-ABL tyrosine kinase inhibitor
        - Primary target: ABL1 (in BCR-ABL fusion)
        - Secondary targets: KIT (c-Kit), PDGFR
        - FDA approved for CML and GIST
        """
        result = drug_client.get_targets(drug_id="chebi:45783")

        assert result["success"] is True
        assert result["drug_curie"] == "chebi:45783"

        target_names = [t["name"] for t in result["targets"]]
        target_curies = [t["curie"] for t in result["targets"]]

        # Core validation: ABL1 and KIT should be present
        assert "ABL1" in target_names, "Imatinib must target ABL1 (BCR-ABL)"
        assert "KIT" in target_names, "Imatinib must target KIT (c-Kit)"

        # Verify proper formatting
        abl1_target = next(t for t in result["targets"] if t["name"] == "ABL1")
        assert abl1_target["namespace"] == "hgnc"
        assert abl1_target["action_type"] in ["inhibitor", "antagonist"]
        assert abl1_target["evidence_count"] > 0

        print(f"\n✓ Imatinib targets validated: {', '.join(target_names[:5])}")

    def test_drugs_targeting_egfr(self, drug_client):
        """
        Test finding EGFR inhibitors.

        Expected drugs:
        - Erlotinib (Tarceva) - EGFR TKI
        - Gefitinib (Iressa) - EGFR TKI
        - Cetuximab (Erbitux) - EGFR antibody
        - Osimertinib (Tagrisso) - 3rd gen EGFR TKI
        """
        result = drug_client.get_drugs_for_target(target_id="hgnc:3236")  # EGFR

        assert result["success"] is True
        assert result["target_curie"] == "hgnc:3236"
        assert len(result["drugs"]) > 0

        drug_names = [d["name"].lower() for d in result["drugs"]]

        # At least one of the major EGFR inhibitors should be present
        egfr_inhibitors = ["erlotinib", "gefitinib", "cetuximab", "osimertinib", "afatinib"]
        found_inhibitors = [drug for drug in egfr_inhibitors if any(drug in name for name in drug_names)]

        assert len(found_inhibitors) > 0, f"Expected EGFR inhibitors, found: {drug_names[:10]}"

        print(f"\n✓ Found {len(found_inhibitors)} known EGFR inhibitors: {', '.join(found_inhibitors)}")

    def test_pembrolizumab_targets_pd1(self, drug_client):
        """
        Test pembrolizumab (Keytruda) targets PD-1.

        Scientific validation:
        - Pembrolizumab is monoclonal antibody
        - Target: PDCD1 (PD-1, programmed cell death protein 1)
        - Mechanism: Immune checkpoint inhibitor
        - FDA approved for melanoma, NSCLC, many others
        """
        result = drug_client.get_targets(drug_id="chebi:164898")

        assert result["success"] is True
        target_names = [t["name"] for t in result["targets"]]

        # PD-1 gene symbol is PDCD1
        assert "PDCD1" in target_names or "PD1" in target_names, \
            "Pembrolizumab must target PDCD1 (PD-1)"

        pd1_target = next(
            (t for t in result["targets"] if t["name"] in ["PDCD1", "PD1"]),
            None
        )
        if pd1_target:
            assert pd1_target["action_type"] in ["antibody", "antagonist", "inhibitor"]
            print(f"\n✓ Pembrolizumab target validated: {pd1_target['name']} ({pd1_target['action_type']})")


class TestKnownDrugIndications:
    """Test known drug indications from FDA approvals."""

    def test_drugs_for_breast_cancer(self, drug_client):
        """
        Test finding drugs indicated for breast cancer.

        Expected drugs:
        - Tamoxifen - SERM, hormone therapy
        - Trastuzumab (Herceptin) - HER2 antibody
        - Paclitaxel (Taxol) - microtubule stabilizer
        - Doxorubicin (Adriamycin) - topoisomerase inhibitor
        """
        # Breast cancer: mondo:0007254 or doid:1612
        result = drug_client.get_drugs_for_indication(disease_id="mondo:0007254")

        assert result["success"] is True
        assert len(result["drugs"]) > 0

        drug_names = [d["name"].lower() for d in result["drugs"]]

        # At least some known breast cancer drugs should be present
        breast_cancer_drugs = ["tamoxifen", "trastuzumab", "paclitaxel", "doxorubicin", "letrozole"]
        found_drugs = [drug for drug in breast_cancer_drugs if any(drug in name for name in drug_names)]

        assert len(found_drugs) > 0, f"Expected breast cancer drugs, found: {drug_names[:10]}"

        print(f"\n✓ Found {len(found_drugs)} known breast cancer drugs: {', '.join(found_drugs)}")

    def test_imatinib_indications(self, drug_client):
        """
        Test imatinib indications.

        Expected:
        - Chronic myeloid leukemia (CML) - mondo:0011996
        - Gastrointestinal stromal tumor (GIST) - mondo:0011719
        - Philadelphia chromosome positive ALL
        """
        result = drug_client.get_indications(drug_id="chebi:45783")

        assert result["success"] is True
        assert len(result["indications"]) > 0

        disease_names = [i["disease_name"].lower() for i in result["indications"]]

        # CML should definitely be present (primary indication)
        assert any("leukemia" in name or "cml" in name for name in disease_names), \
            f"Imatinib must have CML indication. Found: {disease_names}"

        # At least one should be approved (phase 4)
        approved_indications = [i for i in result["indications"] if i.get("max_phase") == 4]
        assert len(approved_indications) > 0, "Imatinib should have approved indications"

        print(f"\n✓ Imatinib indications validated: {', '.join(disease_names[:3])}")


class TestKnownSideEffects:
    """Test known side effects from pharmacovigilance data."""

    def test_aspirin_side_effects(self, drug_client):
        """
        Test aspirin side effects.

        Well-documented:
        - Gastrointestinal bleeding
        - Peptic ulcer
        - Tinnitus (high doses)
        - Allergic reactions
        """
        result = drug_client.get_side_effects(drug_id="chebi:15365")

        assert result["success"] is True
        assert len(result["side_effects"]) > 0

        effect_names = [e["effect_name"].lower() for e in result["side_effects"]]

        # GI effects are most common
        gi_related = [
            "hemorrhage", "bleeding", "ulcer", "gastro",
            "dyspepsia", "nausea", "abdominal"
        ]
        has_gi_effect = any(
            any(keyword in effect for keyword in gi_related)
            for effect in effect_names
        )

        assert has_gi_effect, f"Aspirin should have GI side effects. Found: {effect_names[:10]}"

        print(f"\n✓ Aspirin side effects validated: {', '.join(effect_names[:5])}")

    def test_methotrexate_side_effects(self, drug_client):
        """
        Test methotrexate side effects.

        Known effects:
        - Hepatotoxicity
        - Myelosuppression
        - Mucositis
        - Pulmonary toxicity
        """
        result = drug_client.get_side_effects(drug_id="chebi:44185")

        assert result["success"] is True
        assert len(result["side_effects"]) > 0

        effect_names = [e["effect_name"].lower() for e in result["side_effects"]]

        # Common methotrexate toxicities
        expected_effects = ["hepato", "liver", "myelo", "mucositis", "pulmonary", "nausea"]
        found_effects = [
            effect for effect in expected_effects
            if any(effect in name for name in effect_names)
        ]

        assert len(found_effects) > 0, \
            f"Methotrexate should have known toxicities. Found: {effect_names[:10]}"

        print(f"\n✓ Methotrexate side effects validated: {', '.join(effect_names[:5])}")


class TestFiltering:
    """Test filtering and query parameters."""

    def test_action_type_filtering(self, drug_client):
        """Test filtering targets by action type."""
        # Get all targets for a kinase inhibitor
        result = drug_client.get_targets(
            drug_id="chebi:45783",  # Imatinib
            action_type="inhibitor",
        )

        assert result["success"] is True

        # All targets should be inhibitors
        for target in result["targets"]:
            assert target["action_type"] in ["inhibitor", "antagonist"], \
                f"Expected inhibitor, got {target['action_type']}"

        print(f"\n✓ Action type filtering validated: {len(result['targets'])} inhibitor targets")

    def test_clinical_phase_filtering(self, drug_client):
        """Test filtering indications by clinical phase."""
        # Get only approved indications (phase 4)
        result = drug_client.get_indications(
            drug_id="chebi:45783",  # Imatinib
            min_phase=4,
        )

        assert result["success"] is True

        # All should be phase 4 (approved)
        for indication in result["indications"]:
            assert indication["max_phase"] == 4, \
                f"Expected phase 4, got phase {indication['max_phase']}"

        print(f"\n✓ Phase filtering validated: {len(result['indications'])} approved indications")

    def test_pagination(self, drug_client):
        """Test pagination for large result sets."""
        # Get first page
        result_page1 = drug_client.get_drugs_for_target(
            target_id="hgnc:3236",  # EGFR - many inhibitors
            limit=5,
            offset=0,
        )

        # Get second page
        result_page2 = drug_client.get_drugs_for_target(
            target_id="hgnc:3236",
            limit=5,
            offset=5,
        )

        assert result_page1["success"] is True
        assert result_page2["success"] is True

        # Pages should be different
        page1_drugs = {d["curie"] for d in result_page1["drugs"]}
        page2_drugs = {d["curie"] for d in result_page2["drugs"]}
        assert page1_drugs != page2_drugs, "Pages should contain different drugs"

        # Check pagination metadata
        assert result_page1["pagination"]["offset"] == 0
        assert result_page2["pagination"]["offset"] == 5
        assert result_page1["pagination"]["limit"] == 5

        print(f"\n✓ Pagination validated: Page 1 ({len(page1_drugs)}), Page 2 ({len(page2_drugs)})")


class TestPerformance:
    """Test query performance."""

    def test_query_performance_under_5_seconds(self, drug_client):
        """Test that complex queries complete within 5 seconds."""
        start_time = time.time()

        # Complex query: get full profile
        result = drug_client.get_profile(
            drug_id="chebi:45783",  # Imatinib
            include_targets=True,
            include_indications=True,
            include_side_effects=True,
        )

        elapsed_time = time.time() - start_time

        assert result["success"] is True
        assert elapsed_time < 5.0, f"Query took {elapsed_time:.2f}s, expected <5s"

        print(f"\n✓ Performance validated: {elapsed_time:.2f}s (target: <5s)")

    def test_batch_query_performance(self, drug_client):
        """Test performance of multiple sequential queries."""
        start_time = time.time()

        # Query 10 different drugs
        test_drugs = [
            "chebi:45783",  # Imatinib
            "chebi:15365",  # Aspirin
            "chebi:44185",  # Methotrexate
            "chebi:41774",  # Doxorubicin
            "chebi:63632",  # Paclitaxel
        ]

        results = []
        for drug_id in test_drugs:
            result = drug_client.get_targets(drug_id=drug_id)
            results.append(result)

        elapsed_time = time.time() - start_time

        assert all(r["success"] for r in results)
        assert elapsed_time < 10.0, f"Batch queries took {elapsed_time:.2f}s, expected <10s"

        print(f"\n✓ Batch performance validated: {len(test_drugs)} queries in {elapsed_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
