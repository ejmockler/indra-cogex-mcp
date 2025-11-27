"""Tests for CURIE normalization utilities."""

import pytest

from cogex_mcp.services.curie_normalizer import (
    normalize_curie,
    normalize_gilda_results,
)


class TestNormalizeCurie:
    """Tests for normalize_curie function."""

    def test_normalize_curie_chebi(self):
        """Test CHEBI namespace normalization with redundant prefix."""
        assert normalize_curie("CHEBI", "CHEBI:8863") == "chebi:8863"

    def test_normalize_curie_doid(self):
        """Test DOID namespace normalization with redundant prefix."""
        assert normalize_curie("DOID", "DOID:332") == "doid:332"

    def test_normalize_curie_mesh(self):
        """Test MESH namespace normalization without redundant prefix."""
        assert normalize_curie("MESH", "D000690") == "mesh:D000690"

    def test_normalize_curie_hgnc(self):
        """Test HGNC namespace normalization with redundant prefix."""
        assert normalize_curie("HGNC", "HGNC:5468") == "hgnc:5468"

    def test_normalize_curie_go(self):
        """Test GO namespace normalization with redundant prefix."""
        assert normalize_curie("GO", "GO:0005783") == "go:0005783"

    def test_normalize_curie_mondo(self):
        """Test MONDO namespace normalization with redundant prefix."""
        assert normalize_curie("MONDO", "MONDO:0005015") == "mondo:0005015"

    def test_normalize_curie_hp(self):
        """Test HP namespace normalization with redundant prefix."""
        assert normalize_curie("HP", "HP:0001250") == "hp:0001250"

    def test_normalize_curie_uniprot(self):
        """Test UniProt namespace normalization without redundant prefix."""
        assert normalize_curie("UNIPROT", "P04637") == "uniprot:P04637"

    def test_normalize_curie_already_lowercase(self):
        """Test normalization when namespace is already lowercase."""
        assert normalize_curie("chebi", "CHEBI:8863") == "chebi:8863"
        assert normalize_curie("chebi", "chebi:8863") == "chebi:8863"

    def test_normalize_curie_already_normalized(self):
        """Test normalization when CURIE is already in correct format."""
        assert normalize_curie("chebi", "8863") == "chebi:8863"
        assert normalize_curie("mesh", "D000690") == "mesh:D000690"

    def test_normalize_curie_case_insensitive_prefix(self):
        """Test that prefix removal is case-insensitive."""
        assert normalize_curie("CHEBI", "chebi:8863") == "chebi:8863"
        assert normalize_curie("chebi", "CHEBI:8863") == "chebi:8863"
        assert normalize_curie("ChEbI", "ChEbI:8863") == "chebi:8863"

    def test_normalize_curie_preserves_id_case(self):
        """Test that identifier case is preserved (only namespace lowercased)."""
        assert normalize_curie("MESH", "D000690") == "mesh:D000690"
        assert normalize_curie("UNIPROT", "P04637") == "uniprot:P04637"

    def test_normalize_curie_multiple_colons(self):
        """Test handling of identifiers with multiple colons."""
        # Only the first colon should be used to split
        assert normalize_curie("CUSTOM", "CUSTOM:part1:part2") == "custom:part1:part2"
        assert normalize_curie("CUSTOM", "part1:part2") == "custom:part1:part2"

    def test_normalize_curie_empty_strings(self):
        """Test handling of empty strings."""
        assert normalize_curie("", "") == ":"
        assert normalize_curie("CHEBI", "") == "chebi:"
        assert normalize_curie("", "8863") == ":8863"

    def test_normalize_curie_special_characters(self):
        """Test handling of special characters in identifiers."""
        assert normalize_curie("MESH", "D000690-X") == "mesh:D000690-X"
        assert normalize_curie("CUSTOM", "ID_123") == "custom:ID_123"


class TestNormalizeGildaResults:
    """Tests for normalize_gilda_results function."""

    def test_normalize_gilda_results_basic(self):
        """Test basic normalization of GILDA results."""
        results = [
            {
                "term": {
                    "db": "CHEBI",
                    "id": "CHEBI:8863",
                    "text": "Propranolol"
                },
                "score": 0.95
            },
            {
                "term": {
                    "db": "DOID",
                    "id": "DOID:332",
                    "text": "ALS"
                },
                "score": 0.88
            }
        ]

        normalized = normalize_gilda_results(results)

        assert results[0]["term"]["db"] == "chebi"
        assert results[0]["term"]["id"] == "8863"
        assert results[1]["term"]["db"] == "doid"
        assert results[1]["term"]["id"] == "332"

    def test_normalize_gilda_results_in_place(self):
        """Test that normalization modifies the input list in-place."""
        results = [
            {
                "term": {
                    "db": "CHEBI",
                    "id": "CHEBI:8863",
                    "text": "Propranolol"
                },
                "score": 0.95
            }
        ]

        normalized = normalize_gilda_results(results)

        # Should return the same list object
        assert normalized is results
        # And it should be modified
        assert results[0]["term"]["db"] == "chebi"
        assert results[0]["term"]["id"] == "8863"

    def test_normalize_gilda_results_mixed_formats(self):
        """Test normalization of results with mixed formats."""
        results = [
            {
                "term": {
                    "db": "CHEBI",
                    "id": "CHEBI:8863",
                    "text": "With prefix"
                },
                "score": 0.95
            },
            {
                "term": {
                    "db": "MESH",
                    "id": "D000690",
                    "text": "Without prefix"
                },
                "score": 0.90
            },
            {
                "term": {
                    "db": "hgnc",
                    "id": "5468",
                    "text": "Already normalized"
                },
                "score": 0.85
            }
        ]

        normalize_gilda_results(results)

        assert results[0]["term"]["db"] == "chebi"
        assert results[0]["term"]["id"] == "8863"
        assert results[1]["term"]["db"] == "mesh"
        assert results[1]["term"]["id"] == "D000690"
        assert results[2]["term"]["db"] == "hgnc"
        assert results[2]["term"]["id"] == "5468"

    def test_normalize_gilda_results_empty_list(self):
        """Test normalization of empty results list."""
        results = []
        normalized = normalize_gilda_results(results)
        assert normalized == []
        assert normalized is results

    def test_normalize_gilda_results_missing_term(self):
        """Test handling of results with missing 'term' key."""
        results = [
            {"score": 0.95},  # No 'term' key
            {
                "term": {
                    "db": "CHEBI",
                    "id": "CHEBI:8863",
                    "text": "Valid"
                },
                "score": 0.90
            }
        ]

        # Should not crash, should skip entries without 'term'
        normalize_gilda_results(results)

        # Valid entry should still be normalized
        assert results[1]["term"]["db"] == "chebi"
        assert results[1]["term"]["id"] == "8863"

    def test_normalize_gilda_results_missing_db_or_id(self):
        """Test handling of results with missing 'db' or 'id' keys."""
        results = [
            {
                "term": {
                    "db": "CHEBI",
                    # Missing 'id'
                    "text": "No ID"
                },
                "score": 0.95
            },
            {
                "term": {
                    # Missing 'db'
                    "id": "8863",
                    "text": "No DB"
                },
                "score": 0.90
            },
            {
                "term": {
                    "db": "MESH",
                    "id": "D000690",
                    "text": "Valid"
                },
                "score": 0.85
            }
        ]

        # Should not crash
        normalize_gilda_results(results)

        # Valid entry should be normalized
        assert results[2]["term"]["db"] == "mesh"
        assert results[2]["term"]["id"] == "D000690"

    def test_normalize_gilda_results_empty_db_or_id(self):
        """Test handling of results with empty 'db' or 'id' values."""
        results = [
            {
                "term": {
                    "db": "",
                    "id": "8863",
                    "text": "Empty DB"
                },
                "score": 0.95
            },
            {
                "term": {
                    "db": "CHEBI",
                    "id": "",
                    "text": "Empty ID"
                },
                "score": 0.90
            },
            {
                "term": {
                    "db": "MESH",
                    "id": "D000690",
                    "text": "Valid"
                },
                "score": 0.85
            }
        ]

        # Should not crash
        normalize_gilda_results(results)

        # Valid entry should be normalized
        assert results[2]["term"]["db"] == "mesh"
        assert results[2]["term"]["id"] == "D000690"

    def test_normalize_gilda_results_preserves_other_fields(self):
        """Test that normalization preserves all other fields."""
        results = [
            {
                "term": {
                    "db": "CHEBI",
                    "id": "CHEBI:8863",
                    "text": "Propranolol",
                    "entry_name": "Beta blocker",
                    "definition": "A medication...",
                    "custom_field": "custom_value"
                },
                "score": 0.95,
                "match": {
                    "exact": False,
                    "type": "synonym"
                }
            }
        ]

        normalize_gilda_results(results)

        # Check normalized fields
        assert results[0]["term"]["db"] == "chebi"
        assert results[0]["term"]["id"] == "8863"

        # Check preserved fields
        assert results[0]["term"]["text"] == "Propranolol"
        assert results[0]["term"]["entry_name"] == "Beta blocker"
        assert results[0]["term"]["definition"] == "A medication..."
        assert results[0]["term"]["custom_field"] == "custom_value"
        assert results[0]["score"] == 0.95
        assert results[0]["match"]["exact"] is False

    def test_normalize_gilda_results_case_insensitive_prefix(self):
        """Test that prefix removal is case-insensitive."""
        results = [
            {
                "term": {
                    "db": "CHEBI",
                    "id": "chebi:8863",
                    "text": "Lowercase prefix"
                },
                "score": 0.95
            },
            {
                "term": {
                    "db": "chebi",
                    "id": "CHEBI:8863",
                    "text": "Uppercase prefix"
                },
                "score": 0.90
            },
            {
                "term": {
                    "db": "ChEbI",
                    "id": "ChEbI:8863",
                    "text": "Mixed case prefix"
                },
                "score": 0.85
            }
        ]

        normalize_gilda_results(results)

        # All should be normalized to same format
        assert results[0]["term"]["db"] == "chebi"
        assert results[0]["term"]["id"] == "8863"
        assert results[1]["term"]["db"] == "chebi"
        assert results[1]["term"]["id"] == "8863"
        assert results[2]["term"]["db"] == "chebi"
        assert results[2]["term"]["id"] == "8863"

    def test_normalize_gilda_results_real_world_example(self):
        """Test with realistic GILDA API response."""
        results = [
            {
                "term": {
                    "db": "MESH",
                    "id": "D000690",
                    "text": "Amyotrophic Lateral Sclerosis",
                    "entry_name": "Amyotrophic Lateral Sclerosis",
                },
                "score": 0.85,
                "match": {
                    "exact": False,
                    "text": "ALS"
                }
            },
            {
                "term": {
                    "db": "DOID",
                    "id": "DOID:332",
                    "text": "amyotrophic lateral sclerosis",
                    "entry_name": "disease",
                },
                "score": 0.778,
                "match": {
                    "exact": False,
                    "text": "ALS"
                }
            }
        ]

        normalize_gilda_results(results)

        assert results[0]["term"]["db"] == "mesh"
        assert results[0]["term"]["id"] == "D000690"
        assert results[0]["score"] == 0.85

        assert results[1]["term"]["db"] == "doid"
        assert results[1]["term"]["id"] == "332"
        assert results[1]["score"] == 0.778
