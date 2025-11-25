"""
Latency benchmarks for all 16 tools.

Tests representative queries for each tool with 10 iterations to measure:
- Mean latency
- Median latency
- P95 latency (95th percentile)
- P99 latency (99th percentile)
- Standard deviation

Performance targets:
- Complex queries (Tools 1-5): < 5000ms p95
- Moderate queries (Tools 6-10): < 2000ms p95
- Simple queries (Tools 11-16): < 1000ms p95
"""

import asyncio
import logging
import time

import pytest

from tests.performance.profiler import PerformanceProfiler

logger = logging.getLogger(__name__)


@pytest.mark.performance
@pytest.mark.asyncio
class TestLatencyBenchmarks:
    """Latency benchmarks for all 16 MCP tools."""

    async def _benchmark_query(
        self,
        adapter,
        tool_name: str,
        mode: str,
        params: dict,
        iterations: int = 10,
    ) -> list[float]:
        """
        Benchmark a single query with multiple iterations.

        Args:
            adapter: ClientAdapter instance
            tool_name: Tool identifier
            mode: Query mode
            params: Query parameters
            iterations: Number of iterations (default: 10)

        Returns:
            List of latencies in milliseconds
        """
        latencies = []

        for i in range(iterations):
            start = time.perf_counter()
            try:
                # Execute query through adapter
                result = await adapter.query(mode, **params)
                latency = (time.perf_counter() - start) * 1000  # Convert to ms
                latencies.append(latency)
                logger.debug(f"{tool_name}/{mode} iteration {i+1}: {latency:.2f}ms")
            except Exception as e:
                logger.error(f"{tool_name}/{mode} iteration {i+1} failed: {e}")
                # Record failed query as maximum latency
                latencies.append(60000.0)  # 60 second timeout

            # Small delay between iterations to avoid overwhelming the backend
            await asyncio.sleep(0.1)

        return latencies

    # ========================================================================
    # TOOL 1: Gene/Feature Query
    # ========================================================================

    async def test_tool01_gene_to_features(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 1: gene_to_features mode."""
        tool_name = "tool_01_gene_feature"
        mode = "gene_to_features"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][0],  # TP53
                "include_expression": True,
                "include_go_terms": True,
                "include_pathways": True,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms, p99={stats['p99']:.0f}ms"
        )

        # Assertion: p95 should be under target for complex queries
        assert stats["p95"] < 5000, f"P95 latency {stats['p95']:.0f}ms exceeds 5000ms"

    async def test_tool01_tissue_to_genes(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 1: tissue_to_genes mode."""
        tool_name = "tool_01_gene_feature"
        mode = "tissue_to_genes"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "tissue": known_entities["tissues"][0],  # brain
                "limit": 50,
                "offset": 0,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    async def test_tool01_go_to_genes(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 1: go_to_genes mode."""
        tool_name = "tool_01_gene_feature"
        mode = "go_to_genes"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "go_term": known_entities["go_terms"][0],  # GO:0006915 (apoptosis)
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    # ========================================================================
    # TOOL 2: Subnetwork Extraction
    # ========================================================================

    async def test_tool02_shared_regulators(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 2: shared_regulators mode."""
        tool_name = "tool_02_subnetwork"
        mode = "shared_regulators"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "genes": known_entities["genes"][:5],  # First 5 genes
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    async def test_tool02_shared_targets(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 2: shared_targets mode."""
        tool_name = "tool_02_subnetwork"
        mode = "shared_targets"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "genes": known_entities["genes"][:5],
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    # ========================================================================
    # TOOL 3: Enrichment Analysis
    # ========================================================================

    async def test_tool03_go_enrichment(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 3: GO enrichment analysis."""
        tool_name = "tool_03_enrichment"
        mode = "go_enrichment"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "genes": known_entities["genes"][:10],
                "source": "go",
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    async def test_tool03_pathway_enrichment(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 3: Pathway enrichment analysis."""
        tool_name = "tool_03_enrichment"
        mode = "pathway_enrichment"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "genes": known_entities["genes"][:10],
                "source": "reactome",
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    # ========================================================================
    # TOOL 4: Drug/Effect Query
    # ========================================================================

    async def test_tool04_drug_to_targets(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 4: drug_to_targets mode."""
        tool_name = "tool_04_drug_effect"
        mode = "drug_to_targets"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "drug": known_entities["drugs"][0],  # imatinib
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    async def test_tool04_gene_to_drugs(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 4: gene_to_drugs mode."""
        tool_name = "tool_04_drug_effect"
        mode = "gene_to_drugs"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][0],  # TP53
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    # ========================================================================
    # TOOL 5: Disease/Phenotype Query
    # ========================================================================

    async def test_tool05_disease_to_genes(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 5: disease_to_genes mode."""
        tool_name = "tool_05_disease_phenotype"
        mode = "disease_to_genes"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "disease": known_entities["diseases"][2],  # breast cancer
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    async def test_tool05_gene_to_diseases(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 5: gene_to_diseases mode."""
        tool_name = "tool_05_disease_phenotype"
        mode = "gene_to_diseases"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][0],  # TP53
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    # ========================================================================
    # TOOL 6: Pathway Query
    # ========================================================================

    async def test_tool06_gene_to_pathways(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 6: gene_to_pathways mode."""
        tool_name = "tool_06_pathway"
        mode = "gene_to_pathways"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][0],  # TP53
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    async def test_tool06_pathway_to_genes(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 6: pathway_to_genes mode."""
        tool_name = "tool_06_pathway"
        mode = "pathway_to_genes"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "pathway": known_entities["pathways"][0],  # p53 signaling
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    # ========================================================================
    # TOOL 7: Cell Line Query
    # ========================================================================

    async def test_tool07_cell_line_mutations(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 7: get_mutations mode."""
        tool_name = "tool_07_cell_line"
        mode = "get_mutations"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "cell_line": known_entities["cell_lines"][0],  # A549
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    # ========================================================================
    # TOOL 8: Clinical Trials
    # ========================================================================

    async def test_tool08_trials_for_disease(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 8: trials_for_disease mode."""
        tool_name = "tool_08_clinical_trials"
        mode = "trials_for_disease"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "disease": known_entities["diseases"][2],  # breast cancer
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    # ========================================================================
    # TOOL 9: Literature
    # ========================================================================

    async def test_tool09_publications_for_gene(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 9: publications_for_gene mode."""
        tool_name = "tool_09_literature"
        mode = "publications_for_gene"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][0],  # TP53
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 5000

    # ========================================================================
    # TOOL 10: Variants
    # ========================================================================

    async def test_tool10_variants_for_gene(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 10: variants_for_gene mode."""
        tool_name = "tool_10_variants"
        mode = "variants_for_gene"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][1],  # BRCA1
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 2000

    # ========================================================================
    # TOOL 11: Identifier Resolution
    # ========================================================================

    async def test_tool11_resolve_identifiers(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 11: resolve_identifiers mode."""
        tool_name = "tool_11_identifier"
        mode = "resolve"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "identifiers": known_entities["genes"][:5],
                "from_type": "hgnc.symbol",
                "to_type": "hgnc",
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 1000

    # ========================================================================
    # TOOL 12: Relationship Checking
    # ========================================================================

    async def test_tool12_check_relationship(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 12: check_relationship mode."""
        tool_name = "tool_12_relationship"
        mode = "check"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "relationship_type": "gene_to_disease",
                "source": known_entities["genes"][0],  # TP53
                "target": known_entities["diseases"][2],  # breast cancer
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 1000

    # ========================================================================
    # TOOL 13: Ontology Navigation
    # ========================================================================

    async def test_tool13_ontology_hierarchy(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 13: get_hierarchy mode."""
        tool_name = "tool_13_ontology"
        mode = "get_hierarchy"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "term": known_entities["go_terms"][0],  # GO:0006915
                "ontology": "go",
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 1000

    # ========================================================================
    # TOOL 14: Cell Marker
    # ========================================================================

    async def test_tool14_cell_markers(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 14: get_markers mode."""
        tool_name = "tool_14_cell_marker"
        mode = "get_markers"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "cell_type": "T cell",
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 1000

    # ========================================================================
    # TOOL 15: Kinase Activity
    # ========================================================================

    async def test_tool15_kinase_substrates(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 15: get_substrates mode."""
        tool_name = "tool_15_kinase"
        mode = "get_substrates"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "kinase": "MAPK1",
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 1000

    # ========================================================================
    # TOOL 16: Protein Function
    # ========================================================================

    async def test_tool16_protein_activities(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """Benchmark Tool 16: get_activities mode."""
        tool_name = "tool_16_protein_function"
        mode = "get_activities"

        latencies = await self._benchmark_query(
            performance_adapter,
            tool_name,
            mode,
            {
                "gene": known_entities["genes"][0],  # TP53
                "limit": 50,
            },
        )

        stats = PerformanceProfiler.calculate_statistics(latencies)
        performance_profiler.save_latency_report(tool_name, mode, stats)

        logger.info(
            f"{tool_name}/{mode}: mean={stats['mean']:.0f}ms, "
            f"p95={stats['p95']:.0f}ms"
        )

        assert stats["p95"] < 1000
