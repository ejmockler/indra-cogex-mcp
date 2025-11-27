"""
Clinical Trial Query Examples

Demonstrates querying clinical trial data from ClinicalTrials.gov using CoGEx.
Shows how to find trials for drugs, diseases, and retrieve trial details.

Examples:
1. Pembrolizumab cancer trials (immunotherapy)
2. Alzheimer's disease trials
3. Trial details by NCT ID
4. Phase 3 recruiting melanoma trials
"""

import asyncio
import logging
from typing import List, Dict, Any

from cogex_mcp.clients.clinical_trial_client import ClinicalTrialClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_trials(trials: List[Dict[str, Any]], title: str) -> None:
    """Print formatted trial results."""
    print(f"\n{'=' * 80}")
    print(f"{title}")
    print(f"{'=' * 80}\n")

    if not trials:
        print("No trials found.\n")
        return

    for i, trial in enumerate(trials, 1):
        print(f"{i}. {trial['nct_id']}: {trial.get('title', 'Unknown')}")
        print(f"   Phase: {trial.get('phase', 'N/A')}")
        print(f"   Status: {trial.get('status', 'Unknown')}")

        if trial.get("conditions"):
            print(f"   Conditions: {', '.join(trial['conditions'])}")

        if trial.get("interventions"):
            print(f"   Interventions: {', '.join(trial['interventions'][:3])}")

        if trial.get("enrollment"):
            print(f"   Enrollment: {trial['enrollment']} patients")

        print()


def print_trial_details(details: Dict[str, Any]) -> None:
    """Print formatted trial details."""
    print(f"\n{'=' * 80}")
    print(f"Trial Details: {details['trial_id']}")
    print(f"{'=' * 80}\n")

    # Print drugs
    print("Drugs being tested:")
    if details.get("drugs"):
        for drug in details["drugs"]:
            print(f"  - {drug['drug_name']} ({drug['drug_id']})")
    else:
        print("  (None listed)")

    print()

    # Print diseases
    print("Diseases/Conditions:")
    if details.get("diseases"):
        for disease in details["diseases"]:
            print(f"  - {disease['disease_name']} ({disease['disease_id']})")
    else:
        print("  (None listed)")

    print()


async def example_1_pembrolizumab_trials():
    """
    Example 1: Find pembrolizumab clinical trials.

    Pembrolizumab (Keytruda) is a PD-1 immune checkpoint inhibitor
    approved for multiple cancer types including melanoma, NSCLC, etc.

    Expected results:
    - Multiple Phase 2/3/4 trials
    - Various cancer indications
    - Mix of completed and recruiting trials
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Pembrolizumab (Keytruda) Clinical Trials")
    print("=" * 80)

    client = ClinicalTrialClient()

    # Get all pembrolizumab trials
    result = client.get_drug_trials(
        drug_id="chebi:164898",  # Pembrolizumab
    )

    print(f"\nTotal trials found: {result['total_trials']}")
    print_trials(result["trials"][:5], "First 5 Pembrolizumab Trials")

    # Get Phase 3 trials only
    phase3_result = client.get_drug_trials(
        drug_id="chebi:164898",
        phase=[3],
    )

    print(f"\nPhase 3 trials: {phase3_result['total_trials']}")
    print_trials(
        phase3_result["trials"][:3],
        "Pembrolizumab Phase 3 Trials (Sample)",
    )

    # Get currently recruiting trials
    recruiting_result = client.get_drug_trials(
        drug_id="chebi:164898",
        status="Recruiting",
    )

    print(f"\nCurrently recruiting: {recruiting_result['total_trials']}")
    print_trials(
        recruiting_result["trials"][:3],
        "Pembrolizumab Recruiting Trials (Sample)",
    )


async def example_2_alzheimers_trials():
    """
    Example 2: Find Alzheimer's disease clinical trials.

    Alzheimer's disease is a major research area with many active trials
    testing various therapeutic approaches.

    Expected results:
    - Many trials (50+)
    - Various phases (1-4)
    - Different therapeutic strategies
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Alzheimer's Disease Clinical Trials")
    print("=" * 80)

    client = ClinicalTrialClient()

    # Get all AD trials
    result = client.get_disease_trials(
        disease_id="mesh:D000544",  # Alzheimer's Disease
    )

    print(f"\nTotal AD trials found: {result['total_trials']}")
    print_trials(result["trials"][:5], "First 5 Alzheimer's Trials")

    # Get Phase 3 trials (late-stage development)
    phase3_result = client.get_disease_trials(
        disease_id="mesh:D000544",
        phase=[3, 4],
    )

    print(f"\nPhase 3/4 trials: {phase3_result['total_trials']}")
    print_trials(
        phase3_result["trials"][:3],
        "Alzheimer's Phase 3/4 Trials (Sample)",
    )

    # Get completed trials
    completed_result = client.get_disease_trials(
        disease_id="mesh:D000544",
        status="Completed",
    )

    print(f"\nCompleted trials: {completed_result['total_trials']}")


async def example_3_trial_details():
    """
    Example 3: Get detailed information about a specific trial.

    Uses NCT ID (ClinicalTrials.gov identifier) to retrieve
    comprehensive trial information including drugs and conditions.

    Example trial: NCT01866319 (KEYNOTE-006)
    Famous pembrolizumab melanoma trial that led to FDA approval.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Trial Details by NCT ID")
    print("=" * 80)

    client = ClinicalTrialClient()

    # Get details for KEYNOTE-006 trial
    result = client.get_trial_details(
        trial_id="NCT01866319",  # KEYNOTE-006
    )

    print(f"\nTrial ID: {result['trial_id']}")
    print(f"Found {result['total_drugs']} drug(s)")
    print(f"Found {result['total_diseases']} disease(s)")

    print_trial_details(result)

    # Try another well-known trial (if available)
    print("\n" + "-" * 80)
    print("Querying another trial...")

    try:
        result2 = client.get_trial_details(
            trial_id="NCT02603432",  # Another pembrolizumab trial
        )
        print(f"\nTrial ID: {result2['trial_id']}")
        print(f"Found {result2['total_drugs']} drug(s)")
        print(f"Found {result2['total_diseases']} disease(s)")
        print_trial_details(result2)
    except Exception as e:
        print(f"Note: Trial NCT02603432 may not be in database: {e}")


async def example_4_filtered_disease_trials():
    """
    Example 4: Find Phase 3 recruiting trials for melanoma.

    Combines disease query with phase and status filters to find
    currently active late-stage melanoma trials.

    Expected results:
    - Active recruiting trials
    - Phase 3 (late-stage)
    - Melanoma indication
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Phase 3 Recruiting Melanoma Trials")
    print("=" * 80)

    client = ClinicalTrialClient()

    # Get Phase 3 recruiting melanoma trials
    result = client.get_disease_trials(
        disease_id="mesh:D008545",  # Melanoma
        phase=[3],
        status="Recruiting",
    )

    print(f"\nTotal Phase 3 recruiting melanoma trials: {result['total_trials']}")
    print_trials(
        result["trials"],
        "Phase 3 Recruiting Melanoma Trials",
    )

    # Also check Phase 2 for comparison
    phase2_result = client.get_disease_trials(
        disease_id="mesh:D008545",
        phase=[2],
        status="Recruiting",
    )

    print(f"\nPhase 2 recruiting trials (for comparison): {phase2_result['total_trials']}")


async def example_5_imatinib_trials():
    """
    Example 5: Find imatinib (Gleevec) clinical trials.

    Imatinib is the first approved targeted therapy for CML (chronic
    myeloid leukemia). Shows trials for an approved drug.

    Expected results:
    - Phase 4 post-marketing trials
    - CML and GIST indications
    - Many completed trials
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Imatinib (Gleevec) Clinical Trials")
    print("=" * 80)

    client = ClinicalTrialClient()

    # Get all imatinib trials
    result = client.get_drug_trials(
        drug_id="chebi:45783",  # Imatinib
    )

    print(f"\nTotal imatinib trials: {result['total_trials']}")
    print_trials(result["trials"][:5], "First 5 Imatinib Trials")

    # Get Phase 4 trials (post-marketing)
    phase4_result = client.get_drug_trials(
        drug_id="chebi:45783",
        phase=[4],
    )

    print(f"\nPhase 4 trials: {phase4_result['total_trials']}")
    print_trials(
        phase4_result["trials"][:3],
        "Imatinib Phase 4 Trials (Sample)",
    )


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("CoGEx Clinical Trial Query Examples")
    print("=" * 80)

    try:
        # Run examples
        await example_1_pembrolizumab_trials()
        await example_2_alzheimers_trials()
        await example_3_trial_details()
        await example_4_filtered_disease_trials()
        await example_5_imatinib_trials()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
