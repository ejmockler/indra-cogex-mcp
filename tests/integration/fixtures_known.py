"""
Canonical entities and minimal expectations for live integration tests.

Thresholds are intentionally low to avoid flakiness while still proving that
real data is returned.
"""

KNOWN_ENTITIES = {
    "genes": {
        "TP53": {"pathways_min": 3, "go_terms_min": 3, "expression_min": 1},
        "BRCA1": {"variants_min": 1},
        "EGFR": {"activities_min": 1},  # pending Tool 16 data availability
    },
    "drugs": {
        "imatinib": {"targets_min": 1, "indications_min": 1},
        "pembrolizumab": {"trials_min": 1},
    },
    "diseases": {
        "breast cancer": {"mechanisms_min": 1},
        "alzheimer disease": {"phenotypes_min": 1},
    },
    "pathways": {
        "MAPK signaling": {"genes_min": 3},
    },
    "cell_lines": {
        "A549": {"mutations_min": 1},
    },
    "variants": {
        "rs7412": {"diseases_min": 1, "phenotypes_min": 1},
    },
    "trials": {
        "NCT02576431": {"title_required": True, "status_required": True},
    },
    "go_terms": {
        "GO:0006915": {"genes_min": 1},
        "GO:0006468": {"genes_min": 1},
    },
}


def get_known(key: str, default=None):
    """Convenience accessor to avoid KeyError in tests."""
    return KNOWN_ENTITIES.get(key, default)
