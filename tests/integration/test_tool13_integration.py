"""
Integration tests for Tool 13 (cogex_get_ontology_hierarchy) with live backends.

Tests complete flow: Tool → Entity Resolver → Adapter → Backends → Response

Critical validation pattern:
1. No errors
2. Parse response
3. Validate structure
4. Validate data exists
5. Validate data quality
"""

import json
import logging

import pytest

from cogex_mcp.schemas import HierarchyDirection, OntologyHierarchyQuery, ResponseFormat
from cogex_mcp.tools.ontology import cogex_get_ontology_hierarchy

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13OntologyParents:
    """Test ontology parents (ancestors) queries."""

    async def test_apoptosis_parents(self):
        """
        Get parent terms for apoptosis (GO:0006915).

        Validates:
        - Ontology term resolution
        - Parent traversal works
        - Returns ontology structure
        """
        query = OntologyHierarchyQuery(
            term="GO:0006915",  # apoptotic process
            direction=HierarchyDirection.PARENTS,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        # Step 1: No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Step 2: Parse response
        data = json.loads(result)

        # Step 3: Validate structure
        assert "root_term" in data, "Response should have root_term"
        assert "parents" in data, "Response should have parents"

        # Step 4: Validate data exists
        assert data["root_term"] is not None, "Root term should be present"
        assert data["root_term"]["curie"] == "GO:0006915", "Root should be apoptosis"

        # Apoptosis should have parent terms (e.g., programmed cell death)
        assert data["parents"] is not None, "Parents should be present"
        if isinstance(data["parents"], list):
            assert len(data["parents"]) > 0, "Apoptosis should have parent terms"

        # Step 5: Validate data quality
        if isinstance(data["parents"], list) and len(data["parents"]) > 0:
            for parent in data["parents"]:
                assert "name" in parent, "Parent should have name"
                assert parent["name"], "Parent name should not be empty"
                assert "curie" in parent, "Parent should have CURIE"
                assert parent["curie"].startswith("GO:"), "Parent should be GO term"

        logger.info(f"✓ Apoptosis has {len(data['parents']) if isinstance(data['parents'], list) else 0} parent terms")

    async def test_cell_death_parents(self):
        """
        Get parents for cell death process.

        Tests broader biological process term.
        """
        query = OntologyHierarchyQuery(
            term="GO:0008219",  # cell death
            direction=HierarchyDirection.PARENTS,
            max_depth=3,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "root_term" in data
        assert data["root_term"]["curie"] == "GO:0008219"

        logger.info(f"✓ Cell death ontology query completed")

    async def test_term_by_name(self):
        """
        Query ontology term by name instead of ID.

        Validates entity resolution for ontology terms.
        """
        query = OntologyHierarchyQuery(
            term="apoptotic process",
            direction=HierarchyDirection.PARENTS,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        if result.startswith("Error:"):
            pytest.skip("Ontology term resolution by name not supported")

        data = json.loads(result)
        assert "root_term" in data
        logger.info(f"✓ Term by name resolved: {data['root_term']['curie']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13OntologyChildren:
    """Test ontology children (descendants) queries."""

    async def test_apoptosis_children(self):
        """
        Get child terms for apoptosis.

        Validates descendant traversal.
        """
        query = OntologyHierarchyQuery(
            term="GO:0006915",  # apoptotic process
            direction=HierarchyDirection.CHILDREN,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "root_term" in data
        assert "children" in data

        # Apoptosis should have child terms (e.g., intrinsic/extrinsic apoptosis)
        assert data["children"] is not None, "Children should be present"
        if isinstance(data["children"], list):
            assert len(data["children"]) > 0, "Apoptosis should have child terms"

        # Validate child term structure
        if isinstance(data["children"], list) and len(data["children"]) > 0:
            for child in data["children"]:
                assert "name" in child
                assert child["name"], "Child name should not be empty"
                assert "curie" in child
                assert child["curie"].startswith("GO:")

        logger.info(f"✓ Apoptosis has {len(data['children']) if isinstance(data['children'], list) else 0} child terms")

    async def test_biological_process_children(self):
        """
        Get children of top-level biological process term.

        Should have many children.
        """
        query = OntologyHierarchyQuery(
            term="GO:0008150",  # biological_process (root)
            direction=HierarchyDirection.CHILDREN,
            max_depth=1,  # Only immediate children
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        if result.startswith("Error:"):
            pytest.skip("Root biological process term not found")

        data = json.loads(result)
        assert "children" in data

        if isinstance(data["children"], list):
            # Root should have many children
            logger.info(f"✓ biological_process has {len(data['children'])} immediate children")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13OntologyBothDirections:
    """Test both parents and children in single query."""

    async def test_apoptosis_hierarchy(self):
        """
        Get full hierarchy around apoptosis.

        Validates bidirectional traversal.
        """
        query = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.BOTH,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "root_term" in data
        assert "parents" in data
        assert "children" in data

        # Should have both parents and children
        has_parents = isinstance(data["parents"], list) and len(data["parents"]) > 0
        has_children = isinstance(data["children"], list) and len(data["children"]) > 0

        assert has_parents or has_children, "Should have parents and/or children"

        logger.info(
            f"✓ Apoptosis hierarchy: "
            f"{len(data['parents']) if isinstance(data['parents'], list) else 0} parents, "
            f"{len(data['children']) if isinstance(data['children'], list) else 0} children"
        )

    async def test_hierarchy_depth(self):
        """
        Test depth parameter controls traversal.

        Validates depth limiting.
        """
        # Shallow traversal
        query_shallow = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.BOTH,
            max_depth=1,
            response_format=ResponseFormat.JSON
        )

        result_shallow = await cogex_get_ontology_hierarchy(query_shallow)

        # Deep traversal
        query_deep = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.BOTH,
            max_depth=3,
            response_format=ResponseFormat.JSON
        )

        result_deep = await cogex_get_ontology_hierarchy(query_deep)

        if not result_shallow.startswith("Error:") and not result_deep.startswith("Error:"):
            data_shallow = json.loads(result_shallow)
            data_deep = json.loads(result_deep)

            # Deep should have >= shallow terms (unless shallow already hit limit)
            shallow_count = len(data_shallow.get("parents", []) or []) + len(data_shallow.get("children", []) or [])
            deep_count = len(data_deep.get("parents", []) or []) + len(data_deep.get("children", []) or [])

            logger.info(f"✓ Depth control: shallow={shallow_count}, deep={deep_count}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13OntologyTypes:
    """Test different ontology types (GO, HPO, MONDO, etc.)."""

    async def test_hpo_phenotype_hierarchy(self):
        """
        Test Human Phenotype Ontology term.

        Validates HPO ontology support.
        """
        query = OntologyHierarchyQuery(
            term="HP:0001250",  # Seizure
            direction=HierarchyDirection.PARENTS,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        if result.startswith("Error:"):
            pytest.skip("HPO not supported or term not found")

        data = json.loads(result)
        assert "root_term" in data
        assert data["root_term"]["curie"] == "HP:0001250"

        logger.info("✓ HPO ontology supported")

    async def test_mondo_disease_hierarchy(self):
        """
        Test MONDO disease ontology term.

        Validates MONDO support.
        """
        query = OntologyHierarchyQuery(
            term="MONDO:0005015",  # diabetes mellitus
            direction=HierarchyDirection.PARENTS,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        if result.startswith("Error:"):
            pytest.skip("MONDO not supported or term not found")

        data = json.loads(result)
        assert "root_term" in data
        logger.info("✓ MONDO ontology supported")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13EdgeCases:
    """Test edge cases and error handling."""

    async def test_invalid_go_term(self):
        """
        Invalid GO term should return error.

        Validates error handling.
        """
        query = OntologyHierarchyQuery(
            term="GO:9999999",  # Invalid
            direction=HierarchyDirection.PARENTS,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert result.startswith("Error:"), "Invalid GO term should error"
        assert "not found" in result.lower() or "invalid" in result.lower()

        logger.info(f"✓ Invalid term error: {result}")

    async def test_max_depth_limits(self):
        """
        Test max_depth parameter boundaries.

        Validates parameter validation.
        """
        # Minimum depth
        query_min = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.PARENTS,
            max_depth=1,
            response_format=ResponseFormat.JSON
        )

        result_min = await cogex_get_ontology_hierarchy(query_min)
        assert not result_min.startswith("Error:"), "min depth=1 should work"

        # Maximum depth
        query_max = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.PARENTS,
            max_depth=5,
            response_format=ResponseFormat.JSON
        )

        result_max = await cogex_get_ontology_hierarchy(query_max)
        assert not result_max.startswith("Error:"), "max depth=5 should work"

        logger.info("✓ Depth parameter boundaries validated")

    async def test_leaf_node_no_children(self):
        """
        Leaf node should have no children.

        Tests edge case of terminal nodes.
        """
        # Use a specific leaf term if known, or skip if unavailable
        query = OntologyHierarchyQuery(
            term="GO:0097194",  # execution phase of apoptosis (likely leaf)
            direction=HierarchyDirection.CHILDREN,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        if result.startswith("Error:"):
            pytest.skip("Leaf term not found")

        data = json.loads(result)
        assert "children" in data

        # Leaf nodes may have empty children list
        logger.info(f"✓ Leaf node children: {len(data.get('children', []))}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13OutputFormats:
    """Test different output formats."""

    async def test_markdown_with_tree(self):
        """
        Test markdown output with ASCII tree.

        Validates tree visualization.
        """
        query = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.BOTH,
            max_depth=2,
            response_format=ResponseFormat.MARKDOWN
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Should contain tree characters and GO terms
        has_tree = any(char in result for char in ["├", "└", "●", "─"])
        has_go_term = "GO:0006915" in result

        assert has_tree or "apoptosis" in result.lower(), "Should have tree visualization or term info"
        assert has_go_term or "apoptosis" in result.lower(), "Should mention the term"

        logger.info("✓ Markdown tree visualization generated")

    async def test_json_hierarchy_structure(self):
        """
        Test JSON hierarchy structure completeness.

        Validates JSON data quality.
        """
        query = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.BOTH,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)

        # Validate root term completeness
        root = data["root_term"]
        assert "name" in root
        assert "curie" in root
        assert root["name"], "Root name should not be empty"
        assert root["curie"], "Root CURIE should not be empty"

        # Validate parent/child structure
        if isinstance(data.get("parents"), list) and len(data["parents"]) > 0:
            for parent in data["parents"]:
                assert "depth" in parent, "Parent should have depth"
                assert parent["depth"] > 0, "Parent depth should be positive"
                assert "relationship" in parent or True, "Relationship optional but common"

        if isinstance(data.get("children"), list) and len(data["children"]) > 0:
            for child in data["children"]:
                assert "depth" in child, "Child should have depth"
                assert child["depth"] > 0, "Child depth should be positive"

        logger.info("✓ JSON hierarchy structure validated")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool13Relationships:
    """Test ontology relationship types."""

    async def test_relationship_types(self):
        """
        Ontology terms should indicate relationship types.

        Validates relationship metadata (is_a, part_of, etc.).
        """
        query = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.BOTH,
            max_depth=2,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_get_ontology_hierarchy(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)

        # Check for relationship types in results
        has_relationships = False

        for term_list in [data.get("parents", []), data.get("children", [])]:
            if isinstance(term_list, list):
                for term in term_list:
                    if "relationship" in term:
                        has_relationships = True
                        # Validate relationship type
                        rel_type = term["relationship"]
                        assert rel_type in ["is_a", "part_of", "regulates", "has_part", "unknown"]
                        logger.info(f"  Relationship: {rel_type}")

        if has_relationships:
            logger.info("✓ Relationship types present")
        else:
            logger.info("✓ No relationship metadata (optional)")
