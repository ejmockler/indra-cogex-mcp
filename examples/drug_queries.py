"""
Drug Query Examples - INDRA CoGEx MCP

This module demonstrates how to use the DrugClient for various drug-related queries
including drug profiles, target-based discovery, indication searches, and side effect analysis.

All examples use the unified DrugClient which wraps INDRA CoGEx library functions.
"""

import asyncio
import logging
from pprint import pprint

from cogex_mcp.clients.drug_client import DrugClient
from indra_cogex.client.neo4j_client import Neo4jClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Imatinib Complete Profile
# ============================================================================

async def example_1_imatinib_profile():
    """
    Get comprehensive drug profile for Imatinib (Gleevec).

    This example demonstrates:
    - Fetching molecular targets (ABL1, KIT, PDGFR, etc.)
    - Retrieving therapeutic indications (CML, GIST, etc.)
    - Accessing side effect data
    - Complete drug characterization
    """
    logger.info("=" * 80)
    logger.info("EXAMPLE 1: Imatinib Complete Profile")
    logger.info("=" * 80)

    # Create drug client (autoclient will handle Neo4j connection)
    drug_client = DrugClient()

    # Query comprehensive Imatinib profile
    # ChEBI:45783 = Imatinib
    result = drug_client.get_drug_profile(
        drug_id="chebi:45783",
        include_targets=True,
        include_indications=True,
        include_side_effects=True,
    )

    # Display results
    if result["success"]:
        logger.info(f"\nDrug: {result['drug_id']}")

        # Molecular targets
        if "targets" in result:
            logger.info(f"\n--- Molecular Targets ({len(result['targets'])}) ---")
            for target in result["targets"][:5]:  # Show first 5
                logger.info(
                    f"  " {target['target_name']} ({target['target_id']}) "
                    f"- {target['action']}"
                )

        # Therapeutic indications
        if "indications" in result:
            logger.info(f"\n--- Indications ({len(result['indications'])}) ---")
            for indication in result["indications"][:5]:
                logger.info(
                    f"  " {indication['disease_name']} ({indication['disease_id']}) "
                    f"- Phase {indication.get('max_phase', 'N/A')}"
                )

        # Side effects
        if "side_effects" in result:
            logger.info(f"\n--- Side Effects ({len(result['side_effects'])}) ---")
            for se in result["side_effects"][:5]:
                logger.info(
                    f"  " {se['effect']} "
                    f"({se.get('frequency', 'frequency unknown')})"
                )
    else:
        logger.error(f"Error: {result.get('error')}")

    logger.info("\n" + "=" * 80 + "\n")


# ============================================================================
# Example 2: Find EGFR Inhibitors
# ============================================================================

async def example_2_egfr_inhibitors():
    """
    Find all drugs that inhibit EGFR (Epidermal Growth Factor Receptor).

    This example demonstrates:
    - Target-based drug discovery
    - Filtering by mechanism of action (inhibitor)
    - Identifying FDA-approved and investigational drugs
    - Common use case for precision oncology
    """
    logger.info("=" * 80)
    logger.info("EXAMPLE 2: EGFR Inhibitors")
    logger.info("=" * 80)

    drug_client = DrugClient()

    # Query drugs targeting EGFR
    # HGNC:3236 = EGFR gene
    result = drug_client.find_drugs_for_target(
        target_id="hgnc:3236",
        action_types=["inhibitor"],  # Only inhibitors
    )

    if result["success"]:
        logger.info(f"\nFound {result['total_drugs']} EGFR inhibitors")
        logger.info("\n--- EGFR Inhibitors ---")

        for drug in result["drugs"][:10]:  # Show first 10
            logger.info(
                f"  " {drug['drug_name']} ({drug['drug_id']}) "
                f"- {drug['action']}"
            )

        logger.info(f"\nWell-known examples:")
        logger.info("  " Gefitinib (Iressa) - 1st generation")
        logger.info("  " Erlotinib (Tarceva) - 1st generation")
        logger.info("  " Afatinib (Gilotrif) - 2nd generation")
        logger.info("  " Osimertinib (Tagrisso) - 3rd generation (T790M)")
    else:
        logger.error(f"Error: {result.get('error')}")

    logger.info("\n" + "=" * 80 + "\n")


# ============================================================================
# Example 3: Breast Cancer Therapeutics
# ============================================================================

async def example_3_breast_cancer_drugs():
    """
    Find drugs indicated for breast cancer treatment.

    This example demonstrates:
    - Disease-based drug discovery
    - Identifying approved therapies
    - Clinical indication mapping
    - Translational medicine workflow
    """
    logger.info("=" * 80)
    logger.info("EXAMPLE 3: Breast Cancer Therapeutics")
    logger.info("=" * 80)

    drug_client = DrugClient()

    # Query drugs for breast cancer
    # MeSH:D001943 = Breast Neoplasms
    result = drug_client.find_drugs_for_indication(
        disease_id="mesh:D001943",
    )

    if result["success"]:
        logger.info(f"\nFound {result['total_drugs']} drugs indicated for breast cancer")
        logger.info("\n--- Breast Cancer Drugs ---")

        for drug in result["drugs"][:10]:  # Show first 10
            logger.info(
                f"  " {drug['drug_name']} ({drug['drug_id']}) "
                f"- {drug.get('indication_type', 'approved')}"
            )

        logger.info(f"\nTherapeutic classes:")
        logger.info("  " Hormone therapies (Tamoxifen, Letrozole)")
        logger.info("  " HER2 inhibitors (Trastuzumab, Pertuzumab)")
        logger.info("  " CDK4/6 inhibitors (Palbociclib, Ribociclib)")
        logger.info("  " Chemotherapy (Doxorubicin, Paclitaxel)")
    else:
        logger.error(f"Error: {result.get('error')}")

    logger.info("\n" + "=" * 80 + "\n")


# ============================================================================
# Example 4: Drugs Causing Nausea
# ============================================================================

async def example_4_nausea_side_effects():
    """
    Find drugs that commonly cause nausea as a side effect.

    This example demonstrates:
    - Adverse event profiling
    - Safety pharmacology
    - Drug-side effect associations
    - Supporting clinical decision making
    """
    logger.info("=" * 80)
    logger.info("EXAMPLE 4: Drugs Causing Nausea")
    logger.info("=" * 80)

    drug_client = DrugClient()

    # Query drugs causing nausea
    result = drug_client.find_drugs_for_side_effect(
        side_effect="nausea",
    )

    if result["success"]:
        logger.info(f"\nFound {result['total_drugs']} drugs associated with nausea")
        logger.info("\n--- Drugs Causing Nausea ---")

        for drug in result["drugs"][:10]:  # Show first 10
            logger.info(
                f"  " {drug['drug_name']} ({drug['drug_id']}) "
                f"- {drug.get('frequency', 'frequency unknown')}"
            )

        logger.info(f"\nCommon drug classes:")
        logger.info("  " Chemotherapy agents (very common)")
        logger.info("  " Opioid analgesics (common)")
        logger.info("  " Antibiotics (common)")
        logger.info("  " SSRIs/antidepressants (common)")
    else:
        logger.error(f"Error: {result.get('error')}")

    logger.info("\n" + "=" * 80 + "\n")


# ============================================================================
# Example 5: Drug Repurposing Workflow
# ============================================================================

async def example_5_drug_repurposing():
    """
    Drug repurposing: Find alternative uses for Metformin.

    This example demonstrates:
    - Beyond diabetes: Cancer, aging, neurodegeneration
    - Off-label use discovery
    - Mechanism-based repurposing
    - Translational research workflow

    Metformin is approved for diabetes but shows promise in:
    - Cancer prevention and treatment
    - Anti-aging effects
    - Neuroprotection
    - Metabolic disorders
    """
    logger.info("=" * 80)
    logger.info("EXAMPLE 5: Drug Repurposing - Metformin")
    logger.info("=" * 80)

    drug_client = DrugClient()

    # Step 1: Get Metformin profile
    logger.info("\nStep 1: Get Metformin molecular profile")

    # ChEBI:6801 = Metformin
    metformin_profile = drug_client.get_drug_profile(
        drug_id="chebi:6801",
        include_targets=True,
        include_indications=True,
        include_side_effects=False,
    )

    if metformin_profile["success"]:
        # Show targets
        if "targets" in metformin_profile:
            logger.info(f"\n--- Molecular Targets ({len(metformin_profile['targets'])}) ---")
            for target in metformin_profile["targets"][:5]:
                logger.info(
                    f"  " {target['target_name']} ({target['target_id']})"
                )

        # Show approved indications
        if "indications" in metformin_profile:
            logger.info(f"\n--- Approved Indications ---")
            for indication in metformin_profile["indications"][:3]:
                logger.info(
                    f"  " {indication['disease_name']}"
                )

    # Step 2: Repurposing strategy
    logger.info("\n\nStep 2: Drug Repurposing Opportunities")
    logger.info("\n--- Potential Alternative Indications ---")
    logger.info("  " Cancer prevention (colorectal, breast)")
    logger.info("    - AMPK activation ’ mTOR inhibition")
    logger.info("    - Reduced cancer cell proliferation")
    logger.info("  " Anti-aging effects")
    logger.info("    - Metabolic optimization")
    logger.info("    - Longevity pathways activation")
    logger.info("  " Neuroprotection")
    logger.info("    - Alzheimer's disease")
    logger.info("    - Parkinson's disease")
    logger.info("  " PCOS (Polycystic Ovary Syndrome)")
    logger.info("    - Insulin sensitization")
    logger.info("    - Hormonal regulation")

    logger.info("\n--- Mechanism Supporting Repurposing ---")
    logger.info("  1. AMPK activation (energy sensing)")
    logger.info("  2. mTOR pathway inhibition (growth regulation)")
    logger.info("  3. Insulin sensitivity improvement")
    logger.info("  4. Anti-inflammatory effects")
    logger.info("  5. Autophagy induction")

    logger.info("\n" + "=" * 80 + "\n")


# ============================================================================
# Main execution
# ============================================================================

async def main():
    """Run all drug query examples."""
    logger.info("\n" + "=" * 80)
    logger.info("INDRA CoGEx MCP - Drug Query Examples")
    logger.info("=" * 80 + "\n")

    # Run all examples
    await example_1_imatinib_profile()
    await example_2_egfr_inhibitors()
    await example_3_breast_cancer_drugs()
    await example_4_nausea_side_effects()
    await example_5_drug_repurposing()

    logger.info("=" * 80)
    logger.info("All examples completed!")
    logger.info("=" * 80 + "\n")


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
