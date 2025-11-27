"""
Cell Marker Query Examples for INDRA CoGEx MCP Server

This module demonstrates how to use the CellMarkerClient to query cell type
markers and their expression patterns in the INDRA CoGEx knowledge graph.

The CellMarkerClient provides three main query modes:
1. get_cell_type_markers - Get marker genes for a specific cell type
2. get_marker_cell_types - Get cell types expressing a specific marker gene
3. check_marker_status - Check if a gene is a marker for a specific cell type

All examples use the @autoclient() decorator which automatically manages the
Neo4j connection.
"""

import asyncio
import logging
from typing import Dict, Any

from cogex_mcp.clients.cell_marker_client import CellMarkerClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Example 1: Get T cell markers
async def example_t_cell_markers():
    """
    Example 1: Query marker genes for T cells.

    This demonstrates how to retrieve all known marker genes for a specific
    cell type. T cells are a critical component of the adaptive immune system,
    and their markers include CD3, CD4, CD8, and others.

    Expected markers include:
    - CD3D, CD3E, CD3G (T cell receptor complex)
    - CD4 (helper T cells)
    - CD8A, CD8B (cytotoxic T cells)
    - CD2, CD5, CD7 (pan-T cell markers)
    """
    print("\n" + "="*70)
    print("Example 1: T Cell Markers")
    print("="*70)

    client = CellMarkerClient()

    # Query T cell markers
    result = client.get_cell_type_markers(
        cell_type="T cell",
        species="human",
        tissue="blood",  # Filter to blood tissue
    )

    if result["success"]:
        print(f"\n✓ Found {result['total_markers']} T cell markers")
        print(f"  Cell type: {result['cell_type']}")
        print(f"  Species: {result['species']}")
        print(f"  Tissue: {result.get('tissue', 'N/A')}")

        if result["markers"]:
            print(f"\nTop {min(10, len(result['markers']))} markers:")

            for i, marker in enumerate(result["markers"][:10], 1):
                gene = marker["gene"]
                print(f"  {i}. {gene['name']} ({gene['curie']})")
                print(f"     Type: {marker['marker_type']}")
                print(f"     Evidence: {marker['evidence']}")

            # Highlight key markers if found
            marker_names = {m["gene"]["name"] for m in result["markers"]}
            key_markers = {"CD3D", "CD3E", "CD4", "CD8A", "CD2"}
            found_key = marker_names.intersection(key_markers)

            if found_key:
                print(f"\n  ✓ Key T cell markers found: {', '.join(sorted(found_key))}")
        else:
            print("\n  Note: No markers found (database may have limited data)")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 2: Find cell types expressing CD4
async def example_cd4_cell_types():
    """
    Example 2: Find cell types that express CD4 as a marker.

    This demonstrates reverse lookup - given a marker gene, find all cell
    types where it's expressed. CD4 is primarily known as a helper T cell
    marker, but may also be found in other immune cells.

    Expected cell types:
    - T cell (helper T cells)
    - Thymocyte (T cell precursors)
    - Possibly: Monocyte, Macrophage (low expression)
    """
    print("\n" + "="*70)
    print("Example 2: Cell Types Expressing CD4")
    print("="*70)

    client = CellMarkerClient()

    # Query cell types for CD4 marker
    result = client.get_marker_cell_types(
        marker_gene="CD4",
        species="human",
    )

    if result["success"]:
        print(f"\n✓ Found {result['total_cell_types']} cell types expressing CD4")
        print(f"  Marker: {result['marker_gene']}")
        print(f"  Species: {result['species']}")

        if result["cell_types"]:
            print(f"\nCell types:")

            for i, cell_type in enumerate(result["cell_types"], 1):
                print(f"  {i}. {cell_type['name']}")
                print(f"     Tissue: {cell_type.get('tissue', 'N/A')}")
                print(f"     Species: {cell_type.get('species', 'human')}")
                print(f"     Markers: {cell_type.get('marker_count', '?')}")

            # Check if T cells are in the results
            cell_type_names = {ct["name"].lower() for ct in result["cell_types"]}
            if any("t cell" in name or "thymocyte" in name for name in cell_type_names):
                print("\n  ✓ Expected T cell types found!")
        else:
            print("\n  Note: No cell types found (database may have limited data)")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 3: Check if CD8A is a T cell marker
async def example_check_cd8a_t_cell():
    """
    Example 3: Check if CD8A is a marker for T cells.

    This demonstrates a boolean check for marker status. CD8A (CD8 alpha chain)
    is a well-known marker for cytotoxic T cells, so we expect this to return
    True.

    CD8A is:
    - Part of the CD8 co-receptor complex
    - Expressed on cytotoxic T cells
    - Binds to MHC class I molecules
    - Critical for T cell recognition of infected cells
    """
    print("\n" + "="*70)
    print("Example 3: Check if CD8A is a T Cell Marker")
    print("="*70)

    client = CellMarkerClient()

    # Check marker status
    result = client.check_marker_status(
        cell_type="T cell",
        marker_gene="CD8A",
    )

    if result["success"]:
        is_marker = result["is_marker"]
        status = "✓ YES" if is_marker else "✗ NO"

        print(f"\nMarker: {result['marker_gene']} ({result['gene_id']})")
        print(f"Cell type: {result['cell_type']}")
        print(f"Is marker: {status}")

        if is_marker:
            print("\n  ✓ CD8A is confirmed as a T cell marker")
            print("    CD8A is expressed on cytotoxic T cells and marks")
            print("    cells capable of direct target cell killing.")
        else:
            print("\n  ✗ CD8A not found as T cell marker")
            print("    (This is unexpected - may indicate database limitations)")
    else:
        print(f"✗ Query failed: {result.get('error', 'Unknown error')}")

    return result


# Example 4: Compare B cell and T cell markers
async def example_compare_b_t_cell_markers():
    """
    Example 4: Compare marker genes between B cells and T cells.

    This demonstrates how to use the client to compare marker profiles
    across different cell types. B cells and T cells have distinct marker
    profiles reflecting their different immune functions.

    Expected B cell markers: CD19, CD20, CD79A, CD79B
    Expected T cell markers: CD3D, CD3E, CD4, CD8A
    """
    print("\n" + "="*70)
    print("Example 4: Compare B Cell and T Cell Markers")
    print("="*70)

    client = CellMarkerClient()

    # Get B cell markers
    print("\nQuerying B cell markers...")
    b_cell_result = client.get_cell_type_markers(
        cell_type="B cell",
        species="human",
    )

    # Get T cell markers
    print("Querying T cell markers...")
    t_cell_result = client.get_cell_type_markers(
        cell_type="T cell",
        species="human",
    )

    # Compare results
    if b_cell_result["success"] and t_cell_result["success"]:
        b_markers = {m["gene"]["name"] for m in b_cell_result["markers"]}
        t_markers = {m["gene"]["name"] for m in t_cell_result["markers"]}

        print(f"\n✓ B cells: {b_cell_result['total_markers']} markers")
        print(f"  Top markers: {', '.join(list(b_markers)[:5])}")

        print(f"\n✓ T cells: {t_cell_result['total_markers']} markers")
        print(f"  Top markers: {', '.join(list(t_markers)[:5])}")

        # Find shared and unique markers
        shared = b_markers.intersection(t_markers)
        b_unique = b_markers - t_markers
        t_unique = t_markers - b_markers

        if shared:
            print(f"\nShared markers ({len(shared)}): {', '.join(sorted(shared)[:5])}")

        if b_unique:
            print(f"\nB cell-specific ({len(b_unique)}): {', '.join(sorted(b_unique)[:5])}")

        if t_unique:
            print(f"\nT cell-specific ({len(t_unique)}): {', '.join(sorted(t_unique)[:5])}")

        # Verify expected markers
        expected_b = {"CD19", "CD20", "MS4A1"}  # MS4A1 is CD20
        expected_t = {"CD3D", "CD3E", "CD4", "CD8A"}

        found_b = b_markers.intersection(expected_b)
        found_t = t_markers.intersection(expected_t)

        if found_b:
            print(f"\n  ✓ Expected B cell markers found: {', '.join(sorted(found_b))}")
        if found_t:
            print(f"  ✓ Expected T cell markers found: {', '.join(sorted(found_t))}")
    else:
        if not b_cell_result["success"]:
            print(f"✗ B cell query failed: {b_cell_result.get('error', 'Unknown')}")
        if not t_cell_result["success"]:
            print(f"✗ T cell query failed: {t_cell_result.get('error', 'Unknown')}")

    return {"b_cells": b_cell_result, "t_cells": t_cell_result}


# Example 5: Tissue-specific marker analysis
async def example_tissue_specific_markers():
    """
    Example 5: Analyze tissue-specific markers for T cells.

    This demonstrates how to filter markers by tissue to understand
    tissue-specific expression patterns. T cells are found in various
    tissues with potentially different marker profiles.

    Tissues of interest:
    - Blood (circulating T cells)
    - Lymph node (activated T cells)
    - Thymus (T cell development)
    - Spleen (immune response)
    """
    print("\n" + "="*70)
    print("Example 5: Tissue-Specific T Cell Markers")
    print("="*70)

    client = CellMarkerClient()

    tissues = ["blood", "lymph node", "thymus", "spleen"]
    tissue_markers = {}

    for tissue in tissues:
        print(f"\nQuerying T cells in {tissue}...")
        result = client.get_cell_type_markers(
            cell_type="T cell",
            species="human",
            tissue=tissue,
        )

        if result["success"]:
            marker_count = result["total_markers"]
            tissue_markers[tissue] = {
                "count": marker_count,
                "markers": {m["gene"]["name"] for m in result["markers"]}
            }
            print(f"  ✓ Found {marker_count} markers")

            if result["markers"]:
                top_3 = [m["gene"]["name"] for m in result["markers"][:3]]
                print(f"    Top 3: {', '.join(top_3)}")
        else:
            print(f"  ✗ Query failed or no data")
            tissue_markers[tissue] = {"count": 0, "markers": set()}

    # Summary
    print("\n" + "-"*70)
    print("Summary:")
    total_unique = set()
    for tissue, data in tissue_markers.items():
        total_unique.update(data["markers"])
        print(f"  {tissue}: {data['count']} markers")

    print(f"\nTotal unique markers across all tissues: {len(total_unique)}")

    if total_unique:
        print(f"Examples: {', '.join(list(total_unique)[:5])}")

    return tissue_markers


# Example 6: Error handling
async def example_error_handling():
    """
    Example 6: Demonstrate proper error handling.

    This shows how to handle various conditions that may occur during
    cell marker queries, including unknown cell types and markers.
    """
    print("\n" + "="*70)
    print("Example 6: Error Handling Examples")
    print("="*70)

    client = CellMarkerClient()

    # Test 6a: Unknown cell type
    print("\nTest 6a: Unknown cell type")
    result = client.get_cell_type_markers(
        cell_type="Nonexistent Cell Type XYZ",
        species="human",
    )

    if result["success"]:
        print(f"  ✓ Query succeeded (returned {result['total_markers']} markers)")
        if result['total_markers'] == 0:
            print("    No markers found for unknown cell type (expected)")
    else:
        print(f"  Error: {result.get('error', 'Unknown')}")

    # Test 6b: Unknown marker gene
    print("\nTest 6b: Unknown marker gene")
    result = client.get_marker_cell_types(
        marker_gene="FAKE_GENE_XYZ",
        species="human",
    )

    if result["success"]:
        print(f"  ✓ Query succeeded (returned {result['total_cell_types']} cell types)")
        if result['total_cell_types'] == 0:
            print("    No cell types found for unknown marker (expected)")
    else:
        print(f"  Error: {result.get('error', 'Unknown')}")

    # Test 6c: False marker check
    print("\nTest 6c: Check non-marker gene")
    result = client.check_marker_status(
        cell_type="T cell",
        marker_gene="ALB",  # Albumin - not a T cell marker
    )

    if result["success"]:
        is_marker = result["is_marker"]
        status = "YES" if is_marker else "NO"
        print(f"  ✓ ALB is T cell marker: {status}")
        if not is_marker:
            print("    Correctly identified as non-marker (expected)")
    else:
        print(f"  Error: {result.get('error', 'Unknown')}")


# Main execution
async def main():
    """
    Run all cell marker query examples.

    This demonstrates the complete CellMarkerClient API with realistic
    use cases for cell type marker analysis.
    """
    print("\n" + "="*70)
    print("INDRA CoGEx CellMarkerClient Examples")
    print("="*70)
    print("\nDemonstrating cell type marker queries using the")
    print("INDRA CoGEx knowledge graph.\n")

    try:
        # Run all examples
        await example_t_cell_markers()
        await example_cd4_cell_types()
        await example_check_cd8a_t_cell()
        await example_compare_b_t_cell_markers()
        await example_tissue_specific_markers()
        await example_error_handling()

        print("\n" + "="*70)
        print("All examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
