"""
MCP Tools for INDRA CoGEx.

16 compositional, bidirectional tools providing 91% coverage of CoGEx capabilities.
"""

# Tools will be imported as they are implemented
# Each tool module self-registers with the MCP server via @mcp.tool() decorator

# Import implemented tools
from cogex_mcp.tools import (
    cell_line,
    cell_marker,
    clinical_trials,
    disease_phenotype,
    drug_effect,
    enrichment,
    gene_feature,
    identifier,
    kinase,
    literature,
    ontology,
    pathway,
    protein_function,
    relationship,
    subnetwork,
    variants,
)

__all__ = [
    "gene_feature",
    "subnetwork",
    "enrichment",
    "drug_effect",
    "disease_phenotype",
    "pathway",
    "cell_line",
    "clinical_trials",
    "literature",
    "variants",
    "identifier",
    "relationship",
    "ontology",
    "cell_marker",
    "kinase",
    "protein_function",
]
