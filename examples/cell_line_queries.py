"""
Cell Line Query Examples

Demonstrates CCLE and DepMap cell line data queries including:
1. A549 lung cancer cell line profile
2. Finding KRAS-mutant cell lines
3. Checking TP53 status in HeLa
4. Screening for PIK3CA mutations in breast cancer models

These examples use the CellLineClient to access cancer cell line data
from the Cancer Cell Line Encyclopedia (CCLE) and DepMap projects.
"""

import asyncio
import logging
from cogex_mcp.clients.cell_line_client import CellLineClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example1_a549_profile():
    """
    Example 1: A549 Lung Cancer Cell Line Profile

    A549 is a non-small cell lung cancer (NSCLC) line derived from
    a lung carcinoma. It's one of the most widely used models for
    studying lung cancer biology and drug response.

    Known features:
    - KRAS G12S mutation (driver)
    - STK11 mutation
    - KEAP1 mutation
    - Wild-type EGFR
    - Wild-type TP53
    """
    logger.info("=" * 80)
    logger.info("Example 1: A549 Lung Cancer Cell Line Profile")
    logger.info("=" * 80)

    client = CellLineClient()

    # Get comprehensive cell line profile
    result = client.get_cell_line_profile(
        cell_line="A549",
        include_mutations=True,
        include_copy_number=True,
        include_dependencies=False,
        include_expression=False,
    )

    if not result.get("success"):
        logger.error(f"Query failed: {result.get('error')}")
        return

    logger.info(f"\nCell Line: {result['cell_line']}")

    # Display mutations
    mutations = result.get("mutations", [])
    logger.info(f"\nMutations found: {len(mutations)}")

    if mutations:
        logger.info("\nTop mutations:")
        for i, mutation in enumerate(mutations[:10], 1):
            gene = mutation.get("gene_name", "Unknown")
            mut_type = mutation.get("mutation_type", "unknown")
            protein_change = mutation.get("protein_change", "")
            is_driver = mutation.get("is_driver", False)
            driver_status = " [DRIVER]" if is_driver else ""

            logger.info(
                f"  {i}. {gene} - {mut_type} - {protein_change}{driver_status}"
            )

    # Display copy number alterations
    cnas = result.get("copy_number_alterations", [])
    logger.info(f"\nCopy Number Alterations: {len(cnas)}")

    if cnas:
        amplifications = [c for c in cnas if c["alteration_type"] == "amplification"]
        deletions = [c for c in cnas if c["alteration_type"] == "deletion"]

        logger.info(f"  Amplifications: {len(amplifications)}")
        if amplifications[:5]:
            for cna in amplifications[:5]:
                logger.info(f"    - {cna['gene_name']} (CN: {cna['copy_number']:.1f})")

        logger.info(f"  Deletions: {len(deletions)}")
        if deletions[:5]:
            for cna in deletions[:5]:
                logger.info(f"    - {cna['gene_name']} (CN: {cna['copy_number']:.1f})")

    logger.info("\n" + "=" * 80)


async def example2_find_kras_mutants():
    """
    Example 2: Find KRAS-Mutant Cell Lines

    KRAS is one of the most frequently mutated oncogenes in cancer,
    particularly in pancreatic, colorectal, and lung cancers.

    KRAS-mutant cell lines are valuable models for:
    - Studying RAS pathway biology
    - Testing KRAS-targeted therapies
    - Understanding resistance mechanisms

    Common KRAS-mutant lines:
    - A549 (lung) - G12S
    - HCT116 (colon) - G13D
    - SW480 (colon) - G12V
    - PANC-1 (pancreatic) - G12D
    """
    logger.info("=" * 80)
    logger.info("Example 2: Find KRAS-Mutant Cell Lines")
    logger.info("=" * 80)

    client = CellLineClient()

    # Find all KRAS-mutant cell lines
    result = client.get_cell_lines_with_mutation(
        gene_id="KRAS"
    )

    if not result.get("success"):
        logger.error(f"Query failed: {result.get('error')}")
        return

    logger.info(f"\nGene: {result['gene_id']}")

    cell_lines = result.get("cell_lines", [])
    logger.info(f"KRAS-mutant cell lines found: {len(cell_lines)}")

    if cell_lines:
        logger.info("\nTop KRAS-mutant cell lines:")
        for i, cell_line in enumerate(cell_lines[:15], 1):
            name = cell_line.get("name", "Unknown")
            tissue = cell_line.get("tissue", "unknown")
            disease = cell_line.get("disease", "unknown")

            logger.info(f"  {i}. {name:15s} - {tissue:20s} - {disease}")

    logger.info("\n" + "=" * 80)


async def example3_check_tp53_in_hela():
    """
    Example 3: Check TP53 Status in HeLa

    HeLa is a cervical cancer cell line immortalized by HPV infection.
    The HPV E6 protein targets TP53 for degradation, effectively
    inactivating the p53 tumor suppressor pathway.

    This example demonstrates a boolean mutation check,
    useful for confirming expected mutations in well-characterized
    cell lines or validating database completeness.
    """
    logger.info("=" * 80)
    logger.info("Example 3: Check TP53 Status in HeLa")
    logger.info("=" * 80)

    client = CellLineClient()

    # Check if HeLa has TP53 mutation
    result = client.check_mutation(
        cell_line="HeLa",
        gene_id="TP53",
    )

    if not result.get("success"):
        logger.error(f"Query failed: {result.get('error')}")
        return

    logger.info(f"\nCell Line: {result['cell_line']}")
    logger.info(f"Gene: {result['gene_id']}")
    logger.info(f"Has Mutation: {result['is_mutated']}")

    if result['is_mutated']:
        logger.info("\nInterpretation:")
        logger.info("  HeLa cells have TP53 mutations/inactivation due to HPV E6")
        logger.info("  E6 protein targets p53 for ubiquitin-mediated degradation")
        logger.info("  This leads to loss of p53 tumor suppressor function")
    else:
        logger.info("\nNote: Database may not have TP53 mutation data for HeLa")
        logger.info("  TP53 is functionally inactivated by HPV E6 protein")

    logger.info("\n" + "=" * 80)


async def example4_pik3ca_breast_cancer_screen():
    """
    Example 4: Screen for PIK3CA Mutations in Breast Cancer Models

    PIK3CA is frequently mutated in breast cancer (~40% of cases).
    The H1047R hotspot mutation in the kinase domain is particularly
    common in ER+ breast cancers.

    PIK3CA-mutant cell lines:
    - MCF7 (H1047R) - ER+ luminal
    - T47D (H1047R) - ER+ luminal
    - MDA-MB-453 (H1047R) - ER-
    - HCC1954 (H1047R) - HER2+

    These models are valuable for studying:
    - PI3K pathway biology
    - PIK3CA inhibitor response
    - Combination therapies (PI3Ki + endocrine therapy)
    """
    logger.info("=" * 80)
    logger.info("Example 4: Screen for PIK3CA Mutations in Breast Cancer")
    logger.info("=" * 80)

    client = CellLineClient()

    # Find all PIK3CA-mutant cell lines
    result = client.get_cell_lines_with_mutation(
        gene_id="PIK3CA"
    )

    if not result.get("success"):
        logger.error(f"Query failed: {result.get('error')}")
        return

    logger.info(f"\nGene: {result['gene_id']}")

    cell_lines = result.get("cell_lines", [])
    logger.info(f"PIK3CA-mutant cell lines found: {len(cell_lines)}")

    # Filter for breast cancer models (if tissue info available)
    breast_lines = [
        cl for cl in cell_lines
        if cl.get("tissue", "").lower() == "breast"
        or cl.get("disease", "").lower().find("breast") >= 0
    ]

    if breast_lines:
        logger.info(f"\nPIK3CA-mutant breast cancer cell lines: {len(breast_lines)}")
        for i, cell_line in enumerate(breast_lines[:10], 1):
            name = cell_line.get("name", "Unknown")
            disease = cell_line.get("disease", "unknown")
            logger.info(f"  {i}. {name:15s} - {disease}")
    else:
        logger.info("\nShowing all PIK3CA-mutant cell lines (tissue info may be limited):")
        for i, cell_line in enumerate(cell_lines[:15], 1):
            name = cell_line.get("name", "Unknown")
            tissue = cell_line.get("tissue", "unknown")
            disease = cell_line.get("disease", "unknown")
            logger.info(f"  {i}. {name:15s} - {tissue:20s} - {disease}")

    # Check specific known PIK3CA-mutant breast lines
    logger.info("\nChecking known PIK3CA-mutant breast cancer lines:")
    known_lines = ["MCF7", "T47D", "MDA-MB-453", "HCC1954"]

    for cell_line_name in known_lines:
        check_result = client.check_mutation(
            cell_line=cell_line_name,
            gene_id="PIK3CA",
        )

        if check_result.get("success"):
            is_mutated = check_result.get("is_mutated", False)
            status = "MUTANT" if is_mutated else "WT"
            logger.info(f"  {cell_line_name:15s}: {status}")

    logger.info("\n" + "=" * 80)


async def main():
    """Run all cell line query examples."""
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("CELL LINE QUERY EXAMPLES")
    logger.info("=" * 80)
    logger.info("\n")

    # Run examples sequentially
    await example1_a549_profile()
    await example2_find_kras_mutants()
    await example3_check_tp53_in_hela()
    await example4_pik3ca_breast_cancer_screen()

    logger.info("\n")
    logger.info("=" * 80)
    logger.info("ALL EXAMPLES COMPLETED")
    logger.info("=" * 80)
    logger.info("\n")


if __name__ == "__main__":
    asyncio.run(main())
