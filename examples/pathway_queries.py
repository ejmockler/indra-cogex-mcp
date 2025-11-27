"""
Pathway Query Examples for INDRA CoGEx MCP Server

This module demonstrates how to use the PathwayClient to query pathway memberships
and relationships in the INDRA CoGEx knowledge graph.

The PathwayClient provides four main query modes:
1. get_genes - Get all genes in a specific pathway
2. get_pathways - Get all pathways containing a specific gene
3. find_shared - Find pathways shared across multiple genes
4. check_membership - Check if a gene is in a specific pathway

All examples use the @autoclient() decorator which automatically manages the
Neo4j connection.
"""

import asyncio
import logging
from typing import Dict, Any

from cogex_mcp.clients.pathway_client import PathwayClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Example 1: Get genes in TP53 signaling pathway
async def example_tp53_pathway_genes():
    """
    Example 1: Query all genes in the TP53 signaling pathway.

    This demonstrates how to retrieve the complete gene membership
    of a specific pathway using the pathway CURIE from Reactome.
    """
    print("\n" + "="*70)
    print("Example 1: Genes in TP53 Signaling Pathway (Reactome)")
    print("="*70)

    client = PathwayClient()

    # Query genes in TP53 regulation pathway from Reactome
    # Reactome ID: R-HSA-5633007 (TP53 Regulates Transcription of Genes Involved in G1 Cell Cycle Arrest)
    result = client.get_genes_in_pathway(
        pathway_id="reactome:R-HSA-5633007",
        limit=10,
        offset=0,
    )

    if result["success"]:
        print(f"\n✓ Found {result['total_count']} genes in TP53 pathway")
        print(f"  Pathway: {result['pathway']['name']}")
        print(f"  Source: {result['pathway']['source']}")
        print(f"\nFirst 10 genes:")

        for i, gene in enumerate(result["records"][:10], 1):
            print(f"  {i}. {gene['name']} ({gene['curie']})")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 2: Get pathways containing MAPK1
async def example_mapk1_pathways():
    """
    Example 2: Find all pathways that contain the MAPK1 gene.

    This demonstrates reverse lookup - given a gene, find all pathways
    it participates in. Useful for understanding a gene's functional roles.
    """
    print("\n" + "="*70)
    print("Example 2: Pathways Containing MAPK1 (ERK2)")
    print("="*70)

    client = PathwayClient()

    # Query pathways for MAPK1 (ERK2)
    result = client.get_pathways_for_gene(
        gene_id="hgnc:6871",  # MAPK1
        source="reactome",   # Filter to only Reactome pathways
        limit=10,
    )

    if result["success"]:
        print(f"\n✓ Found {result['total_count']} Reactome pathways containing MAPK1")
        print(f"\nTop 10 pathways:")

        for i, pathway in enumerate(result["records"][:10], 1):
            gene_count = pathway.get("gene_count", "?")
            print(f"  {i}. {pathway['pathway_name']}")
            print(f"     CURIE: {pathway['pathway_id']}")
            print(f"     Genes: {gene_count}")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 3: Find shared pathways for apoptosis genes
async def example_shared_apoptosis_pathways():
    """
    Example 3: Find pathways shared across multiple apoptosis-related genes.

    This demonstrates how to identify common biological processes by finding
    pathways that contain ALL of the specified genes. Useful for pathway
    enrichment analysis and understanding gene co-participation.
    """
    print("\n" + "="*70)
    print("Example 3: Shared Pathways for Apoptosis Genes")
    print("="*70)

    client = PathwayClient()

    # Key apoptosis genes
    apoptosis_genes = [
        "hgnc:11998",  # TP53
        "hgnc:588",    # CASP3
        "hgnc:591",    # CASP8
        "hgnc:593",    # CASP9
    ]

    gene_names = ["TP53", "CASP3", "CASP8", "CASP9"]
    print(f"\nQuerying shared pathways for: {', '.join(gene_names)}")

    result = client.get_shared_pathways(
        gene_ids=apoptosis_genes,
        source="reactome",
        limit=5,
    )

    if result["success"]:
        print(f"\n✓ Found {result['total_count']} shared pathways")

        if result["records"]:
            print(f"\nTop {min(5, len(result['records']))} shared pathways:")

            for i, pathway in enumerate(result["records"][:5], 1):
                genes_in_pathway = pathway.get("genes_in_pathway", [])
                print(f"\n  {i}. {pathway['pathway_name']}")
                print(f"     CURIE: {pathway['pathway_id']}")
                print(f"     Query genes in pathway: {len(genes_in_pathway)}/{len(apoptosis_genes)}")
                print(f"     Total genes: {pathway.get('gene_count', '?')}")
        else:
            print("\n  No pathways contain ALL specified genes.")
            print("  Try querying individual genes or smaller gene sets.")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 4: Check if TP53 is in p53 pathway
async def example_check_tp53_membership():
    """
    Example 4: Check if TP53 gene is a member of the p53 signaling pathway.

    This demonstrates a boolean membership check - useful for validation
    and filtering in automated workflows.
    """
    print("\n" + "="*70)
    print("Example 4: Check TP53 Membership in p53 Pathway")
    print("="*70)

    client = PathwayClient()

    # Check if TP53 is in the p53 signaling pathway
    result = client.check_membership(
        gene_id="hgnc:11998",  # TP53
        pathway_id="reactome:R-HSA-5633007",  # TP53 Regulates Transcription
    )

    if result["success"]:
        is_member = result["is_member"]
        status = "✓ YES" if is_member else "✗ NO"

        print(f"\nGene: TP53 (hgnc:11998)")
        print(f"Pathway: {result['pathway']['pathway_id']}")
        print(f"Is member: {status}")

        if is_member:
            print("\n  TP53 is confirmed to be in this pathway.")
        else:
            print("\n  TP53 is NOT in this pathway.")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 5: Comprehensive pathway analysis for a gene
async def example_comprehensive_gene_analysis():
    """
    Example 5: Comprehensive pathway analysis for a single gene.

    This demonstrates how to combine multiple query modes to get a complete
    picture of a gene's pathway involvement across different databases.
    """
    print("\n" + "="*70)
    print("Example 5: Comprehensive Pathway Analysis for EGFR")
    print("="*70)

    client = PathwayClient()
    gene_id = "hgnc:3467"  # EGFR

    print(f"\nAnalyzing pathway involvement for EGFR...")

    # Get pathways from different sources
    sources = ["reactome", "wikipathways", "go"]
    all_pathways = {}

    for source in sources:
        result = client.get_pathways_for_gene(
            gene_id=gene_id,
            source=source,
            limit=5,
        )

        if result["success"]:
            all_pathways[source] = result["records"]
            print(f"\n  {source.upper()}: {result['total_count']} pathways")

            # Show top 3 pathways
            for i, pathway in enumerate(result["records"][:3], 1):
                print(f"    {i}. {pathway['pathway_name']}")
        else:
            print(f"\n  {source.upper()}: Query failed")

    # Summary
    total = sum(len(pathways) for pathways in all_pathways.values())
    print(f"\n✓ Total unique pathway associations: {total}")

    return all_pathways


# Example 6: Pagination example
async def example_pagination():
    """
    Example 6: Demonstrate pagination for large result sets.

    This shows how to retrieve results in pages, which is essential
    for pathways with many genes or genes with many pathway associations.
    """
    print("\n" + "="*70)
    print("Example 6: Pagination - Genes in MAPK Signaling Pathway")
    print("="*70)

    client = PathwayClient()

    # MAPK signaling is a large pathway - demonstrate pagination
    pathway_id = "reactome:R-HSA-5683057"  # MAPK family signaling cascades
    page_size = 10

    print(f"\nRetrieving genes in pages of {page_size}...")

    # Get first page
    page1 = client.get_genes_in_pathway(
        pathway_id=pathway_id,
        limit=page_size,
        offset=0,
    )

    if page1["success"]:
        total = page1["total_count"]
        print(f"\n✓ Total genes in pathway: {total}")
        print(f"  Pages: {(total + page_size - 1) // page_size}")

        print(f"\nPage 1 (genes 1-{min(page_size, total)}):")
        for i, gene in enumerate(page1["records"], 1):
            print(f"  {i}. {gene['name']}")

        # Get second page
        if total > page_size:
            page2 = client.get_genes_in_pathway(
                pathway_id=pathway_id,
                limit=page_size,
                offset=page_size,
            )

            if page2["success"]:
                print(f"\nPage 2 (genes {page_size+1}-{min(2*page_size, total)}):")
                for i, gene in enumerate(page2["records"], page_size + 1):
                    print(f"  {i}. {gene['name']}")
    else:
        print(f"✗ Query failed: {page1.get('error', 'Unknown error')}")

    return page1


# Example 7: Error handling
async def example_error_handling():
    """
    Example 7: Demonstrate proper error handling.

    This shows how to handle various error conditions that may occur
    during pathway queries.
    """
    print("\n" + "="*70)
    print("Example 7: Error Handling Examples")
    print("="*70)

    client = PathwayClient()

    # Example 7a: Invalid pathway ID
    print("\nTest 7a: Invalid pathway ID")
    result = client.get_genes_in_pathway(
        pathway_id="invalid:XXXX",
        limit=10,
    )

    if not result["success"]:
        print(f"  ✓ Properly caught error: {result.get('error', 'Unknown')}")
    else:
        print(f"  Unexpected success (pathway might exist)")

    # Example 7b: Invalid gene ID
    print("\nTest 7b: Invalid gene ID")
    result = client.get_pathways_for_gene(
        gene_id="invalid:99999",
        limit=10,
    )

    if not result["success"]:
        print(f"  ✓ Properly caught error: {result.get('error', 'Unknown')}")
    else:
        print(f"  ✓ Query succeeded (returned {result['total_count']} pathways)")

    # Example 7c: Empty gene list
    print("\nTest 7c: Empty gene list for shared pathways")
    result = client.get_shared_pathways(
        gene_ids=[],
        limit=10,
    )

    if not result["success"]:
        print(f"  ✓ Properly caught error: {result.get('error', 'Unknown')}")
    else:
        print(f"  Query returned {result['total_count']} results")


# Main execution
async def main():
    """
    Run all pathway query examples.

    This demonstrates the complete PathwayClient API with realistic
    use cases for biological pathway analysis.
    """
    print("\n" + "="*70)
    print("INDRA CoGEx PathwayClient Examples")
    print("="*70)
    print("\nDemonstrating pathway membership and relationship queries")
    print("using the INDRA CoGEx knowledge graph.\n")

    try:
        # Run all examples
        await example_tp53_pathway_genes()
        await example_mapk1_pathways()
        await example_shared_apoptosis_pathways()
        await example_check_tp53_membership()
        await example_comprehensive_gene_analysis()
        await example_pagination()
        await example_error_handling()

        print("\n" + "="*70)
        print("All examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
