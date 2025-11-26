"""
INDRA CoGEx MCP Tool Handlers

Each module contains the implementation for one MCP tool.
All handlers expose a `handle(args)` function.
"""

# Import all handler modules to make them available
from cogex_mcp.server.handlers import (
    disease_phenotype,
    gene_feature,
    subnetwork,
    enrichment,
    drug_effect,
    pathway,
    cell_line,
    clinical_trials,
    literature,
    variants,
    identifier,
    relationship,
    ontology,
    cell_markers,
    kinase,
    protein_function,
)

__all__ = [
    "disease_phenotype",
    "gene_feature",
    "subnetwork",
    "enrichment",
    "drug_effect",
    "pathway",
    "cell_line",
    "clinical_trials",
    "literature",
    "variants",
    "identifier",
    "relationship",
    "ontology",
    "cell_markers",
    "kinase",
    "protein_function",
]
