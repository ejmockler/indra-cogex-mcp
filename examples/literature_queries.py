"""
Literature query examples using LiteratureClient.

Demonstrates:
1. Extracting statements from famous papers
2. Getting evidence for specific statements
3. Searching autophagy literature by MeSH
4. Batch retrieving statements by hashes
"""

import asyncio
import os
from indra_cogex.client.neo4j_client import Neo4jClient

from cogex_mcp.clients.literature_client import LiteratureClient


async def main():
    """Run all literature query examples."""
    # Setup Neo4j connection
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")

    # Create Neo4j client
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    # Verify connection
    try:
        await driver.verify_connectivity()
        print(f"Connected to Neo4j at {uri}\n")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        print("Please ensure Neo4j is running and credentials are correct.")
        return

    # Create literature client (using synchronous version for examples)
    # In real usage, you'd use the async Neo4j client
    from indra_cogex.client.neo4j_client import Neo4jClient as SyncNeo4jClient

    # For demonstration, we'll create a synchronous client
    sync_client = SyncNeo4jClient(url=uri.replace("bolt://", "neo4j://"),
                                   username=user,
                                   password=password)
    literature_client = LiteratureClient(neo4j_client=sync_client)

    print("=" * 80)
    print("INDRA CoGEx Literature Query Examples")
    print("=" * 80)
    print()

    # Example 1: Extract statements from a paper
    await example_1_extract_paper_statements(literature_client)

    # Example 2: Get evidence for a specific statement
    await example_2_get_statement_evidence(literature_client)

    # Example 3: Search autophagy literature by MeSH
    await example_3_mesh_search(literature_client)

    # Example 4: Batch retrieve statements
    await example_4_batch_retrieval(literature_client)

    await driver.close()
    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


async def example_1_extract_paper_statements(client: LiteratureClient):
    """
    Example 1: Extract INDRA statements from a famous paper.

    This example demonstrates:
    - Extracting mechanistic statements from a PubMed publication
    - Including evidence text snippets
    - Exploring statement types and agents
    """
    print("Example 1: Extract Statements from Famous Paper")
    print("-" * 80)

    # Use a well-known PMID (you may need to adjust based on your database)
    pmid = "28746307"  # Example PMID - adjust as needed

    try:
        result = client.get_paper_statements(
            pmid=pmid,
            include_evidence_text=True,
            max_evidence_per_statement=3,
        )

        if result["success"] and result["total_statements"] > 0:
            print(f"PMID: {pmid}")
            print(f"Total statements extracted: {result['total_statements']}")
            print()

            # Show first 5 statements
            for i, stmt in enumerate(result["statements"][:5], 1):
                print(f"Statement {i}:")
                print(f"  Type: {stmt['stmt_type']}")
                print(f"  Subject: {stmt['subject']['name']} ({stmt['subject']['curie']})")
                print(f"  Object: {stmt['object']['name']} ({stmt['object']['curie']})")
                print(f"  Belief: {stmt['belief_score']:.2f}")
                print(f"  Evidence count: {stmt['evidence_count']}")

                # Show evidence if available
                if stmt.get("evidence") and len(stmt["evidence"]) > 0:
                    print(f"  Sample evidence:")
                    for j, ev in enumerate(stmt["evidence"][:2], 1):
                        print(f"    {j}. [{ev['source_api']}] {ev['text'][:100]}...")

                print()

            print(f"(Showing 5 of {result['total_statements']} statements)")

        else:
            print(f"No statements found for PMID {pmid}")
            print("Try adjusting the PMID to one in your database.")

    except Exception as e:
        print(f"Error: {e}")

    print()


async def example_2_get_statement_evidence(client: LiteratureClient):
    """
    Example 2: Get evidence for a specific INDRA statement.

    This example demonstrates:
    - Retrieving evidence supporting a statement
    - Examining evidence sources (REACH, Sparser, etc.)
    - Viewing evidence text snippets and PMIDs
    """
    print("Example 2: Get Evidence for Specific Statement")
    print("-" * 80)

    # First, get a statement hash from a paper
    pmid = "28746307"

    try:
        # Get statements from paper
        stmt_result = client.get_paper_statements(
            pmid=pmid,
            include_evidence_text=False,
        )

        if stmt_result["total_statements"] > 0:
            # Get first statement's hash
            stmt = stmt_result["statements"][0]
            stmt_hash = stmt["stmt_hash"]

            print(f"Statement: {stmt['subject']['name']} → {stmt['object']['name']}")
            print(f"Type: {stmt['stmt_type']}")
            print(f"Hash: {stmt_hash}")
            print()

            # Get full evidence for this statement
            ev_result = client.get_statement_evidence(
                statement_hash=stmt_hash,
                include_evidence_text=True,
            )

            if ev_result["total_evidence"] > 0:
                print(f"Total evidence: {ev_result['total_evidence']}")
                print()

                # Show first 3 evidence entries
                for i, ev in enumerate(ev_result["evidence"][:3], 1):
                    print(f"Evidence {i}:")
                    print(f"  Source: {ev['source_api']}")
                    print(f"  PMID: {ev.get('pmid', 'N/A')}")
                    if ev.get("text"):
                        print(f"  Text: {ev['text'][:150]}...")
                    print()

                print(f"(Showing 3 of {ev_result['total_evidence']} evidence entries)")

            else:
                print("No evidence found for this statement.")

        else:
            print(f"No statements found in PMID {pmid}")

    except Exception as e:
        print(f"Error: {e}")

    print()


async def example_3_mesh_search(client: LiteratureClient):
    """
    Example 3: Search autophagy literature by MeSH terms.

    This example demonstrates:
    - Searching PubMed by MeSH (Medical Subject Headings) terms
    - Combining multiple MeSH terms
    - Getting publication PMIDs and URLs
    """
    print("Example 3: Search Autophagy Literature by MeSH")
    print("-" * 80)

    # Search for autophagy and cancer papers
    mesh_terms = ["autophagy", "cancer"]

    try:
        result = client.search_mesh_literature(
            mesh_terms=mesh_terms,
        )

        if result["success"] and result["total_publications"] > 0:
            print(f"MeSH terms: {', '.join(mesh_terms)}")
            print(f"Total publications: {result['total_publications']}")
            print()

            # Show first 10 publications
            for i, pub in enumerate(result["publications"][:10], 1):
                print(f"{i}. PMID: {pub['pmid']}")
                print(f"   URL: {pub['url']}")
                print()

            print(f"(Showing 10 of {result['total_publications']} publications)")

            print()
            print("You can retrieve statements from any of these PMIDs using:")
            print(f"  client.get_paper_statements(pmid='{result['publications'][0]['pmid']}')")

        else:
            print(f"No publications found for MeSH terms: {mesh_terms}")
            print("Try different MeSH terms or check your database.")

    except Exception as e:
        print(f"Error: {e}")

    print()


async def example_4_batch_retrieval(client: LiteratureClient):
    """
    Example 4: Batch retrieve statements by hashes.

    This example demonstrates:
    - Batch retrieval of multiple statements
    - Efficient bulk loading of statement data
    - Reconstructing networks or pathways
    """
    print("Example 4: Batch Retrieve Statements by Hashes")
    print("-" * 80)

    # First, get some statement hashes
    pmid = "28746307"

    try:
        # Get statements from paper
        stmt_result = client.get_paper_statements(
            pmid=pmid,
            include_evidence_text=False,
        )

        if stmt_result["total_statements"] >= 2:
            # Collect first 3 statement hashes
            hashes = [
                stmt["stmt_hash"]
                for stmt in stmt_result["statements"][:3]
                if stmt.get("stmt_hash")
            ]

            if len(hashes) >= 2:
                print(f"Batch retrieving {len(hashes)} statements")
                print()

                # Batch retrieve with evidence
                batch_result = client.get_statements_by_hashes(
                    statement_hashes=hashes,
                    include_evidence_text=True,
                    max_evidence_per_statement=2,
                )

                if batch_result["total_statements"] > 0:
                    print(f"Retrieved {batch_result['total_statements']} statements")
                    print()

                    # Show each statement
                    for i, stmt in enumerate(batch_result["statements"], 1):
                        print(f"Statement {i}:")
                        print(f"  Hash: {stmt['stmt_hash']}")
                        print(f"  Type: {stmt['stmt_type']}")
                        print(f"  {stmt['subject']['name']} → {stmt['object']['name']}")
                        print(f"  Evidence: {len(stmt.get('evidence', []))} entries")
                        print()

                else:
                    print("No statements retrieved.")

            else:
                print("Not enough statements with hashes found.")

        else:
            print(f"Not enough statements in PMID {pmid}")

    except Exception as e:
        print(f"Error: {e}")

    print()


if __name__ == "__main__":
    # Run examples
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
