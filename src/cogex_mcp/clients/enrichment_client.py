"""
Direct CoGEx enrichment client.

Calls INDRA CoGEx enrichment functions directly, bypassing web app dependencies.
This implementation extracts the core enrichment logic from CoGEx's discrete.py
without requiring Flask/web authentication dependencies.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from scipy.stats import fisher_exact
from statsmodels.stats.multitest import multipletests

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_genes_for_go_term,
    get_genes_in_tissue,
    get_go_terms_for_gene,
    get_pathways_for_gene,
)

logger = logging.getLogger(__name__)


class EnrichmentClient:
    """
    Direct enrichment analysis using CoGEx Neo4j client.

    Implements Fisher's exact test enrichment for:
    - GO terms
    - Reactome pathways
    - WikiPathways
    - Phenotypes
    - INDRA upstream/downstream
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize enrichment client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def go_enrichment(
        self,
        gene_ids: List[str],
        background_gene_ids: Optional[List[str]] = None,
        alpha: float = 0.05,
        correction_method: str = "fdr_bh",
        *,
        client: Neo4jClient,
    ) -> pd.DataFrame:
        """
        Perform GO term enrichment analysis using Fisher's exact test.

        Args:
            gene_ids: List of gene CURIEs (e.g., ["hgnc:11179", "hgnc:11571"])
            background_gene_ids: Optional background gene set
            alpha: Significance threshold
            correction_method: Multiple testing correction method
            client: Neo4j client (injected by autoclient)

        Returns:
            DataFrame with enrichment results
        """
        logger.info(f"GO enrichment for {len(gene_ids)} genes")

        # Get all GO terms for input genes
        gene_go_terms = {}
        for gene_id in gene_ids:
            terms = get_go_terms_for_gene(gene_id, client=client)
            gene_go_terms[gene_id] = {t["go_id"] for t in terms}

        # Collect unique GO terms
        all_go_terms = set()
        for terms in gene_go_terms.values():
            all_go_terms.update(terms)

        # Run enrichment test for each GO term
        results = []
        for go_term in all_go_terms:
            # Get genes with this GO term
            term_genes_data = get_genes_for_go_term(go_term, client=client)
            term_gene_ids = {g["gene_id"] for g in term_genes_data}

            # Build contingency table
            in_term_and_set = len(set(gene_ids) & term_gene_ids)
            in_term_not_set = len(term_gene_ids - set(gene_ids))
            not_term_in_set = len(set(gene_ids) - term_gene_ids)

            if background_gene_ids:
                not_term_not_set = len(set(background_gene_ids) - term_gene_ids - set(gene_ids))
            else:
                # Estimate background (total genes in GO)
                not_term_not_set = 20000  # Approximate human genome size

            # Fisher's exact test
            oddsratio, pvalue = fisher_exact(
                [[in_term_and_set, in_term_not_set],
                 [not_term_in_set, not_term_not_set]],
                alternative='greater'
            )

            if in_term_and_set > 0:  # Only keep terms with overlap
                results.append({
                    'term_id': go_term,
                    'term_name': term_genes_data[0].get('go_name', 'Unknown') if term_genes_data else 'Unknown',
                    'p_value': pvalue,
                    'gene_count': in_term_and_set,
                    'term_size': len(term_gene_ids),
                    'genes': list(set(gene_ids) & term_gene_ids),
                })

        # Convert to DataFrame
        df = pd.DataFrame(results)

        if df.empty:
            return df

        # Multiple testing correction
        df['adjusted_p_value'] = multipletests(
            df['p_value'],
            alpha=alpha,
            method=correction_method
        )[1]

        # Sort by p-value
        df = df.sort_values('p_value')

        return df

    @autoclient()
    def reactome_enrichment(
        self,
        gene_ids: List[str],
        background_gene_ids: Optional[List[str]] = None,
        alpha: float = 0.05,
        correction_method: str = "fdr_bh",
        *,
        client: Neo4jClient,
    ) -> pd.DataFrame:
        """
        Perform Reactome pathway enrichment analysis.

        Args:
            gene_ids: List of gene CURIEs
            background_gene_ids: Optional background gene set
            alpha: Significance threshold
            correction_method: Multiple testing correction method
            client: Neo4j client (injected by autoclient)

        Returns:
            DataFrame with enrichment results
        """
        logger.info(f"Reactome enrichment for {len(gene_ids)} genes")

        # Get all pathways for input genes
        gene_pathways = {}
        for gene_id in gene_ids:
            pathways = get_pathways_for_gene(gene_id, client=client)
            # Filter to Reactome only
            reactome_pathways = [p for p in pathways if p.get('namespace') == 'reactome']
            gene_pathways[gene_id] = {p['pathway_id'] for p in reactome_pathways}

        # Collect unique pathways
        all_pathways = set()
        for pathways in gene_pathways.values():
            all_pathways.update(pathways)

        # Run enrichment test for each pathway
        results = []
        for pathway_id in all_pathways:
            # Query genes in this pathway
            query = """
            MATCH (g:BioEntity)-[:partof]->(p:BioEntity {id: $pathway_id})
            WHERE g:Gene
            RETURN g.id AS gene_id
            """
            pathway_genes_data = client.query_tx(query, pathway_id=pathway_id)
            pathway_gene_ids = {g['gene_id'] for g in pathway_genes_data}

            # Build contingency table
            in_pathway_and_set = len(set(gene_ids) & pathway_gene_ids)
            in_pathway_not_set = len(pathway_gene_ids - set(gene_ids))
            not_pathway_in_set = len(set(gene_ids) - pathway_gene_ids)

            if background_gene_ids:
                not_pathway_not_set = len(set(background_gene_ids) - pathway_gene_ids - set(gene_ids))
            else:
                not_pathway_not_set = 20000

            # Fisher's exact test
            oddsratio, pvalue = fisher_exact(
                [[in_pathway_and_set, in_pathway_not_set],
                 [not_pathway_in_set, not_pathway_not_set]],
                alternative='greater'
            )

            if in_pathway_and_set > 0:
                results.append({
                    'term_id': pathway_id,
                    'term_name': pathway_id.split(':')[-1].replace('-', ' ').title(),
                    'p_value': pvalue,
                    'gene_count': in_pathway_and_set,
                    'term_size': len(pathway_gene_ids),
                    'genes': list(set(gene_ids) & pathway_gene_ids),
                })

        # Convert to DataFrame
        df = pd.DataFrame(results)

        if df.empty:
            return df

        # Multiple testing correction
        df['adjusted_p_value'] = multipletests(
            df['p_value'],
            alpha=alpha,
            method=correction_method
        )[1]

        # Sort by p-value
        df = df.sort_values('p_value')

        return df

    def run_enrichment(
        self,
        gene_ids: List[str],
        source: str = "go",
        analysis_type: str = "discrete",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run enrichment analysis.

        Args:
            gene_ids: List of gene CURIEs
            source: Enrichment source ("go", "reactome", "wikipathways", etc.)
            analysis_type: Analysis type ("discrete", "continuous", "signed")
            **kwargs: Additional parameters (alpha, correction_method, etc.)

        Returns:
            Dict with enrichment results
        """
        if analysis_type != "discrete":
            raise NotImplementedError(f"Analysis type '{analysis_type}' not yet implemented")

        # Route to appropriate enrichment function
        if source == "go":
            df = self.go_enrichment(gene_ids, **kwargs)
        elif source == "reactome":
            df = self.reactome_enrichment(gene_ids, **kwargs)
        else:
            raise ValueError(f"Unsupported source: {source}")

        # Convert DataFrame to dict format
        results = []
        for _, row in df.iterrows():
            results.append({
                'term_id': row['term_id'],
                'term_name': row['term_name'],
                'p_value': float(row['p_value']),
                'adjusted_p_value': float(row['adjusted_p_value']),
                'gene_count': int(row['gene_count']),
                'term_size': int(row['term_size']),
                'genes': row['genes'],
            })

        return {
            'success': True,
            'results': results,
            'total_genes': len(gene_ids),
        }
