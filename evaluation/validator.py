"""
Answer Validator for INDRA CoGEx MCP Evaluation Suite

Validates LLM answers against reference criteria and generates
detailed validation reports with scoring.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ValidationScore:
    """Validation score for a single question."""

    question_id: str
    overall_score: float  # 0-100
    component_scores: Dict[str, float]  # Individual rubric scores
    passed: bool
    validation_results: Dict[str, Any]
    feedback: List[str]
    warnings: List[str]
    errors: List[str]


class AnswerValidator:
    """
    Validate LLM answers against reference criteria.

    Performs multiple validation checks:
    - Entity presence (required entities mentioned)
    - Tool usage (correct tools invoked)
    - Structural requirements (format, completeness)
    - Numerical accuracy (counts, p-values, scores)
    - Biological reasoning quality
    """

    def __init__(
        self,
        reference_file: str = "reference_answers.json",
        passing_threshold: float = 70.0,
    ):
        """
        Initialize validator.

        Args:
            reference_file: Path to reference answers JSON
            passing_threshold: Minimum score to pass (0-100)
        """
        self.passing_threshold = passing_threshold

        # Load reference answers
        with open(reference_file, 'r') as f:
            data = json.load(f)
            self.references = data["questions"]
            self.metadata = data["metadata"]
            self.scoring = data["scoring_guidelines"]

    def validate_answer(
        self,
        question_id: str,
        answer: str,
        tools_used: List[str],
        tool_call_count: int,
        execution_successful: bool,
    ) -> ValidationScore:
        """
        Validate a single answer against reference criteria.

        Args:
            question_id: Question ID (e.g., "q1")
            answer: LLM's answer text
            tools_used: List of tool names used
            tool_call_count: Total number of tool calls
            execution_successful: Whether execution completed without errors

        Returns:
            ValidationScore with detailed breakdown
        """
        if question_id not in self.references:
            return self._create_error_score(
                question_id,
                f"Question {question_id} not found in references"
            )

        ref = self.references[question_id]

        # Initialize tracking
        feedback = []
        warnings = []
        errors = []
        validation_results = {}
        component_scores = {}

        # Skip validation if execution failed
        if not execution_successful:
            errors.append("Question execution failed")
            return ValidationScore(
                question_id=question_id,
                overall_score=0.0,
                component_scores={},
                passed=False,
                validation_results={"execution_failed": True},
                feedback=[],
                warnings=[],
                errors=errors,
            )

        # 1. Entity Presence Check
        entity_score, entity_feedback = self._check_entity_presence(
            answer, ref.get("key_entities", [])
        )
        component_scores["entity_presence"] = entity_score
        feedback.extend(entity_feedback)
        validation_results["entities_found"] = entity_score > 0

        # 2. Tool Usage Check
        tool_score, tool_feedback = self._check_tool_usage(
            tools_used,
            ref.get("expected_tools", []),
            tool_call_count,
            ref.get("min_tool_calls", 0),
            ref.get("max_tool_calls", 100),
        )
        component_scores["tool_usage"] = tool_score
        feedback.extend(tool_feedback)
        validation_results["tool_usage_appropriate"] = tool_score >= 50

        # 3. Structural Validation
        structure_score, structure_feedback = self._check_structure(
            answer, ref
        )
        component_scores["structure"] = structure_score
        feedback.extend(structure_feedback)
        validation_results["structure_valid"] = structure_score >= 50

        # 4. Numerical Data Validation
        numerical_score, numerical_feedback = self._check_numerical_data(
            answer, ref.get("validation_patterns", {})
        )
        component_scores["numerical_accuracy"] = numerical_score
        feedback.extend(numerical_feedback)
        validation_results["numerical_data_present"] = numerical_score > 0

        # 5. Keyword Presence
        keyword_score, keyword_feedback = self._check_keywords(
            answer, ref.get("keywords_required", [])
        )
        component_scores["keyword_coverage"] = keyword_score
        feedback.extend(keyword_feedback)

        # 6. Answer Length Check
        length_valid, length_feedback = self._check_length(
            answer, ref.get("min_answer_length", 100)
        )
        if not length_valid:
            warnings.append(length_feedback)
        validation_results["length_appropriate"] = length_valid

        # 7. Biological Reasoning Quality (heuristic)
        reasoning_score, reasoning_feedback = self._assess_biological_reasoning(
            answer, ref
        )
        component_scores["biological_reasoning"] = reasoning_score
        feedback.extend(reasoning_feedback)

        # Calculate overall score using rubric weights
        overall_score = self._calculate_overall_score(
            component_scores,
            ref.get("scoring_rubric", {})
        )

        passed = overall_score >= self.passing_threshold

        return ValidationScore(
            question_id=question_id,
            overall_score=overall_score,
            component_scores=component_scores,
            passed=passed,
            validation_results=validation_results,
            feedback=feedback,
            warnings=warnings,
            errors=errors,
        )

    def validate_all(
        self,
        results_file: str,
        output_file: str,
    ) -> Dict[str, Any]:
        """
        Validate all results from evaluation run.

        Args:
            results_file: Path to evaluation results JSON
            output_file: Path to save validation report

        Returns:
            Validation report dictionary
        """
        # Load evaluation results
        with open(results_file, 'r') as f:
            eval_data = json.load(f)

        results = eval_data.get("results", [])

        # Validate each result
        validation_scores = []
        for result in results:
            score = self.validate_answer(
                question_id=result["question_id"],
                answer=result["llm_answer"],
                tools_used=result["tools_used"],
                tool_call_count=result["tool_call_count"],
                execution_successful=result["execution_successful"],
            )
            validation_scores.append(score)

        # Generate report
        report = self._generate_validation_report(
            validation_scores,
            eval_data.get("metadata", {}),
            eval_data.get("summary", {}),
        )

        # Save report
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Print summary
        self._print_validation_summary(report)

        return report

    def _check_entity_presence(
        self,
        answer: str,
        key_entities: List[str],
    ) -> Tuple[float, List[str]]:
        """Check if key entities are mentioned in answer."""
        if not key_entities:
            return 100.0, []

        answer_lower = answer.lower()
        found_entities = []
        missing_entities = []

        for entity in key_entities:
            if entity.lower() in answer_lower:
                found_entities.append(entity)
            else:
                missing_entities.append(entity)

        score = (len(found_entities) / len(key_entities)) * 100

        feedback = []
        if found_entities:
            feedback.append(f"✓ Found entities: {', '.join(found_entities)}")
        if missing_entities:
            feedback.append(f"✗ Missing entities: {', '.join(missing_entities)}")

        return score, feedback

    def _check_tool_usage(
        self,
        tools_used: List[str],
        expected_tools: List[str],
        tool_call_count: int,
        min_calls: int,
        max_calls: int,
    ) -> Tuple[float, List[str]]:
        """Validate tool usage."""
        feedback = []
        scores = []

        # Check expected tools used
        if expected_tools:
            tools_used_set = set(tools_used)
            expected_set = set(expected_tools)

            found_tools = tools_used_set & expected_set
            missing_tools = expected_set - tools_used_set
            extra_tools = tools_used_set - expected_set

            tool_coverage = (len(found_tools) / len(expected_set)) * 100 if expected_set else 100
            scores.append(tool_coverage)

            if found_tools:
                feedback.append(f"✓ Used expected tools: {', '.join(found_tools)}")
            if missing_tools:
                feedback.append(f"✗ Missing tools: {', '.join(missing_tools)}")
            if extra_tools:
                feedback.append(f"ℹ Extra tools used: {', '.join(extra_tools)}")

        # Check tool call count
        if min_calls > 0:
            if tool_call_count < min_calls:
                count_score = (tool_call_count / min_calls) * 100
                feedback.append(
                    f"⚠ Tool calls ({tool_call_count}) below expected minimum ({min_calls})"
                )
            elif tool_call_count > max_calls:
                count_score = 90.0  # Penalty for excessive calls
                feedback.append(
                    f"⚠ Tool calls ({tool_call_count}) above expected maximum ({max_calls})"
                )
            else:
                count_score = 100.0
                feedback.append(f"✓ Tool call count appropriate ({tool_call_count})")

            scores.append(count_score)

        overall_score = sum(scores) / len(scores) if scores else 100.0
        return overall_score, feedback

    def _check_structure(
        self,
        answer: str,
        ref: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Check structural requirements from validation patterns."""
        patterns = ref.get("validation_patterns", {})
        feedback = []
        scores = []

        # Check for required ID formats
        if "reactome_id" in patterns:
            pattern = patterns["reactome_id"]
            if re.search(pattern, answer):
                feedback.append("✓ Contains valid Reactome ID")
                scores.append(100)
            else:
                feedback.append("✗ Missing valid Reactome ID format")
                scores.append(0)

        if "rsid_format" in patterns:
            pattern = patterns["rsid_format"]
            if re.search(pattern, answer):
                feedback.append("✓ Contains valid rsID")
                scores.append(100)
            else:
                feedback.append("✗ Missing valid rsID format")
                scores.append(0)

        if "pmid_format" in patterns:
            pattern = patterns["pmid_format"]
            if re.search(pattern, answer):
                feedback.append("✓ Contains valid PMID")
                scores.append(100)
            else:
                feedback.append("✗ Missing valid PMID format")
                scores.append(0)

        # Default if no patterns specified
        if not scores:
            return 100.0, ["ℹ No structural requirements specified"]

        return sum(scores) / len(scores), feedback

    def _check_numerical_data(
        self,
        answer: str,
        patterns: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Check for presence of numerical data."""
        feedback = []
        scores = []

        # Check for p-values
        if "p_value_format" in patterns:
            p_value_pattern = r'\d\.?\d*e-?\d+'
            p_values = re.findall(p_value_pattern, answer)
            if p_values:
                feedback.append(f"✓ Found p-values: {len(p_values)} instances")
                scores.append(100)
            else:
                feedback.append("✗ No p-values found")
                scores.append(0)

        # Check for counts
        count_patterns = [
            r'\d+\s+genes',
            r'\d+\s+pathways',
            r'\d+\s+targets',
            r'\d+\s+trials',
        ]
        count_found = any(re.search(pattern, answer.lower()) for pattern in count_patterns)
        if count_found:
            feedback.append("✓ Contains numerical counts")
            scores.append(100)
        else:
            feedback.append("⚠ Limited numerical data")
            scores.append(50)

        if not scores:
            return 100.0, []

        return sum(scores) / len(scores), feedback

    def _check_keywords(
        self,
        answer: str,
        required_keywords: List[str],
    ) -> Tuple[float, List[str]]:
        """Check for required keywords."""
        if not required_keywords:
            return 100.0, []

        answer_lower = answer.lower()
        found_keywords = []
        missing_keywords = []

        for keyword in required_keywords:
            if keyword.lower() in answer_lower:
                found_keywords.append(keyword)
            else:
                missing_keywords.append(keyword)

        score = (len(found_keywords) / len(required_keywords)) * 100

        feedback = []
        if found_keywords:
            feedback.append(f"✓ Found keywords: {', '.join(found_keywords)}")
        if missing_keywords:
            feedback.append(f"✗ Missing keywords: {', '.join(missing_keywords)}")

        return score, feedback

    def _check_length(
        self,
        answer: str,
        min_length: int,
    ) -> Tuple[bool, str]:
        """Check if answer meets minimum length."""
        actual_length = len(answer)
        if actual_length >= min_length:
            return True, f"Answer length: {actual_length} chars (minimum: {min_length})"
        else:
            return False, f"Answer too short: {actual_length} chars (minimum: {min_length})"

    def _assess_biological_reasoning(
        self,
        answer: str,
        ref: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Heuristic assessment of biological reasoning quality."""
        feedback = []
        scores = []

        # Check for biological context keywords
        reasoning_keywords = [
            'because', 'therefore', 'due to', 'resulting in',
            'pathway', 'mechanism', 'regulation', 'function',
            'associated', 'involved', 'role', 'effect'
        ]

        answer_lower = answer.lower()
        found_reasoning = sum(1 for kw in reasoning_keywords if kw in answer_lower)

        reasoning_density = (found_reasoning / len(reasoning_keywords)) * 100
        scores.append(reasoning_density)

        if reasoning_density > 30:
            feedback.append("✓ Answer includes biological reasoning")
        else:
            feedback.append("⚠ Limited biological context")

        # Check if biological context from reference is addressed
        bio_context = ref.get("biological_context", "")
        if bio_context:
            # Extract key terms from biological context
            context_terms = re.findall(r'\b[A-Z][A-Za-z]{4,}\b', bio_context)
            terms_mentioned = sum(1 for term in context_terms if term in answer)

            if terms_mentioned > 0:
                context_score = min((terms_mentioned / len(context_terms)) * 100, 100)
                scores.append(context_score)
                feedback.append(f"✓ Addresses {terms_mentioned} key biological concepts")
            else:
                scores.append(50)
                feedback.append("⚠ Limited connection to biological context")

        return sum(scores) / len(scores) if scores else 75.0, feedback

    def _calculate_overall_score(
        self,
        component_scores: Dict[str, float],
        rubric: Dict[str, float],
    ) -> float:
        """Calculate weighted overall score using rubric."""
        if not rubric:
            # Equal weighting if no rubric
            return sum(component_scores.values()) / len(component_scores) if component_scores else 0

        # Normalize rubric to percentages
        total_weight = sum(rubric.values())
        normalized_rubric = {k: (v / total_weight) for k, v in rubric.items()}

        # Calculate weighted score
        weighted_score = 0
        for component, score in component_scores.items():
            # Map component names to rubric keys (flexible matching)
            rubric_key = None
            for rk in normalized_rubric.keys():
                if component.lower() in rk.lower() or rk.lower() in component.lower():
                    rubric_key = rk
                    break

            if rubric_key:
                weighted_score += score * normalized_rubric[rubric_key]
            else:
                # If no rubric entry, contribute proportionally
                weighted_score += score / len(component_scores)

        return min(weighted_score, 100.0)

    def _generate_validation_report(
        self,
        validation_scores: List[ValidationScore],
        eval_metadata: Dict[str, Any],
        eval_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        total = len(validation_scores)
        passed = sum(1 for vs in validation_scores if vs.passed)

        avg_score = sum(vs.overall_score for vs in validation_scores) / total if total > 0 else 0

        # Component score averages
        all_components = set()
        for vs in validation_scores:
            all_components.update(vs.component_scores.keys())

        component_averages = {}
        for component in all_components:
            scores = [
                vs.component_scores.get(component, 0)
                for vs in validation_scores
            ]
            component_averages[component] = sum(scores) / len(scores) if scores else 0

        # Category breakdown
        categories = {}
        for vs in validation_scores:
            q_ref = self.references.get(vs.question_id, {})
            category = q_ref.get("category", "unknown")

            if category not in categories:
                categories[category] = {
                    "total": 0,
                    "passed": 0,
                    "avg_score": 0,
                }

            categories[category]["total"] += 1
            if vs.passed:
                categories[category]["passed"] += 1
            categories[category]["avg_score"] += vs.overall_score

        # Calculate category averages
        for cat in categories.values():
            if cat["total"] > 0:
                cat["avg_score"] /= cat["total"]

        report = {
            "metadata": {
                "validation_timestamp": datetime.now().isoformat(),
                "evaluation_timestamp": eval_metadata.get("timestamp", ""),
                "model": eval_metadata.get("model", ""),
                "passing_threshold": self.passing_threshold,
            },
            "summary": {
                "total_questions": total,
                "questions_passed": passed,
                "questions_failed": total - passed,
                "pass_rate": (passed / total * 100) if total > 0 else 0,
                "average_score": avg_score,
                "component_averages": component_averages,
            },
            "category_performance": categories,
            "detailed_scores": [asdict(vs) for vs in validation_scores],
            "evaluation_summary": eval_summary,
        }

        return report

    def _print_validation_summary(self, report: Dict[str, Any]):
        """Print validation summary to console."""
        summary = report["summary"]

        print("\n" + "="*80)
        print("VALIDATION REPORT")
        print("="*80)
        print(f"Model: {report['metadata']['model']}")
        print(f"Questions: {summary['total_questions']}")
        print(f"Passed: {summary['questions_passed']} ({summary['pass_rate']:.1f}%)")
        print(f"Failed: {summary['questions_failed']}")
        print(f"Average Score: {summary['average_score']:.1f}/100")
        print(f"Passing Threshold: {report['metadata']['passing_threshold']}")

        print("\n" + "-"*80)
        print("Component Scores:")
        print("-"*80)
        for component, score in summary['component_averages'].items():
            print(f"  {component:.<50} {score:>6.1f}")

        print("\n" + "-"*80)
        print("Category Performance:")
        print("-"*80)
        for category, data in report['category_performance'].items():
            pass_rate = (data['passed'] / data['total'] * 100) if data['total'] > 0 else 0
            print(f"  {category:.<40} {data['passed']}/{data['total']} ({pass_rate:.0f}%) - Avg: {data['avg_score']:.1f}")

        print("="*80 + "\n")

    def _create_error_score(self, question_id: str, error_msg: str) -> ValidationScore:
        """Create error validation score."""
        return ValidationScore(
            question_id=question_id,
            overall_score=0.0,
            component_scores={},
            passed=False,
            validation_results={},
            feedback=[],
            warnings=[],
            errors=[error_msg],
        )


def main():
    """Main entry point for validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate INDRA CoGEx MCP evaluation results"
    )
    parser.add_argument(
        "--results",
        required=True,
        help="Path to evaluation results JSON",
    )
    parser.add_argument(
        "--output",
        default="results/validation_report.json",
        help="Output file for validation report",
    )
    parser.add_argument(
        "--reference",
        default="reference_answers.json",
        help="Path to reference answers JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        help="Passing threshold (0-100)",
    )

    args = parser.parse_args()

    validator = AnswerValidator(
        reference_file=args.reference,
        passing_threshold=args.threshold,
    )

    validator.validate_all(
        results_file=args.results,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
