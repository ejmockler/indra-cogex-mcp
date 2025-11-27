"""
Lightweight live sanity checks per client to ensure at least one real backend
call succeeds without relying on mocks.
"""

import pytest

from tests.integration.utils import assert_json, assert_non_empty


@pytest.mark.integration
@pytest.mark.asyncio
class TestClientSanity:
    async def test_gene_client_tp53(self, integration_adapter):
        data = assert_json(
            await integration_adapter.query(
                "gene_to_features",
                mode="gene_to_features",
                gene="TP53",
                include_go_terms=True,
                response_format="json",
                limit=3,
            )
        )
        assert_non_empty(data, "gene")

    async def test_drug_client_imatinib(self, integration_adapter):
        data = assert_json(
            await integration_adapter.query(
                "drug_to_profile",
                mode="drug_to_profile",
                drug="imatinib",
                include_targets=True,
                response_format="json",
                limit=3,
            )
        )
        assert_non_empty(data, "targets")

    async def test_pathway_client_mapk(self, integration_adapter):
        data = assert_json(
            await integration_adapter.query(
                "query_pathway",
                mode="get_genes",
                pathway="MAPK signaling",
                response_format="json",
                limit=3,
            )
        )
        assert_non_empty(data, "genes")

    async def test_variant_client_brca1(self, integration_adapter):
        data = assert_json(
            await integration_adapter.query(
                "query_variants",
                mode="get_variants_for_gene",
                gene="BRCA1",
                response_format="json",
                limit=3,
            )
        )
        assert_non_empty(data, "variants")

    async def test_literature_client_pmid(self, integration_adapter):
        data = assert_json(
            await integration_adapter.query(
                "query_literature",
                mode="get_statements_for_pmid",
                pmid="29760375",
                response_format="json",
                limit=3,
            )
        )
        assert_non_empty(data, "statements")
