"""
Example variant queries using VariantClient.

Demonstrates:
1. APOE variants and Alzheimer's risk
2. BRCA1 pathogenic variants
3. GWAS lookup: Type 2 diabetes variants
4. Variant → gene mapping (rs7412 → APOE)
5. Phenotype scan: Height-associated variants
"""

import asyncio
import os
from indra_cogex.client.neo4j_client import Neo4jClient
from cogex_mcp.clients.variant_client import VariantClient


# Example 1: APOE Variants and Alzheimer's Disease Risk
async def example_apoe_alzheimers():
    """
    Demonstrate APOE variants and their association with Alzheimer's disease.

    Scientific background:
    - APOE ε4 allele (rs429358) is the strongest genetic risk factor for late-onset AD
    - APOE ε2 allele (rs7412) is protective against AD
    - These variants are among the most studied in human genetics
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: APOE Variants and Alzheimer's Disease")
    print("="*70)

    # Get Neo4j client
    client = Neo4jClient()
    variant_client = VariantClient(neo4j_client=client)

    # Get all variants for APOE gene with genome-wide significance
    print("\n1. Getting genome-wide significant variants for APOE gene...")
    result = variant_client.get_gene_variants(
        gene_id="hgnc:613",  # APOE
        max_p_value=5e-8,     # Genome-wide significance threshold
    )

    if result["success"]:
        print(f"   Found {result['total_variants']} genome-wide significant variants")
        for variant in result["variants"][:5]:
            print(f"   - {variant['rsid']}: p={variant['p_value']:.2e}, trait={variant['trait']}")

    # Look up specific famous variants
    print("\n2. Looking up rs7412 (ε2 protective allele)...")
    rs7412_genes = variant_client.get_variant_genes("rs7412")
    if rs7412_genes["success"] and rs7412_genes["total_genes"] > 0:
        genes = [g["name"] for g in rs7412_genes["genes"]]
        print(f"   rs7412 maps to: {', '.join(genes)}")

    # Get diseases associated with rs429358 (ε4 risk allele)
    print("\n3. Looking up rs429358 (ε4 risk allele)...")
    rs429358_diseases = variant_client.get_variant_diseases(
        variant_id="rs429358",
        max_p_value=1e-5,
    )
    if rs429358_diseases["success"]:
        print(f"   Found {rs429358_diseases['total_diseases']} disease associations")
        for disease in rs429358_diseases["diseases"][:3]:
            print(f"   - {disease['name']}: p={disease.get('p_value', 'N/A')}")

    print("\nScientific interpretation:")
    print("  • rs429358 (C→T, creating ε4 allele) increases AD risk ~3-15x")
    print("  • rs7412 (C→T, creating ε2 allele) decreases AD risk ~0.5x")
    print("  • Effect sizes vary by ethnicity and environmental factors")


# Example 2: BRCA1 Pathogenic Variants Discovery
async def example_brca1_pathogenic():
    """
    Identify pathogenic variants in BRCA1 associated with breast/ovarian cancer.

    Scientific background:
    - BRCA1 mutations account for ~40% of hereditary breast cancer
    - BRCA1 mutations account for ~90% of hereditary ovarian cancer
    - Most pathogenic variants are in exons 11, 13, and BRCT domain
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: BRCA1 Pathogenic Variants")
    print("="*70)

    client = Neo4jClient()
    variant_client = VariantClient(neo4j_client=client)

    # Get all BRCA1 variants
    print("\n1. Querying BRCA1 variants...")
    result = variant_client.get_gene_variants(
        gene_id="hgnc:1100",  # BRCA1
        max_p_value=1e-4,
    )

    if result["success"]:
        print(f"   Found {result['total_variants']} BRCA1 variants")

        # Group by trait/phenotype
        trait_counts = {}
        for variant in result["variants"]:
            trait = variant.get("trait", "Unknown")
            trait_counts[trait] = trait_counts.get(trait, 0) + 1

        print("\n   Trait distribution:")
        for trait, count in sorted(trait_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"   - {trait}: {count} variants")

    # Look for breast cancer specific variants
    print("\n2. Querying breast cancer associated variants...")
    breast_cancer_variants = variant_client.get_disease_variants(
        disease_id="doid:1612",  # Breast cancer
        max_p_value=1e-6,
        source="disgenet",  # Use DisGeNet for disease-variant associations
    )

    if breast_cancer_variants["success"]:
        print(f"   Found {breast_cancer_variants['total_variants']} breast cancer variants from DisGeNet")
        for variant in breast_cancer_variants["variants"][:5]:
            print(f"   - {variant['rsid']}: p={variant['p_value']:.2e}")

    print("\nClinical relevance:")
    print("  • Lifetime breast cancer risk: ~70% for BRCA1 carriers")
    print("  • Lifetime ovarian cancer risk: ~44% for BRCA1 carriers")
    print("  • Guides prophylactic surgery and screening decisions")


# Example 3: Type 2 Diabetes GWAS Variants
async def example_t2d_gwas():
    """
    Discover genetic variants associated with type 2 diabetes from GWAS.

    Scientific background:
    - T2D is highly polygenic (400+ loci identified)
    - Top loci: TCF7L2, PPARG, KCNJ11, IRS1
    - Genetic risk scores can predict T2D with moderate accuracy
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Type 2 Diabetes GWAS Variants")
    print("="*70)

    client = Neo4jClient()
    variant_client = VariantClient(neo4j_client=client)

    # Query T2D variants from GWAS Catalog
    print("\n1. Querying type 2 diabetes GWAS variants...")
    result = variant_client.get_phenotype_variants(
        phenotype="type 2 diabetes",
        max_p_value=5e-8,  # Genome-wide significance
    )

    if result["success"]:
        print(f"   Found {result['total_variants']} genome-wide significant T2D variants")

        # Show top variants by p-value
        sorted_variants = sorted(result["variants"], key=lambda x: x.get("p_value", 1.0))
        print("\n   Top 10 variants by significance:")
        for i, variant in enumerate(sorted_variants[:10], 1):
            rsid = variant["rsid"]
            p_value = variant["p_value"]
            trait = variant.get("trait", "T2D")
            print(f"   {i}. {rsid}: p={p_value:.2e} ({trait})")

    # Look up specific genes
    print("\n2. Checking TCF7L2 variants (strongest T2D locus)...")
    tcf7l2_variants = variant_client.get_gene_variants(
        gene_id="hgnc:11641",  # TCF7L2
        max_p_value=1e-5,
    )

    if tcf7l2_variants["success"]:
        print(f"   Found {tcf7l2_variants['total_variants']} TCF7L2 variants")
        for variant in tcf7l2_variants["variants"][:3]:
            print(f"   - {variant['rsid']}: p={variant['p_value']:.2e}, OR={variant.get('odds_ratio', 'N/A')}")

    print("\nGenetic architecture insights:")
    print("  • T2D is highly polygenic with hundreds of loci")
    print("  • Individual variants have small effect sizes (OR~1.1-1.4)")
    print("  • Genetic risk scores combine multiple variants for prediction")
    print("  • Environmental factors (diet, exercise) interact with genetics")


# Example 4: Variant-to-Gene Mapping
async def example_variant_to_gene():
    """
    Map variant rsIDs to their nearby genes.

    Use case: Given GWAS hits, identify candidate causal genes.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Variant → Gene Mapping")
    print("="*70)

    client = Neo4jClient()
    variant_client = VariantClient(neo4j_client=client)

    # Famous variants to look up
    variants_of_interest = [
        ("rs7412", "APOE ε2 protective allele for AD"),
        ("rs429358", "APOE ε4 risk allele for AD"),
        ("rs9939609", "FTO obesity variant"),
        ("rs1801282", "PPARG Pro12Ala T2D variant"),
    ]

    print("\nMapping variants to candidate genes:\n")

    for rsid, description in variants_of_interest:
        print(f"{rsid} ({description}):")
        result = variant_client.get_variant_genes(rsid)

        if result["success"] and result["total_genes"] > 0:
            genes = [g["name"] for g in result["genes"]]
            print(f"  → Genes: {', '.join(genes)}")
        else:
            print(f"  → No genes found (may not be in database)")
        print()

    print("Use case:")
    print("  • Fine-mapping: Identify causal genes from GWAS loci")
    print("  • Prioritization: Focus functional studies on nearby genes")
    print("  • Annotation: Add biological context to variant associations")


# Example 5: Height GWAS Phenotype Scan
async def example_height_gwas():
    """
    Explore genetic architecture of human height using GWAS data.

    Scientific background:
    - Height is extremely polygenic (10,000+ contributing variants)
    - ~700 genome-wide significant loci identified
    - Heritability ~80%, but individual variants have tiny effects
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Human Height Genetic Architecture")
    print("="*70)

    client = Neo4jClient()
    variant_client = VariantClient(neo4j_client=client)

    # Query height-associated variants
    print("\n1. Querying height GWAS variants...")
    result = variant_client.get_phenotype_variants(
        phenotype="height",
        max_p_value=5e-8,
    )

    if result["success"]:
        print(f"   Found {result['total_variants']} genome-wide significant height variants")

        # Analyze significance distribution
        p_values = [v["p_value"] for v in result["variants"]]
        if p_values:
            min_p = min(p_values)
            max_p = max(p_values)
            print(f"   P-value range: {min_p:.2e} to {max_p:.2e}")

        # Show extremely significant variants
        print("\n   Most significant variants:")
        sorted_variants = sorted(result["variants"], key=lambda x: x["p_value"])
        for variant in sorted_variants[:5]:
            rsid = variant["rsid"]
            p_val = variant["p_value"]
            chrom = variant.get("chromosome", "?")
            pos = variant.get("position", "?")
            print(f"   - {rsid} (chr{chrom}:{pos}): p={p_val:.2e}")

    # Look up a specific highly significant variant
    print("\n2. Analyzing a top variant...")
    if result["success"] and result["variants"]:
        top_variant = sorted(result["variants"], key=lambda x: x["p_value"])[0]
        rsid = top_variant["rsid"]

        print(f"\n   Top variant: {rsid}")

        # Find nearby genes
        genes_result = variant_client.get_variant_genes(rsid)
        if genes_result["success"] and genes_result["total_genes"] > 0:
            genes = [g["name"] for g in genes_result["genes"]]
            print(f"   Nearby genes: {', '.join(genes)}")

        # Check other phenotypes
        pheno_result = variant_client.get_variant_phenotypes(rsid, max_p_value=1e-5)
        if pheno_result["success"] and pheno_result["total_phenotypes"] > 0:
            print(f"   Other phenotype associations: {pheno_result['total_phenotypes']}")
            for pheno in pheno_result["phenotypes"][:3]:
                print(f"   - {pheno['name']}: p={pheno.get('p_value', 'N/A')}")

    print("\nGenetic insights:")
    print("  • Height is one of the most polygenic human traits")
    print("  • Each variant contributes ~0.1-0.3 cm to height")
    print("  • Demonstrates limits of GWAS for complex traits")
    print("  • Many height variants also affect other traits (pleiotropy)")


# Main execution
async def main():
    """Run all examples."""
    print("\n" + "#"*70)
    print("# Variant Query Examples")
    print("# Demonstrating VariantClient with Real Scientific Use Cases")
    print("#"*70)

    # Check if Neo4j is available
    try:
        client = Neo4jClient()
        print("\n✓ Connected to INDRA CoGEx Neo4j database")
    except Exception as e:
        print(f"\n✗ Could not connect to Neo4j: {e}")
        print("\nPlease ensure:")
        print("  1. Neo4j is running")
        print("  2. INDRA_NEO4J_URL, INDRA_NEO4J_USER, INDRA_NEO4J_PASSWORD are set")
        return

    # Run examples
    try:
        await example_apoe_alzheimers()
        await example_brca1_pathogenic()
        await example_t2d_gwas()
        await example_variant_to_gene()
        await example_height_gwas()
    except Exception as e:
        print(f"\n✗ Example failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "#"*70)
    print("# Examples Complete")
    print("#"*70)
    print()


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
