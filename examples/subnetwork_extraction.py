"""
INDRA CoGEx Subnetwork Extraction Examples

This file demonstrates practical usage of the subnetwork extraction tool
for biological research. Each example is copy-pasteable and runnable.

Requirements:
    - INDRA CoGEx MCP server configured with Neo4j credentials
    - Python 3.10+ with mcp library installed

Setup:
    # Set environment variables
    export NEO4J_URL="bolt://your-server:7687"
    export NEO4J_USER="neo4j"
    export NEO4J_PASSWORD="your_password"

    # Run examples
    python examples/subnetwork_extraction.py
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ==============================================================================
# Example 1: Direct TP53-MDM2 Interaction Network
# ==============================================================================
# Scientific Context:
#   TP53 (tumor suppressor p53) and MDM2 (E3 ubiquitin ligase) form a critical
#   negative feedback loop. MDM2 inhibits TP53, while TP53 activates MDM2
#   transcription. This is a textbook example of regulatory biology.
#
# Use Case:
#   Understanding direct mechanistic interactions between known interaction
#   partners. Useful for validating known biology and discovering specific
#   mechanisms (phosphorylation sites, activation, etc.).
# ==============================================================================

async def example_1_direct_tp53_mdm2():
    """
    Example 1: Direct TP53-MDM2 interaction network

    Expected Output:
        - Phosphorylation events (MDM2 phosphorylates TP53)
        - Activation/Inhibition relationships
        - Ubiquitination events
        - 10-20 high-confidence statements
    """
    print("\n" + "="*80)
    print("Example 1: Direct TP53-MDM2 Interaction Network")
    print("="*80)

    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",  # Update with your credentials
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "direct",
                    "genes": ["TP53", "MDM2"],
                    "min_evidence_count": 2,  # High-confidence only
                    "min_belief_score": 0.7,
                    "max_statements": 50,
                    "response_format": "json"
                }
            )

            data = json.loads(result.content[0].text)

            print(f"\nNetwork Statistics:")
            print(f"  Nodes: {data['statistics']['node_count']}")
            print(f"  Edges: {data['statistics']['edge_count']}")
            print(f"  Statement Types: {data['statistics']['statement_types']}")
            print(f"  Avg Evidence/Statement: {data['statistics']['avg_evidence_per_statement']:.1f}")
            print(f"  Avg Belief Score: {data['statistics']['avg_belief_score']:.2f}")

            print(f"\nSample Statements:")
            for stmt in data['statements'][:3]:
                print(f"  {stmt['subject']['name']} --{stmt['stmt_type']}--> {stmt['object']['name']}")
                print(f"    Evidence: {stmt['evidence_count']}, Belief: {stmt['belief_score']:.2f}")
                if stmt.get('residue') and stmt.get('position'):
                    print(f"    Site: {stmt['residue']}{stmt['position']}")


# ==============================================================================
# Example 2: ALS Gene Mediated Pathways
# ==============================================================================
# Scientific Context:
#   Amyotrophic Lateral Sclerosis (ALS) involves multiple genes: SOD1, TARDBP,
#   FUS, and C9orf72. Understanding how these genes connect through intermediates
#   reveals shared pathways and potential therapeutic targets.
#
# Use Case:
#   Disease mechanism discovery. Find how disease genes connect through common
#   pathways, revealing potential drug targets in the intermediary nodes.
#
# Reference:
#   Mejzini et al. (2019). "ALS Genetics, Mechanisms, and Therapeutics"
#   Front. Neurosci. 13:1247
# ==============================================================================

async def example_2_als_mediated_pathways():
    """
    Example 2: ALS gene mediated pathways

    Expected Output:
        - Two-hop paths connecting ALS genes
        - Intermediary proteins (potential drug targets)
        - RNA processing and protein aggregation mechanisms
        - 30-50 mediated connections
    """
    print("\n" + "="*80)
    print("Example 2: ALS Gene Mediated Pathways")
    print("="*80)

    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "mediated",
                    "genes": ["SOD1", "TARDBP", "FUS", "C9orf72"],
                    "min_evidence_count": 3,
                    "max_statements": 100,
                    "response_format": "json"
                }
            )

            data = json.loads(result.content[0].text)

            print(f"\nALS Pathway Analysis:")
            print(f"  Total Nodes: {data['statistics']['node_count']}")
            print(f"  Mediated Paths: {data['statistics']['edge_count']}")
            print(f"  Mechanism Types: {list(data['statistics']['statement_types'].keys())}")

            # Identify intermediary nodes (not in original gene list)
            als_genes = {"SOD1", "TARDBP", "FUS", "C9orf72"}
            intermediaries = [
                node for node in data['nodes']
                if node['name'] not in als_genes
            ]

            print(f"\nPotential Therapeutic Targets (Intermediaries):")
            for node in intermediaries[:5]:
                print(f"  - {node['name']} ({node['curie']})")

            print(f"\nNote: {data.get('note', '')}")


# ==============================================================================
# Example 3: Apoptosis Shared Regulators
# ==============================================================================
# Scientific Context:
#   Apoptosis genes like BAX, BCL2, and CASP3 are regulated by common upstream
#   signals. Finding shared regulators reveals master control points.
#
# Use Case:
#   Master regulator discovery. Identify proteins that coordinate multiple
#   pathway components, useful for understanding disease and finding drug targets.
# ==============================================================================

async def example_3_apoptosis_shared_regulators():
    """
    Example 3: Apoptosis shared regulators

    Expected Output:
        - TP53 as major regulator
        - BCL2 family regulators
        - Kinases controlling apoptosis
        - 20-40 regulatory relationships
    """
    print("\n" + "="*80)
    print("Example 3: Apoptosis Shared Regulators")
    print("="*80)

    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "shared_upstream",
                    "genes": ["BAX", "BCL2", "CASP3", "CASP9"],
                    "statement_types": ["Activation", "Inhibition", "Phosphorylation"],
                    "min_evidence_count": 2,
                    "max_statements": 100,
                    "response_format": "json"
                }
            )

            data = json.loads(result.content[0].text)

            # Note: Backend may not support shared_upstream yet
            if data.get('note') and 'not yet implemented' in data['note']:
                print(f"\n{data['note']}")
                print("This mode will be available in a future release.")
                return

            print(f"\nShared Regulator Analysis:")
            print(f"  Target Genes: 4 (BAX, BCL2, CASP3, CASP9)")
            print(f"  Shared Regulators: {data['statistics']['node_count'] - 4}")
            print(f"  Regulatory Edges: {data['statistics']['edge_count']}")

            # Group statements by regulator
            regulators = {}
            for stmt in data['statements']:
                reg = stmt['subject']['name']
                if reg not in regulators:
                    regulators[reg] = []
                regulators[reg].append(stmt['object']['name'])

            print(f"\nTop Master Regulators:")
            for reg, targets in sorted(regulators.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                print(f"  {reg} -> {', '.join(set(targets))}")


# ==============================================================================
# Example 4: Brain-Specific Alzheimer's Network
# ==============================================================================
# Scientific Context:
#   Alzheimer's disease genes (APP, PSEN1, MAPT) interact in brain-specific
#   contexts. Tissue filtering reveals brain-relevant mechanisms.
#
# Use Case:
#   Tissue-specific disease modeling. Filter mechanisms by tissue context to
#   focus on disease-relevant biology and avoid confounding from other tissues.
# ==============================================================================

async def example_4_brain_alzheimers_network():
    """
    Example 4: Brain-specific Alzheimer's network

    Expected Output:
        - Brain-expressed interactions only
        - APP processing mechanisms
        - Tau phosphorylation events
        - Neuronal-specific pathways
    """
    print("\n" + "="*80)
    print("Example 4: Brain-Specific Alzheimer's Network")
    print("="*80)

    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # First query: Direct interactions
            result_direct = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "direct",
                    "genes": ["APP", "PSEN1", "MAPT"],
                    "tissue_filter": "brain",  # Brain-specific
                    "min_evidence_count": 1,
                    "max_statements": 50,
                    "response_format": "json"
                }
            )

            data_direct = json.loads(result_direct.content[0].text)

            print(f"\nBrain-Specific Direct Interactions:")
            print(f"  Edges: {data_direct['statistics']['edge_count']}")

            # Second query: Mediated paths
            result_mediated = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "mediated",
                    "genes": ["APP", "PSEN1", "MAPT"],
                    "tissue_filter": "brain",
                    "min_evidence_count": 2,
                    "max_statements": 100,
                    "response_format": "json"
                }
            )

            data_mediated = json.loads(result_mediated.content[0].text)

            print(f"\nBrain-Specific Mediated Pathways:")
            print(f"  Intermediaries: {data_mediated['statistics']['node_count'] - 3}")
            print(f"  Paths: {data_mediated['statistics']['edge_count']}")

            print(f"\nComparison:")
            print(f"  Direct edges: {data_direct['statistics']['edge_count']}")
            print(f"  Mediated paths: {data_mediated['statistics']['edge_count']}")
            print(f"  Enrichment: {data_mediated['statistics']['edge_count'] / max(1, data_direct['statistics']['edge_count']):.1f}x")


# ==============================================================================
# Example 5: Autophagy GO-Filtered Network
# ==============================================================================
# Scientific Context:
#   Autophagy is a cellular recycling process. Filtering by GO term "autophagy"
#   (GO:0006914) focuses on genes with this specific function.
#
# Use Case:
#   Pathway-centric analysis. Build networks restricted to specific biological
#   processes, useful for understanding pathway-specific mechanisms.
# ==============================================================================

async def example_5_autophagy_go_filtered():
    """
    Example 5: Autophagy GO-filtered network

    Expected Output:
        - Genes annotated with autophagy GO terms
        - Autophagy-specific mechanisms
        - mTOR pathway interactions
        - ULK1/ATG protein interactions
    """
    print("\n" + "="*80)
    print("Example 5: Autophagy GO-Filtered Network")
    print("="*80)

    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "direct",
                    "genes": ["MTOR", "ULK1", "ATG5", "ATG7", "BECN1"],
                    "go_filter": "GO:0006914",  # Autophagy process
                    "min_evidence_count": 2,
                    "max_statements": 100,
                    "response_format": "json"
                }
            )

            data = json.loads(result.content[0].text)

            print(f"\nAutophagy Network (GO:0006914 filtered):")
            print(f"  Core Genes: 5")
            print(f"  Total Nodes: {data['statistics']['node_count']}")
            print(f"  Autophagy-Specific Edges: {data['statistics']['edge_count']}")

            print(f"\nMechanism Distribution:")
            for mech, count in data['statistics']['statement_types'].items():
                print(f"  {mech}: {count}")

            print(f"\nKey Regulatory Hubs:")
            # Find nodes with most connections
            node_degrees = {}
            for stmt in data['statements']:
                subj = stmt['subject']['name']
                obj = stmt['object']['name']
                node_degrees[subj] = node_degrees.get(subj, 0) + 1
                node_degrees[obj] = node_degrees.get(obj, 0) + 1

            for node, degree in sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {node}: {degree} connections")


# ==============================================================================
# Example 6: Advanced Filtering and Customization
# ==============================================================================
# Scientific Context:
#   MAPK signaling is a complex cascade involving phosphorylation events.
#   This example demonstrates advanced filtering to focus on specific mechanisms.
#
# Use Case:
#   Precision mechanism discovery. Combine multiple filters to extract
#   highly specific subnetworks (e.g., only phosphorylation events with
#   high evidence support in a specific pathway).
# ==============================================================================

async def example_6_advanced_filtering():
    """
    Example 6: Advanced filtering and customization

    Demonstrates:
        - Multiple statement type filters
        - High confidence thresholds
        - Evidence requirements
        - Source-to-targets mode for downstream analysis

    Expected Output:
        - Only high-confidence phosphorylation events
        - Well-supported activation cascades
        - Detailed evidence information
    """
    print("\n" + "="*80)
    print("Example 6: Advanced Filtering - MAPK Phosphorylation Cascade")
    print("="*80)

    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Query 1: High-confidence phosphorylation cascade
            result1 = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "direct",
                    "genes": ["MAPK1", "MAP2K1", "RAF1", "KRAS"],
                    "statement_types": ["Phosphorylation"],  # Only phosphorylation
                    "min_evidence_count": 5,  # Strong evidence only
                    "min_belief_score": 0.8,  # High confidence
                    "include_evidence": True,  # Get evidence details
                    "max_evidence_per_statement": 3,
                    "max_statements": 50,
                    "response_format": "json"
                }
            )

            data1 = json.loads(result1.content[0].text)

            print(f"\nHigh-Confidence Phosphorylation Events:")
            print(f"  Total Events: {data1['statistics']['edge_count']}")
            print(f"  Avg Evidence: {data1['statistics']['avg_evidence_per_statement']:.1f}")
            print(f"  Avg Belief: {data1['statistics']['avg_belief_score']:.2f}")

            # Show detailed evidence for top statements
            print(f"\nDetailed Evidence (Top 3 Events):")
            for i, stmt in enumerate(data1['statements'][:3], 1):
                print(f"\n  {i}. {stmt['subject']['name']} phosphorylates {stmt['object']['name']}")
                if stmt.get('residue') and stmt.get('position'):
                    print(f"     Site: {stmt['residue']}{stmt['position']}")
                print(f"     Evidence Count: {stmt['evidence_count']}")
                print(f"     Belief Score: {stmt['belief_score']:.2f}")
                print(f"     Sources: {', '.join(stmt['sources'])}")
                if stmt.get('evidence'):
                    print(f"     Sample Evidence:")
                    for ev in stmt['evidence'][:2]:
                        print(f"       - {ev.get('text', 'N/A')[:100]}...")

            # Query 2: Downstream targets of MAPK1
            result2 = await session.call_tool(
                "cogex_extract_subnetwork",
                arguments={
                    "mode": "source_to_targets",
                    "source_gene": "MAPK1",
                    "target_genes": ["FOS", "JUN", "ELK1", "MYC"],
                    "statement_types": ["Phosphorylation", "Activation"],
                    "min_evidence_count": 2,
                    "max_statements": 100,
                    "response_format": "json"
                }
            )

            data2 = json.loads(result2.content[0].text)

            print(f"\n\nMAPK1 Downstream Signaling:")
            print(f"  Source: {data2['source_gene']['name']}")
            print(f"  Targets Queried: 4 (FOS, JUN, ELK1, MYC)")
            print(f"  Confirmed Targets: {data2['statistics']['node_count'] - 1}")
            print(f"  Total Edges: {data2['statistics']['edge_count']}")

            print(f"\nMechanism Breakdown:")
            for mech, count in data2['statistics']['statement_types'].items():
                print(f"  {mech}: {count} events")


# ==============================================================================
# Main Execution
# ==============================================================================

async def main():
    """Run all examples sequentially."""
    print("="*80)
    print("INDRA CoGEx Subnetwork Extraction Examples")
    print("="*80)
    print("\nThese examples demonstrate practical usage of the subnetwork extraction")
    print("tool for biological research. Update Neo4j credentials in each example.")
    print("\nExamples:")
    print("  1. Direct TP53-MDM2 interaction network")
    print("  2. ALS gene mediated pathways")
    print("  3. Apoptosis shared regulators")
    print("  4. Brain-specific Alzheimer's network")
    print("  5. Autophagy GO-filtered network")
    print("  6. Advanced filtering and customization")

    choice = input("\nRun which example? (1-6, or 'all'): ").strip()

    examples = {
        '1': example_1_direct_tp53_mdm2,
        '2': example_2_als_mediated_pathways,
        '3': example_3_apoptosis_shared_regulators,
        '4': example_4_brain_alzheimers_network,
        '5': example_5_autophagy_go_filtered,
        '6': example_6_advanced_filtering,
    }

    if choice.lower() == 'all':
        for func in examples.values():
            await func()
    elif choice in examples:
        await examples[choice]()
    else:
        print(f"Invalid choice: {choice}")
        return

    print("\n" + "="*80)
    print("Examples completed!")
    print("="*80)


if __name__ == "__main__":
    # Note: Update Neo4j credentials in each example function before running
    print("\n⚠️  IMPORTANT: Update Neo4j credentials in example functions before running!")
    print("   Each example has placeholders that need your actual credentials.\n")

    asyncio.run(main())
