"""
MCP Tools for INDRA CoGEx.

16 compositional, bidirectional tools providing 91% coverage of CoGEx capabilities.
"""

# Tools will be imported as they are implemented
# Each tool module self-registers with the MCP server via @mcp.tool() decorator

# Import implemented tools
from cogex_mcp.tools import (
    gene_feature,
    subnetwork,
    enrichment,
    drug_effect,
    disease_phenotype,
    pathway,
    cell_line,
    clinical_trials,
    literature,
    variants,
    identifier,
    relationship,
    ontology,
    cell_marker,
    kinase,
    protein_function,
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
