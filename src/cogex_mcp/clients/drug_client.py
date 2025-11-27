"""
Direct CoGEx drug-target client.

Wraps INDRA CoGEx drug query functions to access drug-target interactions,
therapeutic indications, and side effects from the knowledge graph.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_targets_for_drug,
    get_indications_for_drug,
    get_side_effects_for_drug,
    get_drugs_for_target,
    get_drugs_for_indication,
    get_drugs_for_side_effect,
    is_drug_target,
    drug_has_indication,
)

logger = logging.getLogger(__name__)


class DrugClient:
    """
    Direct drug-target interaction client using CoGEx library functions.

    Provides high-level interface to drug knowledge with:
    - Comprehensive drug profiles (targets, indications, side effects)
    - Drug discovery (find drugs for target/disease)
    - Safety profiling (side effect analysis)
    - Target validation (check drug-target relationships)

    Example usage:
        >>> client = DrugClient()
        >>> result = client.get_drug_profile(
        ...     drug_id="chebi:45783",  # Imatinib
        ...     include_targets=True,
        ...     include_indications=True,
        ... )
        >>> print(f"Found {len(result['targets'])} targets")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize drug client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_drug_profile(
        self,
        drug_id: str,
        include_targets: bool = True,
        include_indications: bool = True,
        include_side_effects: bool = True,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get comprehensive drug profile with targets, indications, and side effects.

        This method queries multiple sources in the knowledge graph to build
        a complete therapeutic profile for a drug, including molecular targets,
        clinical indications, and adverse effects.

        Args:
            drug_id: Drug CURIE (e.g., "chebi:45783", "drugbank:DB00619")
            include_targets: Include molecular targets
            include_indications: Include therapeutic indications
            include_side_effects: Include adverse effects
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with comprehensive drug profile:
                {
                    "success": True,
                    "drug_id": "chebi:45783",
                    "targets": [...],
                    "indications": [...],
                    "side_effects": [...],
                }

        Example:
            >>> result = client.get_drug_profile(
            ...     drug_id="chebi:45783",  # Imatinib
            ...     include_targets=True,
            ...     include_indications=True,
            ... )
            >>> # Returns targets (ABL1, KIT, etc.), indications (CML, GIST), etc.
        """
        logger.info(f"Getting drug profile for {drug_id}")

        # Parse drug identifier
        drug_tuple = self._parse_drug_id(drug_id)

        profile = {
            "success": True,
            "drug_id": drug_id,
        }

        # Fetch targets
        if include_targets:
            logger.debug("Fetching drug targets")
            targets = get_targets_for_drug(drug_tuple, client=client)
            profile["targets"] = self._format_targets(targets)
            logger.info(f"Found {len(profile['targets'])} targets")

        # Fetch indications
        if include_indications:
            logger.debug("Fetching drug indications")
            indications = get_indications_for_drug(drug_tuple, client=client)
            profile["indications"] = self._format_indications(indications)
            logger.info(f"Found {len(profile['indications'])} indications")

        # Fetch side effects
        if include_side_effects:
            logger.debug("Fetching side effects")
            side_effects = get_side_effects_for_drug(drug_tuple, client=client)
            profile["side_effects"] = self._format_side_effects(side_effects)
            logger.info(f"Found {len(profile['side_effects'])} side effects")

        return profile

    @autoclient()
    def find_drugs_for_target(
        self,
        target_id: str,
        action_types: Optional[List[str]] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find drugs that target a specific protein or gene.

        This method identifies all drugs that interact with a molecular target,
        optionally filtered by mechanism of action (inhibitor, agonist, etc.).

        Args:
            target_id: Target gene/protein CURIE (e.g., "hgnc:76", "uniprot:P00519")
            action_types: Filter by action types (e.g., ["inhibitor", "agonist"])
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with drugs targeting the protein:
                {
                    "success": True,
                    "target_id": "hgnc:76",
                    "drugs": [...],
                    "total_drugs": 15,
                }

        Example:
            >>> result = client.find_drugs_for_target(
            ...     target_id="hgnc:76",  # ABL1
            ...     action_types=["inhibitor"],
            ... )
            >>> # Returns Imatinib, Dasatinib, Nilotinib, etc.
        """
        logger.info(f"Finding drugs for target {target_id}")

        # Parse target identifier
        target_tuple = self._parse_drug_id(target_id)

        # Query drugs
        drugs = get_drugs_for_target(target_tuple, client=client)
        logger.debug(f"Retrieved {len(drugs)} drugs")

        # Filter by action type if specified
        if action_types:
            drugs = [
                drug for drug in drugs
                if drug.get("action") in action_types
            ]
            logger.debug(f"After action filter: {len(drugs)} drugs")

        # Format response
        formatted_drugs = []
        for drug in drugs:
            formatted_drugs.append({
                "drug_id": f"{drug.get('namespace', 'unknown').lower()}:{drug.get('identifier', 'unknown')}",
                "drug_name": drug.get("name", "Unknown"),
                "action": drug.get("action", "unknown"),
                "source": drug.get("source", "unknown"),
            })

        return {
            "success": True,
            "target_id": target_id,
            "drugs": formatted_drugs,
            "total_drugs": len(formatted_drugs),
        }

    @autoclient()
    def find_drugs_for_indication(
        self,
        disease_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find drugs indicated for a specific disease.

        This method identifies approved or investigational drugs for treating
        a disease, including clinical trial phase information.

        Args:
            disease_id: Disease CURIE (e.g., "mesh:D000690", "mondo:0005015")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with drugs indicated for disease:
                {
                    "success": True,
                    "disease_id": "mesh:D000690",
                    "drugs": [...],
                    "total_drugs": 5,
                }

        Example:
            >>> result = client.find_drugs_for_indication(
            ...     disease_id="mesh:D000690",  # ALS
            ... )
            >>> # Returns Riluzole, Edaravone, etc.
        """
        logger.info(f"Finding drugs for disease {disease_id}")

        # Parse disease identifier
        disease_tuple = self._parse_drug_id(disease_id)

        # Query drugs
        drugs = get_drugs_for_indication(disease_tuple, client=client)
        logger.debug(f"Retrieved {len(drugs)} drugs")

        # Format response
        formatted_drugs = []
        for drug in drugs:
            formatted_drugs.append({
                "drug_id": f"{drug.get('namespace', 'unknown').lower()}:{drug.get('identifier', 'unknown')}",
                "drug_name": drug.get("name", "Unknown"),
                "indication_type": drug.get("indication_type", "unknown"),
                "max_phase": drug.get("max_phase"),
                "status": drug.get("status", "unknown"),
            })

        return {
            "success": True,
            "disease_id": disease_id,
            "drugs": formatted_drugs,
            "total_drugs": len(formatted_drugs),
        }

    @autoclient()
    def find_drugs_for_side_effect(
        self,
        side_effect: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find drugs that cause a specific side effect.

        This method identifies drugs associated with an adverse effect,
        useful for safety profiling and drug selection.

        Args:
            side_effect: Side effect term or CURIE (e.g., "nausea", "hp:0002017")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with drugs causing side effect:
                {
                    "success": True,
                    "side_effect": "nausea",
                    "drugs": [...],
                    "total_drugs": 42,
                }

        Example:
            >>> result = client.find_drugs_for_side_effect(
            ...     side_effect="nausea",
            ... )
            >>> # Returns drugs commonly causing nausea
        """
        logger.info(f"Finding drugs causing side effect: {side_effect}")

        # Parse side effect identifier (may be plain text or CURIE)
        if ":" in side_effect:
            se_tuple = self._parse_drug_id(side_effect)
        else:
            # Plain text - use as-is
            se_tuple = ("umls", side_effect)

        # Query drugs
        drugs = get_drugs_for_side_effect(se_tuple, client=client)
        logger.debug(f"Retrieved {len(drugs)} drugs")

        # Format response
        formatted_drugs = []
        for drug in drugs:
            formatted_drugs.append({
                "drug_id": f"{drug.get('namespace', 'unknown').lower()}:{drug.get('identifier', 'unknown')}",
                "drug_name": drug.get("name", "Unknown"),
                "frequency": drug.get("frequency"),
                "source": drug.get("source", "unknown"),
            })

        return {
            "success": True,
            "side_effect": side_effect,
            "drugs": formatted_drugs,
            "total_drugs": len(formatted_drugs),
        }

    # Helper methods

    def _parse_drug_id(self, drug_id: str) -> Tuple[str, str]:
        """
        Convert drug/target CURIE to (namespace, identifier) tuple.

        Args:
            drug_id: CURIE string (e.g., "chebi:45783", "hgnc:76")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_drug_id("chebi:45783")
            ("CHEBI", "45783")
            >>> client._parse_drug_id("drugbank:DB00619")
            ("DRUGBANK", "DB00619")
        """
        if ":" in drug_id:
            namespace, identifier = drug_id.split(":", 1)
            # CoGEx expects uppercase namespaces
            return (namespace.upper(), identifier)
        else:
            # Assume ChEBI if no namespace
            logger.debug(f"Assuming CHEBI namespace for: {drug_id}")
            return ("CHEBI", drug_id)

    def _format_targets(self, targets: List[Any]) -> List[Dict[str, Any]]:
        """
        Format drug targets from CoGEx response.

        Args:
            targets: List of target objects from CoGEx

        Returns:
            List of formatted target dictionaries

        Example:
            >>> targets = [Target(name="ABL1", namespace="hgnc", id="76", ...)]
            >>> client._format_targets(targets)
            [{"target_id": "hgnc:76", "target_name": "ABL1", ...}]
        """
        formatted = []
        for target in targets:
            # Handle both dict and object responses
            if isinstance(target, dict):
                target_dict = target
            else:
                # Convert object to dict
                target_dict = {
                    "namespace": getattr(target, "namespace", "unknown"),
                    "identifier": getattr(target, "identifier", "unknown"),
                    "name": getattr(target, "name", "Unknown"),
                    "action": getattr(target, "action", "unknown"),
                    "source": getattr(target, "source", "unknown"),
                }

            formatted.append({
                "target_id": f"{target_dict.get('namespace', 'unknown').lower()}:{target_dict.get('identifier', 'unknown')}",
                "target_name": target_dict.get("name", "Unknown"),
                "action": target_dict.get("action", "unknown"),
                "source": target_dict.get("source", "unknown"),
            })

        return formatted

    def _format_indications(self, indications: List[Any]) -> List[Dict[str, Any]]:
        """
        Format drug indications from CoGEx response.

        Args:
            indications: List of indication objects from CoGEx

        Returns:
            List of formatted indication dictionaries

        Example:
            >>> indications = [Indication(name="Chronic Myeloid Leukemia", ...)]
            >>> client._format_indications(indications)
            [{"disease_id": "mesh:D015464", "disease_name": "CML", ...}]
        """
        formatted = []
        for indication in indications:
            # Handle both dict and object responses
            if isinstance(indication, dict):
                ind_dict = indication
            else:
                # Convert object to dict
                ind_dict = {
                    "namespace": getattr(indication, "namespace", "unknown"),
                    "identifier": getattr(indication, "identifier", "unknown"),
                    "name": getattr(indication, "name", "Unknown"),
                    "indication_type": getattr(indication, "indication_type", "unknown"),
                    "max_phase": getattr(indication, "max_phase", None),
                    "status": getattr(indication, "status", "unknown"),
                }

            formatted.append({
                "disease_id": f"{ind_dict.get('namespace', 'unknown').lower()}:{ind_dict.get('identifier', 'unknown')}",
                "disease_name": ind_dict.get("name", "Unknown"),
                "indication_type": ind_dict.get("indication_type", "unknown"),
                "max_phase": ind_dict.get("max_phase"),
                "status": ind_dict.get("status", "unknown"),
            })

        return formatted

    def _format_side_effects(self, side_effects: List[Any]) -> List[Dict[str, Any]]:
        """
        Format drug side effects from CoGEx response.

        Args:
            side_effects: List of side effect objects from CoGEx

        Returns:
            List of formatted side effect dictionaries

        Example:
            >>> side_effects = [SideEffect(name="Nausea", frequency="common", ...)]
            >>> client._format_side_effects(side_effects)
            [{"effect": "Nausea", "frequency": "common", ...}]
        """
        formatted = []
        for side_effect in side_effects:
            # Handle both dict and object responses
            if isinstance(side_effect, dict):
                se_dict = side_effect
            else:
                # Convert object to dict
                se_dict = {
                    "namespace": getattr(side_effect, "namespace", "unknown"),
                    "identifier": getattr(side_effect, "identifier", "unknown"),
                    "name": getattr(side_effect, "name", "Unknown"),
                    "frequency": getattr(side_effect, "frequency", None),
                    "source": getattr(side_effect, "source", "unknown"),
                }

            formatted.append({
                "effect_id": f"{se_dict.get('namespace', 'unknown').lower()}:{se_dict.get('identifier', 'unknown')}",
                "effect": se_dict.get("name", "Unknown"),
                "frequency": se_dict.get("frequency"),
                "source": se_dict.get("source", "unknown"),
            })

        return formatted
