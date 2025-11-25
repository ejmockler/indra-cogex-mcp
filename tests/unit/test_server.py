"""
Basic tests for MCP server initialization and tool registration.

Run with: pytest tests/test_server.py -v
"""

import pytest

from cogex_mcp import mcp


def test_server_exists():
    """Test that MCP server instance exists."""
    assert mcp is not None
    assert mcp.name == "cogex_mcp"


def test_server_has_tools():
    """Test that server has all Priority 1-2 tools registered."""
    # Get list of registered tools
    tools = list(mcp._tool_manager._tools.keys()) if hasattr(mcp, '_tool_manager') else []

    # Should have all 10 Priority 1-2 tools
    assert len(tools) >= 10, f"Server should have at least 10 tools registered, found {len(tools)}"

    # Check for all Priority 1 tools
    tool_names = [tool for tool in tools]
    assert "cogex_query_gene_or_feature" in tool_names, "Tool 1 should be registered"
    assert "cogex_extract_subnetwork" in tool_names, "Tool 2 should be registered"
    assert "cogex_enrichment_analysis" in tool_names, "Tool 3 should be registered"
    assert "cogex_query_drug_or_effect" in tool_names, "Tool 4 should be registered"
    assert "cogex_query_disease_or_phenotype" in tool_names, "Tool 5 should be registered"

    # Check for all Priority 2 tools
    assert "cogex_query_pathway" in tool_names, "Tool 6 should be registered"
    assert "cogex_query_cell_line" in tool_names, "Tool 7 should be registered"
    assert "cogex_query_clinical_trials" in tool_names, "Tool 8 should be registered"
    assert "cogex_query_literature" in tool_names, "Tool 9 should be registered"
    assert "cogex_query_variants" in tool_names, "Tool 10 should be registered"


def test_tool_has_correct_annotations():
    """Test that Tool 1 has correct MCP annotations."""
    if hasattr(mcp, '_tool_manager'):
        tools = mcp._tool_manager._tools

        if "cogex_query_gene_or_feature" in tools:
            tool = tools["cogex_query_gene_or_feature"]

            # Check annotations exist
            if hasattr(tool, 'annotations'):
                annotations = tool.annotations
                assert annotations.readOnlyHint == True
                assert annotations.destructiveHint == False
                assert annotations.idempotentHint == True
                assert annotations.openWorldHint == True


@pytest.mark.asyncio
async def test_config_validation():
    """Test configuration validation."""
    from cogex_mcp.config import settings

    # Should not raise
    settings.validate_connectivity()

    # Check basic settings
    assert settings.mcp_server_name == "cogex_mcp"
    assert settings.character_limit > 0
    assert settings.cache_enabled in [True, False]


@pytest.mark.asyncio
async def test_cache_service():
    """Test cache service functionality."""
    from cogex_mcp.services.cache import get_cache

    cache = get_cache()

    # Test set/get
    await cache.set("test_key", {"data": "value"})
    result = await cache.get("test_key")

    assert result == {"data": "value"}

    # Test miss
    result = await cache.get("nonexistent_key")
    assert result is None

    # Test stats
    stats = cache.get_stats()
    assert stats.hits >= 1
    assert stats.size >= 0


@pytest.mark.asyncio
async def test_entity_resolver():
    """Test entity resolver basics."""
    from cogex_mcp.services.entity_resolver import get_resolver

    resolver = get_resolver()
    assert resolver is not None

    # Test cache key generation
    key1 = resolver._make_gene_cache_key("TP53")
    key2 = resolver._make_gene_cache_key(("hgnc", "11998"))

    assert isinstance(key1, str)
    assert isinstance(key2, str)
    assert key1 != key2


def test_formatter():
    """Test response formatter."""
    from cogex_mcp.constants import ResponseFormat
    from cogex_mcp.services.formatter import get_formatter

    formatter = get_formatter()

    # Test JSON formatting
    data = {"test": "value", "number": 42}
    json_result = formatter.format_response(data, ResponseFormat.JSON)

    assert isinstance(json_result, str)
    assert "test" in json_result
    assert "42" in json_result

    # Test Markdown formatting
    md_result = formatter.format_response(data, ResponseFormat.MARKDOWN)
    assert isinstance(md_result, str)


def test_pagination():
    """Test pagination service."""
    from cogex_mcp.services.pagination import get_pagination

    pagination = get_pagination()

    # Test pagination metadata
    items = list(range(25))
    result = pagination.paginate(
        items=items[:20],
        total_count=100,
        offset=0,
        limit=20,
    )

    assert result.total_count == 100
    assert result.count == 20
    assert result.has_more == True
    assert result.next_offset == 20

    # Test slicing
    sliced = pagination.slice_results(items, offset=5, limit=10)
    assert len(sliced) == 10
    assert sliced[0] == 5


def test_tool2_annotations():
    """Test that Tool 2 has correct MCP annotations."""
    if hasattr(mcp, '_tool_manager'):
        tools = mcp._tool_manager._tools

        if "cogex_extract_subnetwork" in tools:
            tool = tools["cogex_extract_subnetwork"]

            # Check annotations exist
            if hasattr(tool, 'annotations'):
                annotations = tool.annotations
                assert annotations.readOnlyHint == True
                assert annotations.destructiveHint == False
                assert annotations.idempotentHint == True
                assert annotations.openWorldHint == True


def test_subnetwork_schemas():
    """Test subnetwork-related schemas."""
    from cogex_mcp.schemas import SubnetworkMode, SubnetworkQuery

    # Test SubnetworkMode enum
    assert SubnetworkMode.DIRECT == "direct"
    assert SubnetworkMode.MEDIATED == "mediated"
    assert SubnetworkMode.SHARED_UPSTREAM == "shared_upstream"
    assert SubnetworkMode.SHARED_DOWNSTREAM == "shared_downstream"
    assert SubnetworkMode.SOURCE_TO_TARGETS == "source_to_targets"

    # Test SubnetworkQuery schema
    query = SubnetworkQuery(
        mode=SubnetworkMode.DIRECT,
        genes=["TP53", "MDM2"],
        max_statements=50,
    )
    assert query.mode == SubnetworkMode.DIRECT
    assert query.genes == ["TP53", "MDM2"]
    assert query.max_statements == 50
    assert query.include_evidence == False  # default

    # Test with evidence
    query_with_evidence = SubnetworkQuery(
        mode=SubnetworkMode.MEDIATED,
        genes=["BRCA1", "RAD51"],
        include_evidence=True,
        max_evidence_per_statement=3,
    )
    assert query_with_evidence.include_evidence == True
    assert query_with_evidence.max_evidence_per_statement == 3


def test_tool3_enrichment_schemas():
    """Test enrichment analysis schemas."""
    from cogex_mcp.schemas import EnrichmentQuery, EnrichmentSource, EnrichmentType

    # Test EnrichmentType enum
    assert EnrichmentType.DISCRETE == "discrete"
    assert EnrichmentType.CONTINUOUS == "continuous"
    assert EnrichmentType.SIGNED == "signed"
    assert EnrichmentType.METABOLITE == "metabolite"

    # Test EnrichmentSource enum
    assert EnrichmentSource.GO == "go"
    assert EnrichmentSource.REACTOME == "reactome"
    assert EnrichmentSource.WIKIPATHWAYS == "wikipathways"

    # Test discrete query
    query = EnrichmentQuery(
        analysis_type=EnrichmentType.DISCRETE,
        gene_list=["TP53", "MDM2", "BCL2"],
        source=EnrichmentSource.GO,
        alpha=0.05,
    )
    assert query.analysis_type == EnrichmentType.DISCRETE
    assert len(query.gene_list) == 3
    assert query.alpha == 0.05
    assert query.correction_method == "fdr_bh"  # default


def test_tool4_drug_schemas():
    """Test drug/effect query schemas."""
    from cogex_mcp.schemas import DrugEffectQuery, DrugQueryMode

    # Test DrugQueryMode enum
    assert DrugQueryMode.DRUG_TO_PROFILE == "drug_to_profile"
    assert DrugQueryMode.SIDE_EFFECT_TO_DRUGS == "side_effect_to_drugs"

    # Test drug_to_profile query
    query = DrugEffectQuery(
        mode=DrugQueryMode.DRUG_TO_PROFILE,
        drug="aspirin",
        include_targets=True,
        include_side_effects=True,
    )
    assert query.mode == DrugQueryMode.DRUG_TO_PROFILE
    assert query.drug == "aspirin"
    assert query.include_targets == True
    assert query.include_cell_lines == False  # default


def test_tool5_disease_schemas():
    """Test disease/phenotype query schemas."""
    from cogex_mcp.schemas import DiseasePhenotypeQuery, DiseaseQueryMode

    # Test DiseaseQueryMode enum
    assert DiseaseQueryMode.DISEASE_TO_MECHANISMS == "disease_to_mechanisms"
    assert DiseaseQueryMode.PHENOTYPE_TO_DISEASES == "phenotype_to_diseases"
    assert DiseaseQueryMode.CHECK_PHENOTYPE == "check_phenotype"

    # Test disease_to_mechanisms query
    query = DiseasePhenotypeQuery(
        mode=DiseaseQueryMode.DISEASE_TO_MECHANISMS,
        disease="diabetes",
        include_genes=True,
        include_drugs=True,
    )
    assert query.mode == DiseaseQueryMode.DISEASE_TO_MECHANISMS
    assert query.disease == "diabetes"
    assert query.include_genes == True


def test_tool6_pathway_schemas():
    """Test pathway query schemas."""
    from cogex_mcp.schemas import PathwayQuery, PathwayQueryMode

    # Test PathwayQueryMode enum
    assert PathwayQueryMode.GET_GENES == "get_genes"
    assert PathwayQueryMode.GET_PATHWAYS == "get_pathways"
    assert PathwayQueryMode.FIND_SHARED == "find_shared"
    assert PathwayQueryMode.CHECK_MEMBERSHIP == "check_membership"

    # Test get_pathways query
    query = PathwayQuery(
        mode=PathwayQueryMode.GET_PATHWAYS,
        gene="TP53",
    )
    assert query.mode == PathwayQueryMode.GET_PATHWAYS
    assert query.gene == "TP53"


def test_tool7_cell_line_schemas():
    """Test cell line query schemas."""
    from cogex_mcp.schemas import CellLineQuery, CellLineQueryMode

    # Test CellLineQueryMode enum
    assert CellLineQueryMode.GET_PROPERTIES == "get_properties"
    assert CellLineQueryMode.GET_MUTATED_GENES == "get_mutated_genes"
    assert CellLineQueryMode.GET_CELL_LINES_WITH_MUTATION == "get_cell_lines_with_mutation"
    assert CellLineQueryMode.CHECK_MUTATION == "check_mutation"

    # Test get_properties query
    query = CellLineQuery(
        mode=CellLineQueryMode.GET_PROPERTIES,
        cell_line="MCF7",
    )
    assert query.mode == CellLineQueryMode.GET_PROPERTIES
    assert query.cell_line == "MCF7"


def test_tool8_clinical_trials_schemas():
    """Test clinical trials query schemas."""
    from cogex_mcp.schemas import ClinicalTrialsMode, ClinicalTrialsQuery

    # Test ClinicalTrialsMode enum
    assert ClinicalTrialsMode.GET_FOR_DRUG == "get_for_drug"
    assert ClinicalTrialsMode.GET_FOR_DISEASE == "get_for_disease"
    assert ClinicalTrialsMode.GET_BY_ID == "get_by_id"

    # Test get_for_drug query
    query = ClinicalTrialsQuery(
        mode=ClinicalTrialsMode.GET_FOR_DRUG,
        drug="aspirin",
    )
    assert query.mode == ClinicalTrialsMode.GET_FOR_DRUG
    assert query.drug == "aspirin"


def test_tool9_literature_schemas():
    """Test literature query schemas."""
    from cogex_mcp.schemas import LiteratureQuery, LiteratureQueryMode

    # Test LiteratureQueryMode enum
    assert LiteratureQueryMode.GET_STATEMENTS_FOR_PMID == "get_statements_for_pmid"
    assert LiteratureQueryMode.GET_EVIDENCE_FOR_STATEMENT == "get_evidence_for_statement"
    assert LiteratureQueryMode.SEARCH_BY_MESH == "search_by_mesh"
    assert LiteratureQueryMode.GET_STATEMENTS_BY_HASHES == "get_statements_by_hashes"

    # Test get_statements_for_pmid query
    query = LiteratureQuery(
        mode=LiteratureQueryMode.GET_STATEMENTS_FOR_PMID,
        pmid="12345678",
    )
    assert query.mode == LiteratureQueryMode.GET_STATEMENTS_FOR_PMID
    assert query.pmid == "12345678"


def test_tool10_variants_schemas():
    """Test variant query schemas."""
    from cogex_mcp.schemas import VariantQuery, VariantQueryMode

    # Test VariantQueryMode enum
    assert VariantQueryMode.GET_FOR_GENE == "get_for_gene"
    assert VariantQueryMode.GET_FOR_DISEASE == "get_for_disease"
    assert VariantQueryMode.GET_FOR_PHENOTYPE == "get_for_phenotype"
    assert VariantQueryMode.VARIANT_TO_GENES == "variant_to_genes"
    assert VariantQueryMode.VARIANT_TO_PHENOTYPES == "variant_to_phenotypes"
    assert VariantQueryMode.CHECK_ASSOCIATION == "check_association"

    # Test get_for_gene query
    query = VariantQuery(
        mode=VariantQueryMode.GET_FOR_GENE,
        gene="BRCA1",
        max_p_value=1e-5,
    )
    assert query.mode == VariantQueryMode.GET_FOR_GENE
    assert query.gene == "BRCA1"
    assert query.max_p_value == 1e-5


def test_all_10_tools_registered():
    """Test that all 10 Priority 1-2 tools are registered."""
    if hasattr(mcp, '_tool_manager'):
        tools = mcp._tool_manager._tools

        expected_tools = [
            "cogex_query_gene_or_feature",
            "cogex_extract_subnetwork",
            "cogex_enrichment_analysis",
            "cogex_query_drug_or_effect",
            "cogex_query_disease_or_phenotype",
            "cogex_query_pathway",
            "cogex_query_cell_line",
            "cogex_query_clinical_trials",
            "cogex_query_literature",
            "cogex_query_variants",
        ]

        assert len(tools) >= 10, f"Server should have at least 10 tools registered, found {len(tools)}"

        for tool_name in expected_tools:
            assert tool_name in tools, f"{tool_name} should be registered"


def test_all_tools_have_annotations():
    """Test that all 10 tools have correct MCP annotations."""
    if hasattr(mcp, '_tool_manager'):
        tools = mcp._tool_manager._tools

        expected_tools = [
            "cogex_query_gene_or_feature",
            "cogex_extract_subnetwork",
            "cogex_enrichment_analysis",
            "cogex_query_drug_or_effect",
            "cogex_query_disease_or_phenotype",
            "cogex_query_pathway",
            "cogex_query_cell_line",
            "cogex_query_clinical_trials",
            "cogex_query_literature",
            "cogex_query_variants",
        ]

        for tool_name in expected_tools:
            assert tool_name in tools, f"{tool_name} should be registered"

            tool = tools[tool_name]
            if hasattr(tool, 'annotations'):
                annotations = tool.annotations
                # All tools should be read-only
                assert annotations.readOnlyHint == True
                assert annotations.destructiveHint == False
                # Tool 3 (enrichment) is not idempotent due to statistical computation
                if tool_name == "cogex_enrichment_analysis":
                    assert annotations.idempotentHint == False
                else:
                    assert annotations.idempotentHint == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
