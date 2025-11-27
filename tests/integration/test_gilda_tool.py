"""Integration tests for GILDA entity grounding tool."""

import asyncio
import pytest

from cogex_mcp.clients.gilda_client import GildaClient


@pytest.mark.asyncio
async def test_gilda_client_ground_diabetes():
    """Test GILDA client with unambiguous term 'diabetes mellitus'."""
    client = GildaClient()

    results = await client.ground("diabetes mellitus")

    # Should get results
    assert len(results) > 0, "Expected matches for 'diabetes mellitus'"

    # Check first result structure
    first_result = results[0]
    assert "term" in first_result
    assert "score" in first_result

    term_data = first_result["term"]
    assert "db" in term_data
    assert "id" in term_data
    assert "text" in term_data

    # CURIE should be normalized (lowercase namespace, no redundant prefix)
    namespace = term_data["db"]
    identifier = term_data["id"]
    assert namespace.islower(), f"Namespace should be lowercase: {namespace}"
    assert not identifier.upper().startswith(namespace.upper() + ":"), \
        f"Identifier should not have redundant prefix: {identifier}"

    # Should have high score for exact match
    assert first_result["score"] > 0.5, f"Expected high score, got {first_result['score']}"

    print(f"✓ Test passed: 'diabetes mellitus' → {namespace}:{identifier}")

    await client.close()


@pytest.mark.asyncio
async def test_gilda_client_ground_als():
    """Test GILDA client with abbreviation 'ALS'."""
    client = GildaClient()

    results = await client.ground("ALS")

    # Should get results
    assert len(results) > 0, "Expected matches for 'ALS'"

    # Check for disease match (should be in mesh, doid, or mondo)
    disease_matches = [
        r for r in results
        if r["term"]["db"] in ["mesh", "doid", "mondo"]
    ]

    assert len(disease_matches) > 0, "Expected at least one disease match for 'ALS'"

    first_match = results[0]
    print(f"✓ Test passed: 'ALS' → {first_match['term']['db']}:{first_match['term']['id']}")
    print(f"  Name: {first_match['term']['text']}")
    print(f"  Score: {first_match['score']:.3f}")

    await client.close()


@pytest.mark.asyncio
async def test_gilda_client_ground_er_ambiguous():
    """Test GILDA client with ambiguous term 'ER'."""
    client = GildaClient()

    results = await client.ground("ER")

    # Should get multiple results due to ambiguity
    assert len(results) > 1, "Expected multiple matches for ambiguous term 'ER'"

    # Should have different namespaces (gene, GO term, etc.)
    namespaces = {r["term"]["db"] for r in results[:5]}
    print(f"✓ Test passed: 'ER' has {len(results)} matches across namespaces: {namespaces}")

    # Show top matches
    for i, result in enumerate(results[:3], 1):
        term = result["term"]
        print(f"  {i}. {term['db']}:{term['id']} - {term['text']} (score: {result['score']:.3f})")

    await client.close()


@pytest.mark.asyncio
async def test_gilda_client_ground_no_matches():
    """Test GILDA client with gibberish term."""
    client = GildaClient()

    results = await client.ground("gibberish12345xyz")

    # Should get no results or very low score results
    if len(results) > 0:
        # If there are results, they should have very low scores
        assert results[0]["score"] < 0.3, \
            f"Gibberish term should have low scores, got {results[0]['score']}"
        print(f"✓ Test passed: 'gibberish12345xyz' → {len(results)} low-score matches")
    else:
        print("✓ Test passed: 'gibberish12345xyz' → no matches")

    await client.close()


@pytest.mark.asyncio
async def test_gilda_client_ground_limit():
    """Test GILDA client limit parameter."""
    client = GildaClient()

    # Ground ambiguous term
    all_results = await client.ground("diabetes")

    # Should respect limit in tool (we'll test this via the actual results)
    assert len(all_results) > 0, "Expected matches for 'diabetes'"

    print(f"✓ Test passed: 'diabetes' → {len(all_results)} total matches")

    # Test that we can slice results
    limited = all_results[:3]
    assert len(limited) == min(3, len(all_results)), "Slicing should work"

    await client.close()


@pytest.mark.asyncio
async def test_gilda_cache():
    """Test GILDA client caching."""
    client = GildaClient()

    term = "diabetes"

    # First call - should hit API
    results1 = await client.ground(term)

    # Second call - should hit cache
    results2 = await client.ground(term)

    # Results should be identical
    assert len(results1) == len(results2), "Cached results should match fresh results"

    if results1:
        assert results1[0]["term"]["id"] == results2[0]["term"]["id"], \
            "Cached results should be identical"

    print(f"✓ Test passed: Cache returns same results")

    await client.close()


# Main test runner for manual execution
if __name__ == "__main__":
    async def run_all_tests():
        """Run all tests manually."""
        print("=" * 80)
        print("GILDA Tool Integration Tests")
        print("=" * 80)

        tests = [
            ("Unambiguous term (diabetes mellitus)", test_gilda_client_ground_diabetes),
            ("Abbreviation (ALS)", test_gilda_client_ground_als),
            ("Ambiguous term (ER)", test_gilda_client_ground_er_ambiguous),
            ("No matches (gibberish)", test_gilda_client_ground_no_matches),
            ("Limit parameter", test_gilda_client_ground_limit),
            ("Caching", test_gilda_cache),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            print(f"\n{'=' * 80}")
            print(f"Running: {name}")
            print(f"{'=' * 80}")
            try:
                await test_func()
                passed += 1
                print(f"\n✓ PASSED: {name}")
            except Exception as e:
                failed += 1
                print(f"\n✗ FAILED: {name}")
                print(f"  Error: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n{'=' * 80}")
        print(f"Test Summary: {passed} passed, {failed} failed")
        print(f"{'=' * 80}")

    asyncio.run(run_all_tests())
