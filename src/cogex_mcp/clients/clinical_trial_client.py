"""
Direct CoGEx clinical trial client.

Wraps INDRA CoGEx clinical trial query functions to access trial data from
ClinicalTrials.gov including drug trials, disease trials, and trial details.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_trials_for_drug,
    get_trials_for_disease,
    get_drugs_for_trial,
    get_diseases_for_trial,
)

logger = logging.getLogger(__name__)


class ClinicalTrialClient:
    """
    Direct clinical trial queries using CoGEx library functions.

    Provides high-level interface to ClinicalTrials.gov data with:
    - Drug → clinical trials mapping
    - Disease → clinical trials mapping
    - Trial details by NCT ID
    - Phase and status filtering

    Example usage:
        >>> client = ClinicalTrialClient()
        >>> result = client.get_drug_trials(
        ...     drug_id="chebi:164898",  # Pembrolizumab
        ...     phase=[3, 4],
        ...     status="Recruiting",
        ... )
        >>> print(f"Found {result['total_trials']} trials")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize clinical trial client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_drug_trials(
        self,
        drug_id: str,
        phase: Optional[List[int]] = None,
        status: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get clinical trials testing a drug.

        This method queries CoGEx for all clinical trials that test the specified
        drug, with optional filtering by trial phase and recruitment status.

        Args:
            drug_id: Drug CURIE (e.g., "chebi:164898" for pembrolizumab)
            phase: Filter by clinical phases (e.g., [1, 2, 3, 4])
            status: Filter by trial status (e.g., "Recruiting", "Completed")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with clinical trials and metadata:
                {
                    "success": True,
                    "drug_id": "chebi:164898",
                    "trials": [...],
                    "total_trials": 156,
                }

        Example:
            >>> result = client.get_drug_trials(
            ...     drug_id="chebi:164898",  # Pembrolizumab
            ...     phase=[3, 4],
            ...     status="Recruiting",
            ... )
            >>> for trial in result["trials"]:
            ...     print(f"{trial['nct_id']}: {trial['title']}")
        """
        logger.info(f"Getting clinical trials for drug: {drug_id}")

        # Parse drug CURIE
        drug_tuple = self._parse_trial_id(drug_id)

        # Query CoGEx
        trials = get_trials_for_drug(drug_tuple, client=client)
        logger.debug(f"Retrieved {len(trials)} trials for drug {drug_id}")

        # Filter by phase if specified
        if phase:
            trials = self._filter_by_phase(trials, phase)
            logger.debug(f"After phase filter: {len(trials)} trials")

        # Filter by status if specified
        if status:
            trials = self._filter_by_status(trials, status)
            logger.debug(f"After status filter: {len(trials)} trials")

        # Format response
        formatted_trials = [self._format_trial_dict(trial) for trial in trials]

        return {
            "success": True,
            "drug_id": drug_id,
            "trials": formatted_trials,
            "total_trials": len(formatted_trials),
        }

    @autoclient()
    def get_disease_trials(
        self,
        disease_id: str,
        phase: Optional[List[int]] = None,
        status: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get clinical trials for a disease.

        This method queries CoGEx for all clinical trials that study the specified
        disease, with optional filtering by trial phase and recruitment status.

        Args:
            disease_id: Disease CURIE (e.g., "mesh:D008545" for melanoma)
            phase: Filter by clinical phases (e.g., [1, 2, 3, 4])
            status: Filter by trial status (e.g., "Recruiting", "Completed")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with clinical trials and metadata:
                {
                    "success": True,
                    "disease_id": "mesh:D008545",
                    "trials": [...],
                    "total_trials": 89,
                }

        Example:
            >>> result = client.get_disease_trials(
            ...     disease_id="mesh:D008545",  # Melanoma
            ...     phase=[3],
            ...     status="Recruiting",
            ... )
            >>> print(f"Found {result['total_trials']} melanoma trials")
        """
        logger.info(f"Getting clinical trials for disease: {disease_id}")

        # Parse disease CURIE
        disease_tuple = self._parse_trial_id(disease_id)

        # Query CoGEx
        trials = get_trials_for_disease(disease_tuple, client=client)
        logger.debug(f"Retrieved {len(trials)} trials for disease {disease_id}")

        # Filter by phase if specified
        if phase:
            trials = self._filter_by_phase(trials, phase)
            logger.debug(f"After phase filter: {len(trials)} trials")

        # Filter by status if specified
        if status:
            trials = self._filter_by_status(trials, status)
            logger.debug(f"After status filter: {len(trials)} trials")

        # Format response
        formatted_trials = [self._format_trial_dict(trial) for trial in trials]

        return {
            "success": True,
            "disease_id": disease_id,
            "trials": formatted_trials,
            "total_trials": len(formatted_trials),
        }

    @autoclient()
    def get_trial_details(
        self,
        trial_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a trial by NCT ID.

        This method queries CoGEx for comprehensive trial information including
        drugs being tested, diseases/conditions being studied, and trial metadata.

        Args:
            trial_id: NCT ID (e.g., "NCT02603432", "nct02603432")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with trial details:
                {
                    "success": True,
                    "trial_id": "NCT02603432",
                    "drugs": [...],
                    "diseases": [...],
                    "total_drugs": 1,
                    "total_diseases": 2,
                }

        Example:
            >>> result = client.get_trial_details(
            ...     trial_id="NCT02603432",
            ... )
            >>> print(f"Trial tests {result['total_drugs']} drugs")
        """
        logger.info(f"Getting trial details for: {trial_id}")

        # Parse and normalize NCT ID
        nct_id = self._parse_nct_id(trial_id)

        # Query drugs for trial
        drugs = get_drugs_for_trial(nct_id, client=client)
        logger.debug(f"Retrieved {len(drugs)} drugs for trial {nct_id}")

        # Query diseases for trial
        diseases = get_diseases_for_trial(nct_id, client=client)
        logger.debug(f"Retrieved {len(diseases)} diseases for trial {nct_id}")

        # Format drugs
        formatted_drugs = []
        for drug in drugs:
            if isinstance(drug, dict):
                drug_dict = drug
            else:
                drug_dict = {
                    "namespace": getattr(drug, "namespace", "unknown"),
                    "identifier": getattr(drug, "identifier", "unknown"),
                    "name": getattr(drug, "name", "Unknown"),
                }

            formatted_drugs.append({
                "drug_id": f"{drug_dict.get('namespace', 'unknown').lower()}:{drug_dict.get('identifier', 'unknown')}",
                "drug_name": drug_dict.get("name", "Unknown"),
            })

        # Format diseases
        formatted_diseases = []
        for disease in diseases:
            if isinstance(disease, dict):
                disease_dict = disease
            else:
                disease_dict = {
                    "namespace": getattr(disease, "namespace", "unknown"),
                    "identifier": getattr(disease, "identifier", "unknown"),
                    "name": getattr(disease, "name", "Unknown"),
                }

            formatted_diseases.append({
                "disease_id": f"{disease_dict.get('namespace', 'unknown').lower()}:{disease_dict.get('identifier', 'unknown')}",
                "disease_name": disease_dict.get("name", "Unknown"),
            })

        return {
            "success": True,
            "trial_id": nct_id,
            "drugs": formatted_drugs,
            "diseases": formatted_diseases,
            "total_drugs": len(formatted_drugs),
            "total_diseases": len(formatted_diseases),
        }

    # Helper methods

    def _parse_trial_id(self, curie: str) -> Tuple[str, str]:
        """
        Parse CURIE into (namespace, identifier) tuple.

        Args:
            curie: CURIE string (e.g., "chebi:164898", "mesh:D008545")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_trial_id("chebi:164898")
            ("CHEBI", "164898")
            >>> client._parse_trial_id("mesh:D008545")
            ("MESH", "D008545")
        """
        if ":" in curie:
            namespace, identifier = curie.split(":", 1)
            return (namespace.upper(), identifier)
        else:
            # Assume generic namespace
            logger.debug(f"No namespace in '{curie}', treating as identifier")
            return ("UNKNOWN", curie)

    def _parse_nct_id(self, trial_id: str) -> str:
        """
        Parse and normalize NCT ID.

        Args:
            trial_id: NCT ID (e.g., "NCT02603432", "nct02603432")

        Returns:
            Normalized NCT ID (uppercase, with NCT prefix)

        Example:
            >>> client._parse_nct_id("NCT02603432")
            "NCT02603432"
            >>> client._parse_nct_id("nct02603432")
            "NCT02603432"
            >>> client._parse_nct_id("02603432")
            "NCT02603432"
        """
        # Remove whitespace
        trial_id = trial_id.strip()

        # If it already starts with NCT, just uppercase
        if trial_id.upper().startswith("NCT"):
            return trial_id.upper()

        # If it's just numbers, add NCT prefix
        if re.match(r"^\d{8}$", trial_id):
            return f"NCT{trial_id}"

        # Otherwise, try to extract NCT ID
        match = re.search(r"NCT\d{8}", trial_id.upper())
        if match:
            return match.group(0)

        # Default: uppercase and hope for the best
        logger.warning(f"Could not parse NCT ID from: {trial_id}")
        return trial_id.upper()

    def _filter_by_phase(self, trials: List[Any], phases: List[int]) -> List[Any]:
        """
        Filter trials by clinical phase.

        Args:
            trials: List of trial objects from CoGEx
            phases: List of phases to include (e.g., [1, 2, 3, 4])

        Returns:
            Filtered list of trials

        Example:
            >>> filtered = client._filter_by_phase(trials, [3, 4])
            >>> # Returns only Phase 3 and Phase 4 trials
        """
        filtered = []
        for trial in trials:
            # Handle both dict and object responses
            if isinstance(trial, dict):
                trial_phase = trial.get("phase")
            else:
                trial_phase = getattr(trial, "phase", None)

            # Parse phase (may be string like "Phase 3" or int like 3)
            if trial_phase is not None:
                # Extract numeric phase
                if isinstance(trial_phase, str):
                    phase_match = re.search(r"\d+", trial_phase)
                    if phase_match:
                        trial_phase = int(phase_match.group(0))
                    else:
                        trial_phase = None
                elif isinstance(trial_phase, (int, float)):
                    trial_phase = int(trial_phase)
                else:
                    trial_phase = None

                # Check if phase matches filter
                if trial_phase in phases:
                    filtered.append(trial)
            else:
                # If phase is None, skip it
                continue

        return filtered

    def _filter_by_status(self, trials: List[Any], status: str) -> List[Any]:
        """
        Filter trials by recruitment status.

        Args:
            trials: List of trial objects from CoGEx
            status: Status to filter by (e.g., "Recruiting", "Completed")

        Returns:
            Filtered list of trials

        Example:
            >>> filtered = client._filter_by_status(trials, "Recruiting")
            >>> # Returns only trials currently recruiting
        """
        filtered = []
        status_lower = status.lower()

        for trial in trials:
            # Handle both dict and object responses
            if isinstance(trial, dict):
                trial_status = trial.get("status", "")
            else:
                trial_status = getattr(trial, "status", "")

            # Case-insensitive match
            if trial_status and status_lower in trial_status.lower():
                filtered.append(trial)

        return filtered

    def _format_trial_dict(self, trial: Any) -> Dict[str, Any]:
        """
        Format trial object as dictionary.

        Args:
            trial: Trial object from CoGEx

        Returns:
            Formatted trial dictionary

        Example:
            >>> formatted = client._format_trial_dict(trial)
            >>> # Returns: {"nct_id": "NCT...", "title": "...", "phase": 3, ...}
        """
        # Handle both dict and object responses
        if isinstance(trial, dict):
            trial_dict = trial
        else:
            trial_dict = {
                "nct_id": getattr(trial, "nct_id", "unknown"),
                "title": getattr(trial, "title", "Unknown"),
                "phase": getattr(trial, "phase", None),
                "status": getattr(trial, "status", "unknown"),
                "conditions": getattr(trial, "conditions", []),
                "interventions": getattr(trial, "interventions", []),
            }

        # Build formatted response
        formatted = {
            "nct_id": trial_dict.get("nct_id", "unknown"),
            "title": trial_dict.get("title", "Unknown"),
            "phase": trial_dict.get("phase"),
            "status": trial_dict.get("status", "unknown"),
        }

        # Add optional fields if available
        if "conditions" in trial_dict:
            formatted["conditions"] = trial_dict["conditions"]
        if "interventions" in trial_dict:
            formatted["interventions"] = trial_dict["interventions"]
        if "start_date" in trial_dict:
            formatted["start_date"] = trial_dict["start_date"]
        if "completion_date" in trial_dict:
            formatted["completion_date"] = trial_dict["completion_date"]
        if "enrollment" in trial_dict:
            formatted["enrollment"] = trial_dict["enrollment"]
        if "sponsor" in trial_dict:
            formatted["sponsor"] = trial_dict["sponsor"]

        return formatted
