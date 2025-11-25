"""
Evaluation Runner for INDRA CoGEx MCP Server

Executes evaluation questions through an LLM with MCP tools,
tracks tool invocations, and collects results for validation.
"""

import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import anthropic
import os


@dataclass
class Question:
    """Evaluation question with metadata."""

    id: str
    category: str
    difficulty: str
    text: str
    expected_tools: List[str]
    validation_criteria: Dict[str, Any]
    reference_answer: str
    estimated_tool_calls: str
    estimated_time_seconds: str


@dataclass
class EvaluationResult:
    """Result from executing a single evaluation question."""

    question_id: str
    question_text: str
    category: str
    difficulty: str

    # Execution metrics
    start_time: str
    end_time: str
    elapsed_seconds: float

    # LLM response
    llm_answer: str
    raw_response: Dict[str, Any]

    # Tool usage
    tools_used: List[str]
    tool_call_count: int
    tool_call_sequence: List[Dict[str, Any]]

    # Status
    execution_successful: bool
    error_message: Optional[str] = None

    # Model info
    model_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class EvaluationRunner:
    """
    Run evaluation suite against MCP server through Claude API.

    This runner:
    1. Loads questions from XML
    2. Sends each question to Claude with MCP tools enabled
    3. Tracks tool invocations and responses
    4. Collects timing and token metrics
    5. Saves results for validation
    """

    def __init__(
        self,
        model_name: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 16000,
        temperature: float = 0.0,
    ):
        """
        Initialize evaluation runner.

        Args:
            model_name: Claude model to use for evaluation
            max_tokens: Maximum tokens for responses
            temperature: Sampling temperature (0.0 for deterministic)
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.results: List[EvaluationResult] = []

    def load_questions(self, questions_file: str) -> List[Question]:
        """
        Load evaluation questions from XML file.

        Args:
            questions_file: Path to questions.xml

        Returns:
            List of Question objects
        """
        tree = ET.parse(questions_file)
        root = tree.getroot()

        questions = []
        for q in root.findall("question"):
            # Parse validation criteria
            criteria = {}
            criteria_elem = q.find("validation_criteria")
            if criteria_elem is not None:
                for criterion in criteria_elem.findall("criterion"):
                    criteria[criterion.get("type")] = criterion.text

            # Parse expected tools
            expected_tools = []
            tools_elem = q.find("expected_tools")
            if tools_elem is not None and tools_elem.text:
                expected_tools = [
                    tool.strip()
                    for tool in tools_elem.text.split(",")
                ]

            question = Question(
                id=q.get("id"),
                category=q.get("category"),
                difficulty=q.get("difficulty"),
                text=q.find("text").text.strip(),
                expected_tools=expected_tools,
                validation_criteria=criteria,
                reference_answer=q.find("reference_answer").text.strip(),
                estimated_tool_calls=q.find("estimated_tool_calls").text.strip(),
                estimated_time_seconds=q.find("estimated_time_seconds").text.strip(),
            )
            questions.append(question)

        return questions

    async def run_question(
        self,
        question: Question,
        mcp_server_command: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        Run a single evaluation question through Claude with MCP.

        Args:
            question: Question to evaluate
            mcp_server_command: Command to start MCP server (e.g., ["python", "-m", "cogex_mcp.server"])

        Returns:
            EvaluationResult with execution details
        """
        start_time = datetime.now()

        print(f"\n{'='*80}")
        print(f"Running Question {question.id}: {question.category}")
        print(f"Difficulty: {question.difficulty}")
        print(f"{'='*80}")
        print(f"\nQuestion:\n{question.text}\n")

        try:
            # Prepare system prompt with MCP context
            system_prompt = self._prepare_system_prompt()

            # Prepare messages
            messages = [
                {
                    "role": "user",
                    "content": question.text,
                }
            ]

            # Call Claude API with tool use
            # Note: This is a simplified version - in production, you'd use
            # the MCP SDK or implement full MCP protocol handling
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=messages,
            )

            # Extract answer from response
            answer = self._extract_answer(response)

            # Track tool usage
            tools_used, tool_calls, tool_call_sequence = self._track_tool_usage(response)

            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            print(f"\nCompleted in {elapsed:.1f}s")
            print(f"Tools used ({len(tools_used)}): {', '.join(tools_used)}")
            print(f"Total tool calls: {tool_calls}")

            result = EvaluationResult(
                question_id=question.id,
                question_text=question.text,
                category=question.category,
                difficulty=question.difficulty,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                elapsed_seconds=elapsed,
                llm_answer=answer,
                raw_response=self._serialize_response(response),
                tools_used=tools_used,
                tool_call_count=tool_calls,
                tool_call_sequence=tool_call_sequence,
                execution_successful=True,
                model_name=self.model_name,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except Exception as e:
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            print(f"\n❌ Error: {str(e)}")

            result = EvaluationResult(
                question_id=question.id,
                question_text=question.text,
                category=question.category,
                difficulty=question.difficulty,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                elapsed_seconds=elapsed,
                llm_answer="",
                raw_response={},
                tools_used=[],
                tool_call_count=0,
                tool_call_sequence=[],
                execution_successful=False,
                error_message=str(e),
                model_name=self.model_name,
            )

        self.results.append(result)
        return result

    async def run_all(
        self,
        questions_file: str,
        output_file: str,
        mcp_server_command: Optional[List[str]] = None,
        start_from: Optional[int] = None,
        end_at: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run all evaluation questions and generate report.

        Args:
            questions_file: Path to questions.xml
            output_file: Path to save results JSON
            mcp_server_command: Command to start MCP server
            start_from: Start from question N (1-indexed)
            end_at: End at question N (1-indexed, inclusive)

        Returns:
            Evaluation report dictionary
        """
        questions = self.load_questions(questions_file)

        # Filter questions if range specified
        if start_from or end_at:
            start_idx = (start_from - 1) if start_from else 0
            end_idx = end_at if end_at else len(questions)
            questions = questions[start_idx:end_idx]

        print(f"\n{'='*80}")
        print(f"INDRA CoGEx MCP Evaluation Suite")
        print(f"{'='*80}")
        print(f"Model: {self.model_name}")
        print(f"Questions: {len(questions)}")
        print(f"{'='*80}\n")

        # Run each question
        for i, question in enumerate(questions, 1):
            print(f"\nProgress: {i}/{len(questions)}")
            await self.run_question(question, mcp_server_command)

            # Brief pause between questions
            if i < len(questions):
                await asyncio.sleep(2)

        # Generate report
        report = self.generate_report()

        # Save results
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*80}")
        print(f"Evaluation Complete!")
        print(f"{'='*80}")
        print(f"Results saved to: {output_file}")
        print(f"Total time: {report['summary']['total_time_seconds']:.1f}s")
        print(f"Successful: {report['summary']['successful_questions']}/{report['summary']['total_questions']}")
        print(f"{'='*80}\n")

        return report

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate evaluation report from collected results.

        Returns:
            Report dictionary with summary and detailed results
        """
        total = len(self.results)
        successful = sum(1 for r in self.results if r.execution_successful)

        total_time = sum(r.elapsed_seconds for r in self.results)
        total_tool_calls = sum(r.tool_call_count for r in self.results)
        total_input_tokens = sum(r.input_tokens for r in self.results)
        total_output_tokens = sum(r.output_tokens for r in self.results)

        # Calculate averages for successful questions
        if successful > 0:
            avg_time = sum(
                r.elapsed_seconds for r in self.results if r.execution_successful
            ) / successful
            avg_tool_calls = sum(
                r.tool_call_count for r in self.results if r.execution_successful
            ) / successful
        else:
            avg_time = 0
            avg_tool_calls = 0

        # Tool usage statistics
        all_tools_used = []
        for r in self.results:
            all_tools_used.extend(r.tools_used)

        unique_tools = set(all_tools_used)
        tool_frequency = {
            tool: all_tools_used.count(tool)
            for tool in unique_tools
        }

        # Category breakdown
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = {
                    "total": 0,
                    "successful": 0,
                    "avg_time": 0,
                    "avg_tool_calls": 0,
                }
            categories[r.category]["total"] += 1
            if r.execution_successful:
                categories[r.category]["successful"] += 1
                categories[r.category]["avg_time"] += r.elapsed_seconds
                categories[r.category]["avg_tool_calls"] += r.tool_call_count

        # Calculate category averages
        for cat in categories.values():
            if cat["successful"] > 0:
                cat["avg_time"] /= cat["successful"]
                cat["avg_tool_calls"] /= cat["successful"]

        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model": self.model_name,
                "evaluation_version": "1.0.0",
            },
            "summary": {
                "total_questions": total,
                "successful_questions": successful,
                "failed_questions": total - successful,
                "success_rate": successful / total if total > 0 else 0,
                "total_time_seconds": total_time,
                "avg_time_per_question": avg_time,
                "total_tool_calls": total_tool_calls,
                "avg_tool_calls_per_question": avg_tool_calls,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "unique_tools_used": len(unique_tools),
                "tool_frequency": tool_frequency,
            },
            "category_breakdown": categories,
            "results": [asdict(r) for r in self.results],
        }

        return report

    def _prepare_system_prompt(self) -> str:
        """Prepare system prompt for evaluation."""
        return """You are a biomedical research assistant with access to the INDRA CoGEx
knowledge graph through MCP tools. Answer the user's question using the available tools.

Guidelines:
- Use multiple tools to gather comprehensive information
- Provide specific numerical data, identifiers, and entity names
- Structure your response clearly with all requested components
- Cite tool outputs to support your answer
- Be precise with biological terminology and database identifiers

Available tools include:
- cogex_query_gene_or_feature: Query genes, tissues, GO terms, domains, phenotypes
- cogex_extract_subnetwork: Extract regulatory networks and mechanistic relationships
- cogex_enrichment_analysis: Perform pathway/GO enrichment analysis
- cogex_query_drug_or_effect: Query drugs, targets, indications, side effects
- cogex_query_disease_or_phenotype: Query diseases, genes, variants, phenotypes
- cogex_query_pathway: Query pathways and gene-pathway relationships
- cogex_query_cell_line: Query cell line mutations, dependencies, expression
- cogex_query_clinical_trials: Query clinical trials by drug/disease
- cogex_query_literature: Query literature evidence and INDRA statements
- cogex_query_variants: Query genetic variants and GWAS associations
- cogex_resolve_identifiers: Convert between identifier namespaces
- cogex_check_relationship: Validate biological relationships
- cogex_get_ontology_hierarchy: Navigate ontology hierarchies
- cogex_query_cell_markers: Query cell type markers
- cogex_analyze_kinase_enrichment: Analyze kinase enrichment from phosphosites
- cogex_query_protein_functions: Query protein functions and enzyme activities

Answer comprehensively and accurately."""

    def _extract_answer(self, response) -> str:
        """Extract final answer from Claude response."""
        # Combine all text content blocks
        answer_parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                answer_parts.append(block.text)

        return "\n".join(answer_parts)

    def _track_tool_usage(self, response) -> tuple[List[str], int, List[Dict[str, Any]]]:
        """
        Track tool usage from response.

        Returns:
            (unique_tools_used, total_tool_calls, tool_call_sequence)
        """
        tools_used = set()
        tool_call_count = 0
        tool_call_sequence = []

        for block in response.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                tool_name = block.name
                tools_used.add(tool_name)
                tool_call_count += 1

                tool_call_sequence.append({
                    "tool_name": tool_name,
                    "tool_input": block.input if hasattr(block, 'input') else {},
                    "call_index": tool_call_count,
                })

        return list(tools_used), tool_call_count, tool_call_sequence

    def _serialize_response(self, response) -> Dict[str, Any]:
        """Serialize Claude API response to JSON-compatible dict."""
        return {
            "id": response.id,
            "type": response.type,
            "role": response.role,
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "content": [
                {
                    "type": block.type,
                    "text": block.text if hasattr(block, 'text') else None,
                }
                for block in response.content
            ],
        }


async def main():
    """Main entry point for running evaluations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run INDRA CoGEx MCP evaluation suite"
    )
    parser.add_argument(
        "--questions",
        default="questions.xml",
        help="Path to questions XML file",
    )
    parser.add_argument(
        "--output",
        default="results/evaluation_results.json",
        help="Output file for results",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5-20250929",
        help="Claude model to use",
    )
    parser.add_argument(
        "--start-from",
        type=int,
        help="Start from question N (1-indexed)",
    )
    parser.add_argument(
        "--end-at",
        type=int,
        help="End at question N (1-indexed, inclusive)",
    )

    args = parser.parse_args()

    runner = EvaluationRunner(model_name=args.model)

    await runner.run_all(
        questions_file=args.questions,
        output_file=args.output,
        start_from=args.start_from,
        end_at=args.end_at,
    )


if __name__ == "__main__":
    asyncio.run(main())
