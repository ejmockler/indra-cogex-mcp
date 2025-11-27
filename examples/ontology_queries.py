"""
Ontology hierarchy query examples.

Demonstrates navigating ontology hierarchies in GO (Gene Ontology),
HPO (Human Phenotype Ontology), and MONDO (disease ontology).

Run with: python examples/ontology_queries.py
"""

import asyncio
import logging
from cogex_mcp.clients.ontology_client import OntologyClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def example_1_go_apoptosis_hierarchy():
    """
    Example 1: Navigate GO hierarchy for apoptosis.

    This example demonstrates:
    - Getting parent terms (more general biological processes)
    - Getting child terms (more specific processes)
    - Full bidirectional hierarchy traversal

    GO:0006915 = apoptotic process
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Navigate GO Hierarchy for Apoptosis")
    print("=" * 80)

    client = OntologyClient()

    # Example 1a: Get parent terms (upward to more general)
    print("\n[1a] Getting parent terms for GO:0006915 (apoptotic process)...")
    result = client.get_parent_terms(
        term="GO:0006915",
        max_depth=3,
    )

    if result["success"]:
        print(f"\nFound {result['total_parents']} parent terms:")
        for parent in result["parents"][:5]:  # Show first 5
            indent = "  " * (parent["depth"] - 1)
            print(f"{indent}↑ Depth {parent['depth']}: {parent['name']} ({parent['curie']})")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Example 1b: Get child terms (downward to more specific)
    print("\n[1b] Getting child terms for GO:0006915 (apoptotic process)...")
    result = client.get_child_terms(
        term="GO:0006915",
        max_depth=2,
    )

    if result["success"]:
        print(f"\nFound {result['total_children']} child terms:")
        for child in result["children"][:5]:  # Show first 5
            indent = "  " * child["depth"]
            print(f"{indent}↓ Depth {child['depth']}: {child['name']} ({child['curie']})")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Example 1c: Get complete local hierarchy (both directions)
    print("\n[1c] Getting complete hierarchy for GO:0006915...")
    result = client.get_hierarchy(
        term="GO:0006915",
        direction="both",
        max_depth=2,
    )

    if result["success"]:
        print(f"\nComplete local hierarchy:")
        print(f"  - {result['total_parents']} parent terms")
        print(f"  - {result['total_children']} child terms")
        print(f"\nThis term sits in a hierarchy with {result['total_parents'] + result['total_children']} related terms")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


async def example_2_hpo_phenotype_hierarchy():
    """
    Example 2: Get HPO phenotype hierarchy.

    This example demonstrates:
    - Navigating Human Phenotype Ontology
    - Understanding clinical phenotype relationships
    - Finding related symptoms and conditions

    HP:0001250 = Seizure
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Get HPO Phenotype Hierarchy for Seizures")
    print("=" * 80)

    client = OntologyClient()

    # Get seizure phenotype hierarchy
    print("\n[2a] Getting phenotype hierarchy for HP:0001250 (Seizure)...")
    result = client.get_hierarchy(
        term="HP:0001250",
        direction="both",
        max_depth=2,
    )

    if result["success"]:
        print(f"\nSeizure Phenotype Hierarchy:")
        print(f"  Query term: HP:0001250 (Seizure)")
        print(f"  Parents found: {result['total_parents']}")
        print(f"  Children found: {result['total_children']}")

        # Show parent phenotypes (broader categories)
        if result["parents"]:
            print("\n  Broader phenotype categories (parents):")
            for parent in result["parents"][:3]:
                print(f"    ↑ {parent['name']} ({parent['curie']})")

        # Show child phenotypes (more specific types)
        if result["children"]:
            print("\n  Specific seizure types (children):")
            for child in result["children"][:3]:
                print(f"    ↓ {child['name']} ({child['curie']})")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Example 2b: Explore intellectual disability hierarchy
    print("\n[2b] Getting phenotype hierarchy for HP:0001249 (Intellectual disability)...")
    result = client.get_parent_terms(
        term="HP:0001249",
        max_depth=3,
    )

    if result["success"]:
        print(f"\nIntellectual Disability - Parent Terms:")
        print(f"  Total ancestors: {result['total_parents']}")

        if result["parents"]:
            print("\n  Ancestor phenotypes:")
            for parent in result["parents"][:5]:
                indent = "  " * parent["depth"]
                print(f"  {indent}• {parent['name']} (depth {parent['depth']})")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


async def example_3_mondo_disease_ancestors():
    """
    Example 3: Find MONDO disease ancestors.

    This example demonstrates:
    - Navigating disease ontology
    - Understanding disease classification
    - Finding disease categories and subtypes

    MONDO:0004975 = Alzheimer disease
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Find MONDO Disease Ancestors for Alzheimer's")
    print("=" * 80)

    client = OntologyClient()

    # Example 3a: Get Alzheimer's disease classification
    print("\n[3a] Getting disease ancestors for MONDO:0004975 (Alzheimer disease)...")
    result = client.get_parent_terms(
        term="MONDO:0004975",
        max_depth=4,
    )

    if result["success"]:
        print(f"\nAlzheimer's Disease Classification:")
        print(f"  Query term: MONDO:0004975 (Alzheimer disease)")
        print(f"  Ancestor categories: {result['total_parents']}")

        if result["parents"]:
            print("\n  Disease hierarchy (from specific to general):")
            # Group by depth
            depth_groups = {}
            for parent in result["parents"]:
                depth = parent["depth"]
                if depth not in depth_groups:
                    depth_groups[depth] = []
                depth_groups[depth].append(parent)

            for depth in sorted(depth_groups.keys()):
                print(f"\n  Level {depth}:")
                for parent in depth_groups[depth][:2]:  # Show up to 2 per level
                    print(f"    ↑ {parent['name']} ({parent['curie']})")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Example 3b: Get diabetes subtypes
    print("\n[3b] Getting disease subtypes for MONDO:0005015 (diabetes mellitus)...")
    result = client.get_child_terms(
        term="MONDO:0005015",
        max_depth=2,
    )

    if result["success"]:
        print(f"\nDiabetes Mellitus Subtypes:")
        print(f"  Query term: MONDO:0005015 (diabetes mellitus)")
        print(f"  Subtypes found: {result['total_children']}")

        if result["children"]:
            print("\n  Specific diabetes types:")
            for child in result["children"][:5]:
                print(f"    ↓ {child['name']} ({child['curie']}) - depth {child['depth']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Example 3c: Complete hierarchy view
    print("\n[3c] Getting complete hierarchy for MONDO:0004975...")
    result = client.get_hierarchy(
        term="MONDO:0004975",
        direction="both",
        max_depth=2,
    )

    if result["success"]:
        print(f"\nAlzheimer's Disease - Complete Local Hierarchy:")
        print(f"  Ancestors: {result['total_parents']}")
        print(f"  Descendants: {result['total_children']}")

        # Summary
        total_related = result['total_parents'] + result['total_children']
        print(f"\n  This disease has {total_related} related terms in its local hierarchy")
        print(f"  (within {2} levels in each direction)")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


async def main():
    """Run all ontology query examples."""
    print("\n" + "=" * 80)
    print("INDRA CoGEx - Ontology Hierarchy Query Examples")
    print("=" * 80)
    print("\nThese examples demonstrate navigating ontology hierarchies:")
    print("  • GO (Gene Ontology) - Biological processes")
    print("  • HPO (Human Phenotype Ontology) - Clinical phenotypes")
    print("  • MONDO - Disease classification")

    try:
        # Run all examples
        await example_1_go_apoptosis_hierarchy()
        await example_2_hpo_phenotype_hierarchy()
        await example_3_mondo_disease_ancestors()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
