"""
Tool 10: Variant Query Schemas

This file contains schemas for cogex_query_variants tool.
Will be imported into main schemas.py file.
"""

from typing import Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class VariantQueryMode(str, Enum):
    """Query modes for variant queries."""

    GET_FOR_GENE = "get_for_gene"
    GET_FOR_DISEASE = "get_for_disease"
    GET_FOR_PHENOTYPE = "get_for_phenotype"
    VARIANT_TO_GENES = "variant_to_genes"
    VARIANT_TO_PHENOTYPES = "variant_to_phenotypes"
    CHECK_ASSOCIATION = "check_association"


class VariantNode(BaseModel):
    """Genetic variant from GWAS."""

    rsid: str = Field(..., description="dbSNP rsID")
    chromosome: str
    position: int
    ref_allele: str = Field(..., description="Reference allele")
    alt_allele: str = Field(..., description="Alternate allele")
    p_value: float = Field(..., description="GWAS p-value")
    odds_ratio: Optional[float] = None
    trait: str = Field(..., description="Associated trait or phenotype")
    study: str = Field(..., description="GWAS study identifier")
    source: str = Field(..., description="Data source (gwas_catalog, disgenet)")


class PhenotypeNode(BaseModel):
    """Phenotype entity."""

    name: str
    curie: str
    namespace: str = Field(default="hpo", description="Typically HPO")
    identifier: str
    description: Optional[str] = None
