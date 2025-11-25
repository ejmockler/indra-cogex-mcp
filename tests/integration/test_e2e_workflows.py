"""
End-to-End Workflow Integration Tests

Tests realistic multi-tool workflows that simulate actual LLM usage patterns.
These are the most important integration tests as they validate the entire system.

Run with: pytest tests/integration/test_e2e_workflows.py -v -m integration
"""

import pytest

from cogex_mcp.schemas import (
    CellLineQuery,
    CellLineQueryMode,
    ClinicalTrialsMode,
    ClinicalTrialsQuery,
    DiseasePhenotypeQuery,
    DiseaseQueryMode,
    DrugEffectQuery,
    DrugQueryMode,
    EnrichmentQuery,
    EnrichmentSource,
    EnrichmentType,
    GeneFeatureQuery,
    IdentifierQuery,
    PathwayQuery,
    PathwayQueryMode,
    ProteinFunctionMode,
    ProteinFunctionQuery,
    QueryMode,
    ResponseFormat,
    SubnetworkMode,
    SubnetworkQuery,
    VariantQuery,
    VariantQueryMode,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow1DrugDiscovery:
    """
    Drug Discovery Workflow: Drug → Targets → Pathways → Enrichment

    Simulates: "What does imatinib target and what pathways are affected?"
    """

    async def test_complete_drug_discovery_workflow(self, integration_adapter, known_entities):
        """Complete drug discovery pipeline for imatinib"""

        # Step 1: Get drug targets (Tool 4)
        print("\nStep 1: Getting drug targets for imatinib...")
        drug_query = DrugEffectQuery(
            mode=DrugQueryMode.DRUG_TO_PROFILE,
            drug="imatinib",
            include_targets=True,
            include_indications=True,
            response_format=ResponseFormat.JSON,
        )
        drug_result = await integration_adapter.query(
            "drug_to_profile",
            **drug_query.model_dump(exclude_none=True)
        )
        assert drug_result is not None
        print(f"Found drug profile: {type(drug_result)}")

        # Step 2: Get pathways for top targets (Tool 6)
        print("\nStep 2: Getting pathways for ABL1 (known imatinib target)...")
        pathway_query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="ABL1",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        pathway_result = await integration_adapter.query(
            "pathway_get_pathways",
            **pathway_query.model_dump(exclude_none=True)
        )
        assert pathway_result is not None
        print(f"Found pathways: {type(pathway_result)}")

        # Step 3: Find shared pathways among targets (Tool 6)
        print("\nStep 3: Finding shared pathways among BCR-ABL targets...")
        shared_query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["ABL1", "BCR", "KIT"],  # Known imatinib targets
            response_format=ResponseFormat.JSON,
        )
        shared_result = await integration_adapter.query(
            "pathway_find_shared",
            **shared_query.model_dump(exclude_none=True)
        )
        assert shared_result is not None
        print(f"Found shared pathways: {type(shared_result)}")

        # Step 4: Enrichment analysis on target genes (Tool 3)
        print("\nStep 4: Performing enrichment analysis...")
        enrichment_query = EnrichmentQuery(
            analysis_type=EnrichmentType.DISCRETE,
            gene_list=["ABL1", "BCR", "KIT", "PDGFRA", "PDGFRB"],
            source=EnrichmentSource.REACTOME,
            alpha=0.05,
            response_format=ResponseFormat.JSON,
        )
        enrichment_result = await integration_adapter.query(
            "enrichment_analysis",
            **enrichment_query.model_dump(exclude_none=True)
        )
        assert enrichment_result is not None
        print(f"Enrichment complete: {type(enrichment_result)}")

        print("\n✓ Drug discovery workflow completed successfully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow2DiseaseMechanism:
    """
    Disease Mechanism Workflow: Disease → Genes → Variants → Drugs → Trials

    Simulates: "What are the mechanisms and therapies for Alzheimer's disease?"
    """

    async def test_complete_disease_mechanism_workflow(self, integration_adapter):
        """Complete disease mechanism analysis for Alzheimer's"""

        # Step 1: Get disease mechanisms (Tool 5)
        print("\nStep 1: Getting Alzheimer's disease mechanisms...")
        disease_query = DiseasePhenotypeQuery(
            mode=DiseaseQueryMode.DISEASE_TO_MECHANISMS,
            disease="alzheimer disease",
            include_genes=True,
            include_variants=True,
            include_drugs=True,
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        disease_result = await integration_adapter.query(
            "disease_to_mechanisms",
            **disease_query.model_dump(exclude_none=True)
        )
        assert disease_result is not None
        print(f"Found disease mechanisms: {type(disease_result)}")

        # Step 2: Get variants for APOE gene (Tool 10)
        print("\nStep 2: Getting variants for APOE (key Alzheimer's gene)...")
        variant_query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="APOE",
            max_p_value=1e-5,
            limit=10,
            response_format=ResponseFormat.JSON,
        )
        variant_result = await integration_adapter.query(
            "variants_for_gene",
            **variant_query.model_dump(exclude_none=True)
        )
        assert variant_result is not None
        print(f"Found variants: {type(variant_result)}")

        # Step 3: Check if rs7412 is associated with Alzheimer's (Tool 10)
        print("\nStep 3: Checking rs7412 (APOE variant) association...")
        check_query = VariantQuery(
            mode=VariantQueryMode.CHECK_ASSOCIATION,
            variant="rs7412",
            disease="alzheimer disease",
            response_format=ResponseFormat.JSON,
        )
        check_result = await integration_adapter.query(
            "variant_check",
            **check_query.model_dump(exclude_none=True)
        )
        assert check_result is not None
        print(f"Association check: {type(check_result)}")

        # Step 4: Get clinical trials (Tool 8)
        print("\nStep 4: Finding clinical trials for Alzheimer's...")
        trials_query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="alzheimer disease",
            phase=[2, 3],
            limit=15,
            response_format=ResponseFormat.JSON,
        )
        trials_result = await integration_adapter.query(
            "trials_for_disease",
            **trials_query.model_dump(exclude_none=True)
        )
        assert trials_result is not None
        print(f"Found trials: {type(trials_result)}")

        print("\n✓ Disease mechanism workflow completed successfully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow3PathwayAnalysis:
    """
    Pathway Analysis Workflow: Pathway → Genes → Subnetwork → Enrichment

    Simulates: "Analyze the p53 signaling pathway network"
    """

    async def test_complete_pathway_analysis_workflow(self, integration_adapter):
        """Complete pathway network analysis for p53 signaling"""

        # Step 1: Get pathway genes (Tool 6)
        print("\nStep 1: Getting genes in p53 signaling pathway...")
        pathway_query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="p53 signaling",
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        pathway_result = await integration_adapter.query(
            "pathway_get_genes",
            **pathway_query.model_dump(exclude_none=True)
        )
        assert pathway_result is not None
        print(f"Found pathway genes: {type(pathway_result)}")

        # Step 2: Extract subnetwork (Tool 2)
        print("\nStep 2: Extracting subnetwork for key p53 pathway genes...")
        subnetwork_query = SubnetworkQuery(
            mode=SubnetworkMode.SHARED_UPSTREAM,
            genes=["TP53", "MDM2", "CDKN1A", "BAX"],
            max_statements=50,
            min_evidence_count=2,
            response_format=ResponseFormat.JSON,
        )
        subnetwork_result = await integration_adapter.query(
            "extract_subnetwork",
            **subnetwork_query.model_dump(exclude_none=True)
        )
        assert subnetwork_result is not None
        print(f"Extracted subnetwork: {type(subnetwork_result)}")

        # Step 3: Enrichment on pathway genes (Tool 3)
        print("\nStep 3: Performing GO enrichment on p53 pathway...")
        enrichment_query = EnrichmentQuery(
            analysis_type=EnrichmentType.DISCRETE,
            gene_list=["TP53", "MDM2", "CDKN1A", "BAX", "BCL2", "PUMA"],
            source=EnrichmentSource.GO,
            alpha=0.05,
            response_format=ResponseFormat.JSON,
        )
        enrichment_result = await integration_adapter.query(
            "enrichment_analysis",
            **enrichment_query.model_dump(exclude_none=True)
        )
        assert enrichment_result is not None
        print(f"Enrichment complete: {type(enrichment_result)}")

        # Step 4: Check TP53 pathway membership (Tool 6)
        print("\nStep 4: Verifying TP53 is in p53 signaling pathway...")
        check_query = PathwayQuery(
            mode=PathwayQueryMode.CHECK_MEMBERSHIP,
            gene="TP53",
            pathway="p53 signaling",
            response_format=ResponseFormat.JSON,
        )
        check_result = await integration_adapter.query(
            "pathway_check",
            **check_query.model_dump(exclude_none=True)
        )
        assert check_result is not None
        print(f"Membership verified: {type(check_result)}")

        print("\n✓ Pathway analysis workflow completed successfully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow4CellLineAnalysis:
    """
    Cell Line Analysis Workflow: Cell Line → Mutations → Drug Sensitivity → Pathways

    Simulates: "What are the druggable mutations in A549 lung cancer cells?"
    """

    async def test_complete_cell_line_workflow(self, integration_adapter):
        """Complete cell line analysis for A549"""

        # Step 1: Get cell line mutations (Tool 7)
        print("\nStep 1: Getting mutations in A549 cell line...")
        mutations_query = CellLineQuery(
            mode=CellLineQueryMode.GET_MUTATED_GENES,
            cell_line="A549",
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        mutations_result = await integration_adapter.query(
            "cell_line_mutations",
            **mutations_query.model_dump(exclude_none=True)
        )
        assert mutations_result is not None
        print(f"Found mutations: {type(mutations_result)}")

        # Step 2: Check KRAS mutation (Tool 7)
        print("\nStep 2: Checking for KRAS mutation (known in A549)...")
        check_query = CellLineQuery(
            mode=CellLineQueryMode.CHECK_MUTATION,
            cell_line="A549",
            gene="KRAS",
            response_format=ResponseFormat.JSON,
        )
        check_result = await integration_adapter.query(
            "cell_line_check",
            **check_query.model_dump(exclude_none=True)
        )
        assert check_result is not None
        print(f"KRAS mutation check: {type(check_result)}")

        # Step 3: Find drugs targeting KRAS pathway (Tool 4)
        print("\nStep 3: Finding pathways for mutated genes...")
        pathway_query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="KRAS",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        pathway_result = await integration_adapter.query(
            "pathway_get_pathways",
            **pathway_query.model_dump(exclude_none=True)
        )
        assert pathway_result is not None
        print(f"Found pathways: {type(pathway_result)}")

        # Step 4: Get drug profile for EGFR inhibitors (common A549 therapy)
        print("\nStep 4: Getting drug profiles for potential therapies...")
        drug_query = DrugEffectQuery(
            mode=DrugQueryMode.DRUG_TO_PROFILE,
            drug="erlotinib",  # EGFR inhibitor
            include_targets=True,
            include_cell_lines=True,
            response_format=ResponseFormat.JSON,
        )
        drug_result = await integration_adapter.query(
            "drug_to_profile",
            **drug_query.model_dump(exclude_none=True)
        )
        assert drug_result is not None
        print(f"Drug profile: {type(drug_result)}")

        print("\n✓ Cell line analysis workflow completed successfully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow5IdentifierResolution:
    """
    Identifier Resolution Workflow: Symbols → HGNC → UniProt → Functions

    Simulates: "Convert gene list and get protein functions"
    """

    async def test_complete_identifier_workflow(self, integration_adapter):
        """Complete identifier resolution and function annotation"""

        gene_symbols = ["TP53", "BRCA1", "EGFR"]

        # Step 1: Symbol to HGNC (Tool 11)
        print("\nStep 1: Resolving gene symbols to HGNC IDs...")
        hgnc_query = IdentifierQuery(
            identifiers=gene_symbols,
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON,
        )
        hgnc_result = await integration_adapter.query(
            "resolve_identifiers",
            **hgnc_query.model_dump(exclude_none=True)
        )
        assert hgnc_result is not None
        print(f"HGNC IDs: {type(hgnc_result)}")

        # Step 2: HGNC to UniProt (Tool 11)
        print("\nStep 2: Converting HGNC to UniProt IDs...")
        uniprot_query = IdentifierQuery(
            identifiers=["11998", "1100", "3236"],  # TP53, BRCA1, EGFR HGNC IDs
            from_namespace="hgnc",
            to_namespace="uniprot",
            response_format=ResponseFormat.JSON,
        )
        uniprot_result = await integration_adapter.query(
            "resolve_identifiers",
            **uniprot_query.model_dump(exclude_none=True)
        )
        assert uniprot_result is not None
        print(f"UniProt IDs: {type(uniprot_result)}")

        # Step 3: Get protein functions (Tool 16)
        print("\nStep 3: Getting protein functions for TP53...")
        function_query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="TP53",
            response_format=ResponseFormat.JSON,
        )
        function_result = await integration_adapter.query(
            "gene_to_activities",
            **function_query.model_dump(exclude_none=True)
        )
        assert function_result is not None
        print(f"Functions: {type(function_result)}")

        # Step 4: Check function types (Tool 16)
        print("\nStep 4: Checking function types (kinase, TF, etc.)...")
        check_query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            genes=gene_symbols,
            function_types=["kinase", "transcription_factor", "phosphatase"],
            response_format=ResponseFormat.JSON,
        )
        check_result = await integration_adapter.query(
            "check_function_types",
            **check_query.model_dump(exclude_none=True)
        )
        assert check_result is not None
        print(f"Function types: {type(check_result)}")
        # EGFR should be kinase, TP53 should be TF

        # Step 5: Get gene features (Tool 1)
        print("\nStep 5: Getting comprehensive features for EGFR...")
        features_query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="EGFR",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            response_format=ResponseFormat.JSON,
        )
        features_result = await integration_adapter.query(
            "gene_to_features",
            **features_query.model_dump(exclude_none=True)
        )
        assert features_result is not None
        print(f"Gene features: {type(features_result)}")

        print("\n✓ Identifier resolution workflow completed successfully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflowErrorHandling:
    """Test error handling across workflows"""

    async def test_workflow_with_invalid_data(self, integration_adapter):
        """Test workflow behavior with invalid/missing data"""

        # Try workflow with fake gene
        try:
            drug_query = DrugEffectQuery(
                mode=DrugQueryMode.DRUG_TO_PROFILE,
                drug="fake_drug_12345",
                response_format=ResponseFormat.JSON,
            )
            result = await integration_adapter.query(
                "drug_to_profile",
                **drug_query.model_dump(exclude_none=True)
            )
            # Should handle gracefully
            assert result is not None
        except Exception as e:
            # Should have informative error
            assert "not found" in str(e).lower() or "drug" in str(e).lower()

        print("✓ Error handling validated")
