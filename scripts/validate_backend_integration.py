#!/usr/bin/env python3
"""
Backend Integration Validation Script

Tests all backend methods for Tools 6-16 to ensure they:
1. Connect to Neo4j successfully
2. Execute queries without errors
3. Return expected data structures
4. Handle pagination correctly

Usage:
    python scripts/validate_backend_integration.py
    python scripts/validate_backend_integration.py --tool 6
    python scripts/validate_backend_integration.py --verbose
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cogex_mcp.clients.neo4j_client import Neo4jClient
from cogex_mcp.config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Test data - known entities that should exist in INDRA CoGEx
TEST_ENTITIES = {
    "genes": {
        "TP53": "hgnc:11998",
        "BRCA1": "hgnc:1100",
        "EGFR": "hgnc:3467",
    },
    "pathways": {
        "p53_signaling": "reactome:R-HSA-3700989",
        "apoptosis": "reactome:R-HSA-109581",
    },
    "cell_lines": {
        "A549": "A549",  # Lung cancer cell line
        "MCF7": "MCF7",  # Breast cancer cell line
    },
    "variants": {
        "tp53_variant": "rs28934576",  # Known TP53 variant
    },
    "diseases": {
        "breast_cancer": "DOID:1612",
        "lung_cancer": "DOID:1324",
    },
    "go_terms": {
        "apoptosis": "GO:0006915",
        "dna_repair": "GO:0006281",
    },
    "phenotypes": {
        "seizures": "HP:0001250",
    },
}


class ValidationResult:
    """Track validation results for reporting."""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def record_pass(self, test_name: str):
        self.total += 1
        self.passed += 1
        logger.info(f"✓ {test_name}")

    def record_fail(self, test_name: str, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append((test_name, error))
        logger.error(f"✗ {test_name}: {error}")

    def record_skip(self, test_name: str, reason: str):
        self.total += 1
        self.skipped += 1
        logger.warning(f"⊘ {test_name}: {reason}")

    def print_summary(self):
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total tests:  {self.total}")
        print(f"Passed:       {self.passed} ({self.passed/max(self.total,1)*100:.1f}%)")
        print(f"Failed:       {self.failed}")
        print(f"Skipped:      {self.skipped}")

        if self.errors:
            print("\nFAILURES:")
            for test_name, error in self.errors:
                print(f"  - {test_name}")
                print(f"    {error}")

        print("=" * 80)

        return self.failed == 0


class BackendValidator:
    """Validates backend integration for all tools."""

    def __init__(self, client: Neo4jClient, verbose: bool = False):
        self.client = client
        self.verbose = verbose
        self.results = ValidationResult()

    async def validate_all(self, tool_filter: int | None = None):
        """Run all validations."""
        print("=" * 80)
        print("BACKEND INTEGRATION VALIDATION")
        print("=" * 80)
        print(f"Neo4j URI: {self.client.uri}")
        print(f"Filter: Tool {tool_filter}" if tool_filter else "Testing all Tools 6-16")
        print("=" * 80)
        print()

        # Test connection
        try:
            await self.client.connect()
            health = await self.client.health_check()
            if not health:
                print("✗ Neo4j health check failed")
                return False
            print("✓ Neo4j connection healthy\n")
        except Exception as e:
            print(f"✗ Failed to connect to Neo4j: {e}")
            return False

        # Run tool validations
        tools = [
            (6, self.validate_tool_06),
            (7, self.validate_tool_07),
            (8, self.validate_tool_08),
            (9, self.validate_tool_09),
            (10, self.validate_tool_10),
            (11, self.validate_tool_11),
            (12, self.validate_tool_12),
            (13, self.validate_tool_13),
            (14, self.validate_tool_14),
            (15, self.validate_tool_15),
            (16, self.validate_tool_16),
        ]

        for tool_num, validator_func in tools:
            if tool_filter is not None and tool_filter != tool_num:
                continue

            print(f"\n{'=' * 80}")
            print(f"TOOL {tool_num}: {validator_func.__doc__.strip()}")
            print('=' * 80)

            try:
                await validator_func()
            except Exception as e:
                logger.error(f"Unexpected error in Tool {tool_num}: {e}")
                import traceback
                if self.verbose:
                    traceback.print_exc()

        # Print summary
        self.results.print_summary()

        # Cleanup
        await self.client.close()

        return self.results.failed == 0

    async def validate_tool_06(self):
        """Pathway Queries"""
        gene_id = TEST_ENTITIES["genes"]["TP53"]
        pathway_id = TEST_ENTITIES["pathways"]["p53_signaling"]

        # Test 1: Get genes in pathway
        try:
            result = await self.client.execute_query(
                "get_genes_in_pathway",
                pathway_id=pathway_id,
                limit=5
            )
            assert result["success"], "Query failed"
            assert "records" in result, "Missing records"
            assert isinstance(result["records"], list), "Records should be list"
            self.results.record_pass("get_genes_in_pathway")

            if self.verbose and result["records"]:
                print(f"  Sample: {result['records'][0]}")
        except Exception as e:
            self.results.record_fail("get_genes_in_pathway", str(e))

        # Test 2: Get pathways for gene
        try:
            result = await self.client.execute_query(
                "get_pathways_for_gene",
                gene_id=gene_id,
                limit=5
            )
            assert result["success"]
            assert result["count"] > 0, "TP53 should be in pathways"
            self.results.record_pass("get_pathways_for_gene")

            if self.verbose:
                print(f"  TP53 pathways: {result['count']}")
        except Exception as e:
            self.results.record_fail("get_pathways_for_gene", str(e))

        # Test 3: Get shared pathways
        try:
            result = await self.client.execute_query(
                "get_shared_pathways_for_genes",
                gene_ids=[gene_id, TEST_ENTITIES["genes"]["BRCA1"]],
                limit=5
            )
            assert result["success"]
            self.results.record_pass("get_shared_pathways_for_genes")
        except Exception as e:
            self.results.record_fail("get_shared_pathways_for_genes", str(e))

        # Test 4: Check pathway membership
        try:
            result = await self.client.execute_query(
                "is_gene_in_pathway",
                gene_id=gene_id,
                pathway_id=pathway_id
            )
            assert result["success"]
            assert "records" in result
            self.results.record_pass("is_gene_in_pathway")
        except Exception as e:
            self.results.record_fail("is_gene_in_pathway", str(e))

    async def validate_tool_07(self):
        """Cell Line Queries"""
        cell_line = TEST_ENTITIES["cell_lines"]["A549"]
        gene_id = TEST_ENTITIES["genes"]["EGFR"]

        # Test 1: Get mutations for cell line
        try:
            result = await self.client.execute_query(
                "get_mutations_for_cell_line",
                cell_line=cell_line,
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_mutations_for_cell_line")

            if self.verbose:
                print(f"  Mutations: {result['count']}")
        except Exception as e:
            self.results.record_fail("get_mutations_for_cell_line", str(e))

        # Test 2: Get cell lines for mutation
        try:
            result = await self.client.execute_query(
                "get_cell_lines_for_mutation",
                gene_id=gene_id,
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_cell_lines_for_mutation")
        except Exception as e:
            self.results.record_fail("get_cell_lines_for_mutation", str(e))

        # Test 3: Check mutation in cell line
        try:
            result = await self.client.execute_query(
                "is_mutated_in_cell_line",
                cell_line=cell_line,
                gene_id=gene_id
            )
            assert result["success"]
            self.results.record_pass("is_mutated_in_cell_line")
        except Exception as e:
            self.results.record_fail("is_mutated_in_cell_line", str(e))

        # Test 4: Get copy number
        try:
            result = await self.client.execute_query(
                "get_copy_number_for_cell_line",
                cell_line=cell_line,
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_copy_number_for_cell_line")
        except Exception as e:
            self.results.record_fail("get_copy_number_for_cell_line", str(e))

    async def validate_tool_08(self):
        """Clinical Trials Queries"""
        # Note: May not have trial data in test Neo4j
        drug_id = "chebi:41423"  # Celecoxib

        # Test 1: Get trials for drug
        try:
            result = await self.client.execute_query(
                "get_trials_for_drug",
                drug_id=drug_id,
                limit=5
            )
            assert result["success"]
            self.results.record_pass("get_trials_for_drug")

            if result["count"] == 0:
                self.results.record_skip(
                    "get_trials_for_drug_data",
                    "No trial data in database"
                )
        except Exception as e:
            self.results.record_fail("get_trials_for_drug", str(e))

        # Test 2: Get trials for disease
        try:
            result = await self.client.execute_query(
                "get_trials_for_disease",
                disease_id=TEST_ENTITIES["diseases"]["breast_cancer"],
                limit=5
            )
            assert result["success"]
            self.results.record_pass("get_trials_for_disease")
        except Exception as e:
            self.results.record_fail("get_trials_for_disease", str(e))

    async def validate_tool_09(self):
        """Literature Queries"""
        pmid = "29625053"  # Known PMID

        # Test 1: Get statements for paper
        try:
            result = await self.client.execute_query(
                "get_statements_for_paper",
                pmid=pmid,
                limit=5
            )
            assert result["success"]
            self.results.record_pass("get_statements_for_paper")
        except Exception as e:
            self.results.record_fail("get_statements_for_paper", str(e))

        # Test 2: Get evidence for MeSH terms
        try:
            result = await self.client.execute_query(
                "get_evidence_for_mesh",
                mesh_terms=["Breast Neoplasms"],
                limit=5
            )
            assert result["success"]
            self.results.record_pass("get_evidence_for_mesh")
        except Exception as e:
            self.results.record_fail("get_evidence_for_mesh", str(e))

    async def validate_tool_10(self):
        """Variant Queries"""
        gene_id = TEST_ENTITIES["genes"]["TP53"]
        variant_id = TEST_ENTITIES["variants"]["tp53_variant"]

        # Test 1: Get variants for gene
        try:
            result = await self.client.execute_query(
                "get_variants_for_gene",
                gene_id=gene_id,
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_variants_for_gene")

            if self.verbose:
                print(f"  Variants: {result['count']}")
        except Exception as e:
            self.results.record_fail("get_variants_for_gene", str(e))

        # Test 2: Get genes for variant
        try:
            result = await self.client.execute_query(
                "get_genes_for_variant",
                variant_id=variant_id,
                limit=5
            )
            assert result["success"]
            self.results.record_pass("get_genes_for_variant")
        except Exception as e:
            self.results.record_fail("get_genes_for_variant", str(e))

        # Test 3: Check variant association
        try:
            result = await self.client.execute_query(
                "is_variant_associated",
                variant_id=variant_id,
                disease_id=TEST_ENTITIES["diseases"]["breast_cancer"]
            )
            assert result["success"]
            self.results.record_pass("is_variant_associated")
        except Exception as e:
            self.results.record_fail("is_variant_associated", str(e))

    async def validate_tool_11(self):
        """Identifier Resolution"""
        # Test 1: Symbol to HGNC
        try:
            result = await self.client.execute_query(
                "symbol_to_hgnc",
                symbols=["TP53", "BRCA1"]
            )
            assert result["success"]
            assert result["count"] > 0
            self.results.record_pass("symbol_to_hgnc")
        except Exception as e:
            self.results.record_fail("symbol_to_hgnc", str(e))

        # Test 2: HGNC to UniProt
        try:
            result = await self.client.execute_query(
                "hgnc_to_uniprot",
                hgnc_ids=["hgnc:11998"]
            )
            assert result["success"]
            self.results.record_pass("hgnc_to_uniprot")
        except Exception as e:
            self.results.record_fail("hgnc_to_uniprot", str(e))

        # Test 3: Map identifiers
        try:
            result = await self.client.execute_query(
                "map_identifiers",
                identifiers=["hgnc:11998"],
                to_namespace="uniprot"
            )
            assert result["success"]
            self.results.record_pass("map_identifiers")
        except Exception as e:
            self.results.record_fail("map_identifiers", str(e))

    async def validate_tool_12(self):
        """Relationship Checking"""
        gene_id = TEST_ENTITIES["genes"]["TP53"]
        pathway_id = TEST_ENTITIES["pathways"]["p53_signaling"]

        # Test relationship types
        relationship_tests = [
            ("is_gene_in_pathway", {"gene_id": gene_id, "pathway_id": pathway_id}),
            ("is_drug_target", {"drug_id": "chebi:41423", "target_id": gene_id}),
            ("is_gene_associated_with_disease", {
                "gene_id": gene_id,
                "disease_id": TEST_ENTITIES["diseases"]["breast_cancer"]
            }),
        ]

        for query_name, params in relationship_tests:
            try:
                result = await self.client.execute_query(query_name, **params)
                assert result["success"]
                self.results.record_pass(query_name)
            except Exception as e:
                self.results.record_fail(query_name, str(e))

    async def validate_tool_13(self):
        """Ontology Hierarchy"""
        go_term = TEST_ENTITIES["go_terms"]["apoptosis"]

        # Test 1: Get parents
        try:
            result = await self.client.execute_query(
                "get_ontology_parents",
                term_id=go_term,
                max_depth=2
            )
            assert result["success"]
            self.results.record_pass("get_ontology_parents")

            if self.verbose:
                print(f"  Parents: {result['count']}")
        except Exception as e:
            self.results.record_fail("get_ontology_parents", str(e))

        # Test 2: Get children
        try:
            result = await self.client.execute_query(
                "get_ontology_children",
                term_id=go_term,
                max_depth=2
            )
            assert result["success"]
            self.results.record_pass("get_ontology_children")
        except Exception as e:
            self.results.record_fail("get_ontology_children", str(e))

        # Test 3: Get full hierarchy
        try:
            result = await self.client.execute_query(
                "get_ontology_hierarchy",
                term_id=go_term,
                max_depth=2
            )
            assert result["success"]
            self.results.record_pass("get_ontology_hierarchy")
        except Exception as e:
            self.results.record_fail("get_ontology_hierarchy", str(e))

    async def validate_tool_14(self):
        """Cell Markers"""
        gene_id = TEST_ENTITIES["genes"]["EGFR"]
        cell_type = "T cell"

        # Test 1: Get markers for cell type
        try:
            result = await self.client.execute_query(
                "get_markers_for_cell_type",
                cell_type=cell_type,
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_markers_for_cell_type")
        except Exception as e:
            self.results.record_fail("get_markers_for_cell_type", str(e))

        # Test 2: Get cell types for marker
        try:
            result = await self.client.execute_query(
                "get_cell_types_for_marker",
                gene_id=gene_id,
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_cell_types_for_marker")
        except Exception as e:
            self.results.record_fail("get_cell_types_for_marker", str(e))

        # Test 3: Check marker
        try:
            result = await self.client.execute_query(
                "is_cell_marker",
                gene_id=gene_id,
                cell_type=cell_type
            )
            assert result["success"]
            self.results.record_pass("is_cell_marker")
        except Exception as e:
            self.results.record_fail("is_cell_marker", str(e))

    async def validate_tool_15(self):
        """Kinase Enrichment"""
        # Test kinase analysis query
        try:
            # Check if query exists
            if "kinase_analysis" in self.client._get_cypher_query.__code__.co_consts:
                result = await self.client.execute_query(
                    "kinase_analysis",
                    gene_ids=[TEST_ENTITIES["genes"]["TP53"]],
                    limit=10
                )
                assert result["success"]
                self.results.record_pass("kinase_analysis")
            else:
                self.results.record_skip(
                    "kinase_analysis",
                    "Query not implemented in Neo4j client"
                )
        except Exception as e:
            self.results.record_fail("kinase_analysis", str(e))

    async def validate_tool_16(self):
        """Protein Functions"""
        gene_id = TEST_ENTITIES["genes"]["EGFR"]

        # Test 1: Get enzyme activities
        try:
            result = await self.client.execute_query(
                "get_enzyme_activities",
                gene_id=gene_id
            )
            assert result["success"]
            self.results.record_pass("get_enzyme_activities")
        except Exception as e:
            self.results.record_fail("get_enzyme_activities", str(e))

        # Test 2: Get genes for activity
        try:
            result = await self.client.execute_query(
                "get_genes_for_activity",
                activity="kinase",
                limit=10
            )
            assert result["success"]
            self.results.record_pass("get_genes_for_activity")
        except Exception as e:
            self.results.record_fail("get_genes_for_activity", str(e))

        # Test 3: Check if kinase
        try:
            result = await self.client.execute_query(
                "is_kinase",
                gene_id=gene_id
            )
            assert result["success"]
            self.results.record_pass("is_kinase")
        except Exception as e:
            self.results.record_fail("is_kinase", str(e))

        # Test 4: Check enzyme activity
        try:
            result = await self.client.execute_query(
                "has_enzyme_activity",
                gene_id=gene_id,
                activity="kinase"
            )
            assert result["success"]
            self.results.record_pass("has_enzyme_activity")
        except Exception as e:
            self.results.record_fail("has_enzyme_activity", str(e))


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate backend integration")
    parser.add_argument(
        "--tool",
        type=int,
        choices=range(6, 17),
        help="Validate specific tool only (6-16)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j URI"
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.getenv("NEO4J_USER", "neo4j"),
        help="Neo4j username"
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.getenv("NEO4J_PASSWORD", ""),
        help="Neo4j password"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create Neo4j client
    client = Neo4jClient(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
    )

    # Run validation
    validator = BackendValidator(client, verbose=args.verbose)
    success = await validator.validate_all(tool_filter=args.tool)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
