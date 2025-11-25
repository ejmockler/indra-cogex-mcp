# INDRA CoGEx MCP Evaluation Suite

Comprehensive evaluation framework for testing LLM effectiveness with the INDRA CoGEx MCP server through complex, realistic biomedical questions.

## Overview

This evaluation suite consists of **10 carefully designed questions** that test:
- Multi-tool workflows (3-10 tool invocations per question)
- Biological reasoning and interpretation
- Integration of evidence from multiple sources
- Handling of complex, multi-step research questions
- Accuracy in biomedical data retrieval and analysis

## Question Categories

1. **Drug-Target-Pathway Integration** (1 question)
   - Tests: Drug target identification, pathway analysis, network extraction
   - Tools: `cogex_query_drug_or_effect`, `cogex_query_pathway`, `cogex_extract_subnetwork`
   - Difficulty: Hard

2. **Disease-Gene-Variant Association** (2 questions)
   - Tests: Disease mechanisms, GWAS data, variant analysis, cross-disease associations
   - Tools: `cogex_query_disease_or_phenotype`, `cogex_query_variants`, `cogex_check_relationship`
   - Difficulty: Hard

3. **Cell Line-Mutation-Drug Sensitivity** (1 question)
   - Tests: Cell line profiling, functional annotation, drug matching, enrichment analysis
   - Tools: `cogex_query_cell_line`, `cogex_query_protein_functions`, `cogex_enrichment_analysis`
   - Difficulty: Hard

4. **Clinical Trial-Drug-Disease Matching** (1 question)
   - Tests: Clinical trial filtering, indication identification, relationship verification
   - Tools: `cogex_query_clinical_trials`, `cogex_check_relationship`
   - Difficulty: Medium

5. **Pathway Enrichment Analysis** (2 questions)
   - Tests: Enrichment analysis, pathway analysis, network topology, candidate gene discovery
   - Tools: `cogex_enrichment_analysis`, `cogex_query_pathway`, `cogex_extract_subnetwork`
   - Difficulty: Hard

6. **Identifier Resolution Workflow** (1 question)
   - Tests: Multi-namespace identifier conversion, expression profiling
   - Tools: `cogex_resolve_identifiers`, `cogex_query_gene_or_feature`
   - Difficulty: Medium

7. **Multi-Evidence Literature Integration** (1 question)
   - Tests: Literature search, statement extraction, evidence quality assessment
   - Tools: `cogex_extract_subnetwork`, `cogex_query_literature`
   - Difficulty: Hard

8. **Ontology Navigation with Phenotype Analysis** (1 question)
   - Tests: Ontology traversal, phenotype-gene mapping, functional classification
   - Tools: `cogex_get_ontology_hierarchy`, `cogex_query_gene_or_feature`, `cogex_query_protein_functions`
   - Difficulty: Medium

## File Structure

```
evaluation/
├── __init__.py                    # Package initialization
├── questions.xml                  # 10 evaluation questions with validation criteria
├── reference_answers.json         # Expected answers, scoring rubrics, validation patterns
├── runner.py                      # Evaluation execution framework
├── validator.py                   # Answer validation and scoring logic
├── README.md                      # This file
└── results/                       # Output directory (created on first run)
    ├── evaluation_results.json    # Execution results with timing and tool usage
    └── validation_report.json     # Validation scores and feedback
```

## Installation

The evaluation suite requires:

```bash
# Core dependencies (already in main project)
pip install anthropic  # Claude API client
pip install lxml       # XML parsing

# Ensure INDRA CoGEx MCP server is installed
pip install -e ".[dev]"
```

## Configuration

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Running Evaluations

### Quick Start

Run all 10 questions:

```bash
cd evaluation
python runner.py --questions questions.xml --output results/run_001.json
```

### Run Specific Questions

Run questions 1-3 only:

```bash
python runner.py --questions questions.xml --output results/run_001.json --start-from 1 --end-at 3
```

### Use Different Model

```bash
python runner.py --questions questions.xml --output results/run_opus.json --model claude-opus-4-20250514
```

### Command Line Options

```bash
python runner.py --help

Options:
  --questions PATH    Path to questions XML (default: questions.xml)
  --output PATH       Output file for results (default: results/evaluation_results.json)
  --model NAME        Claude model to use (default: claude-sonnet-4-5-20250929)
  --start-from N      Start from question N (1-indexed)
  --end-at N          End at question N (1-indexed, inclusive)
```

## Validating Results

After running evaluations, validate the answers:

```bash
python validator.py --results results/run_001.json --output results/validation_001.json
```

### Validation Options

```bash
python validator.py --help

Options:
  --results PATH      Path to evaluation results JSON (required)
  --output PATH       Output file for validation report (default: results/validation_report.json)
  --reference PATH    Path to reference answers (default: reference_answers.json)
  --threshold FLOAT   Passing threshold 0-100 (default: 70.0)
```

## Understanding Results

### Evaluation Results (`evaluation_results.json`)

```json
{
  "metadata": {
    "timestamp": "2025-11-24T10:30:00",
    "model": "claude-sonnet-4-5-20250929",
    "evaluation_version": "1.0.0"
  },
  "summary": {
    "total_questions": 10,
    "successful_questions": 10,
    "success_rate": 1.0,
    "total_time_seconds": 542.3,
    "avg_time_per_question": 54.2,
    "total_tool_calls": 67,
    "avg_tool_calls_per_question": 6.7,
    "total_input_tokens": 45000,
    "total_output_tokens": 25000,
    "unique_tools_used": 14,
    "tool_frequency": {
      "cogex_query_gene_or_feature": 12,
      "cogex_query_pathway": 8,
      "cogex_enrichment_analysis": 6,
      ...
    }
  },
  "category_breakdown": {
    "drug-target-pathway": {
      "total": 1,
      "successful": 1,
      "avg_time": 58.3,
      "avg_tool_calls": 7
    },
    ...
  },
  "results": [
    {
      "question_id": "q1",
      "question_text": "...",
      "category": "drug-target-pathway",
      "llm_answer": "...",
      "tools_used": ["cogex_query_drug_or_effect", ...],
      "tool_call_count": 7,
      "elapsed_seconds": 58.3,
      ...
    }
  ]
}
```

### Validation Report (`validation_report.json`)

```json
{
  "metadata": {
    "validation_timestamp": "2025-11-24T10:45:00",
    "model": "claude-sonnet-4-5-20250929",
    "passing_threshold": 70.0
  },
  "summary": {
    "total_questions": 10,
    "questions_passed": 8,
    "questions_failed": 2,
    "pass_rate": 80.0,
    "average_score": 76.5,
    "component_averages": {
      "entity_presence": 85.3,
      "tool_usage": 78.2,
      "structure": 82.1,
      "numerical_accuracy": 71.5,
      "biological_reasoning": 68.9
    }
  },
  "detailed_scores": [
    {
      "question_id": "q1",
      "overall_score": 82.5,
      "passed": true,
      "component_scores": {
        "entity_presence": 90.0,
        "tool_usage": 85.0,
        "structure": 80.0,
        "numerical_accuracy": 75.0,
        "biological_reasoning": 82.0
      },
      "feedback": [
        "✓ Found entities: BCR, ABL1, KIT, PDGFR",
        "✓ Used expected tools: cogex_query_drug_or_effect, cogex_query_pathway",
        "✓ Contains valid Reactome ID",
        "⚠ Limited numerical data"
      ]
    }
  ]
}
```

## Scoring Rubric

Each question is scored on multiple components:

1. **Entity Presence** (15-30%): Key biomedical entities correctly identified
2. **Tool Usage** (10-25%): Appropriate tools invoked in correct order
3. **Structure** (10-20%): Response format and completeness
4. **Numerical Accuracy** (15-30%): Correct counts, p-values, scores, IDs
5. **Biological Reasoning** (10-30%): Quality of interpretation and context

**Overall Score**: Weighted average based on question-specific rubric
**Passing Threshold**: 70/100 (configurable)

### Score Interpretation

- **90-100**: Excellent - Comprehensive, accurate, well-reasoned
- **80-89**: Very Good - Minor issues, mostly complete
- **70-79**: Good - Acceptable with some gaps
- **60-69**: Fair - Significant gaps but shows understanding
- **Below 60**: Poor - Major issues or incomplete

## Expected Performance

### Runtime Estimates

- **Total evaluation time**: 60-90 minutes (all 10 questions)
- **Average per question**: 30-80 seconds (varies by complexity)
- **Total tool calls**: 60-80 across all questions
- **Token usage**: ~70,000 total (input + output)

### Cost Estimates (Claude Sonnet 4.5)

- Input tokens: ~45,000 @ $3/M = $0.135
- Output tokens: ~25,000 @ $15/M = $0.375
- **Total cost**: ~$0.51 per full evaluation run

### Baseline Accuracy

Expected performance with Claude Sonnet 4.5:

- **Pass rate**: 70-90% of questions
- **Average score**: 72-85/100
- **Tool usage accuracy**: 75-90%
- **Entity identification**: 80-95%

## Adding New Questions

1. **Edit `questions.xml`**:

```xml
<question id="q11" category="your-category" difficulty="medium|hard">
  <text>
    Your question text here...
  </text>
  <expected_tools>
    tool1,
    tool2,
    tool3
  </expected_tools>
  <validation_criteria>
    <criterion type="entity_presence">Required entities</criterion>
    <criterion type="numerical_data">Required metrics</criterion>
  </validation_criteria>
  <reference_answer>
    Expected answer content...
  </reference_answer>
  <estimated_tool_calls>5-7</estimated_tool_calls>
  <estimated_time_seconds>40-60</estimated_time_seconds>
</question>
```

2. **Add to `reference_answers.json`**:

```json
"q11": {
  "category": "your-category",
  "key_entities": ["ENTITY1", "ENTITY2"],
  "expected_tools": ["tool1", "tool2"],
  "min_tool_calls": 5,
  "max_tool_calls": 10,
  "validation_patterns": {
    "required_format": "pattern_regex"
  },
  "scoring_rubric": {
    "component1": 25,
    "component2": 25,
    "component3": 30,
    "component4": 20
  },
  "min_answer_length": 200,
  "keywords_required": ["keyword1", "keyword2"],
  "biological_context": "Background information..."
}
```

## Question Design Guidelines

When creating new evaluation questions:

1. **Complexity**: Require 3-10 tool invocations
2. **Independence**: Question should be self-contained
3. **Verifiability**: Have a clear, checkable answer
4. **Realism**: Based on actual research workflows
5. **Stability**: Answer shouldn't change with database updates
6. **Specificity**: Ask for specific entities, IDs, or metrics
7. **Balance**: Mix straightforward and challenging aspects

## Troubleshooting

### "No questions found"

Ensure `questions.xml` is in the current directory or provide full path:

```bash
python runner.py --questions /full/path/to/questions.xml
```

### "ANTHROPIC_API_KEY not set"

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Validation scores seem incorrect

Check that `reference_answers.json` is up-to-date and in sync with `questions.xml`.

### Tool calls failing

Ensure the INDRA CoGEx MCP server is properly configured and accessible. The runner assumes tools are available through the Claude API's MCP integration.

## Best Practices

1. **Run full evaluations regularly** to track performance over time
2. **Save results with timestamps** to compare different runs
3. **Test with different models** to understand model-specific strengths
4. **Review failed questions** to identify tool or prompt improvements
5. **Update reference answers** when biological knowledge changes
6. **Add questions** for new tool combinations or workflows

## Integration with CI/CD

Add to your testing pipeline:

```bash
# .github/workflows/evaluation.yml
- name: Run Evaluation Suite
  run: |
    export ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }}
    cd evaluation
    python runner.py --questions questions.xml --output results/ci_run.json
    python validator.py --results results/ci_run.json --threshold 70
```

## Contributing

When adding new questions or improving validation logic:

1. Test question individually first (`--start-from N --end-at N`)
2. Verify reference answer accuracy
3. Ensure validation criteria are comprehensive
4. Document biological rationale in `biological_context`
5. Update this README with new categories or patterns

## Support

- **Questions**: Open an issue on GitHub
- **Bug reports**: Include evaluation results JSON and validation report
- **Feature requests**: Describe new question types or validation criteria

## Version History

- **1.0.0** (2025-11-24): Initial release with 10 evaluation questions
  - 7 hard difficulty, 3 medium difficulty
  - 8 question categories
  - Comprehensive validation framework
  - Estimated 60-90 minute runtime

---

**Built with precision**: Every question is carefully designed to test real-world biomedical research workflows with rigorous validation criteria.
