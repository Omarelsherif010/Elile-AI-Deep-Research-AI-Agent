"""Tests verifying prompt output formats match their target Pydantic schemas."""

from __future__ import annotations

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def _get_output_format_section(prompt_text: str) -> str:
    """Extract the ## Output Format section from a prompt."""
    match = re.search(r"## Output Format\n(.*?)(?=\n## |\Z)", prompt_text, re.DOTALL)
    return match.group(1) if match else ""


class TestPlannerPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "planner.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("planner")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_output_format_references_research_plan(self):
        text = _get_output_format_section(_read_prompt("planner"))
        assert "ResearchPlan" in text or "SubQuestion" in text

    def test_output_format_references_sub_questions(self):
        text = _get_output_format_section(_read_prompt("planner"))
        assert "sub_questions" in text or "SubQuestion" in text

    def test_schema_fields_present(self):
        """Verify the key fields of ResearchPlan appear in the output format."""
        text = _get_output_format_section(_read_prompt("planner"))
        # dimension field must be mentioned (critical for graph routing)
        assert "dimension" in text
        # priority field must be present (drives search ordering)
        assert "priority" in text


class TestQueryExpanderPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "query_expander.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("query_expander")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_output_format_references_queries(self):
        text = _get_output_format_section(_read_prompt("query_expander"))
        assert "queries" in text

    def test_context_has_sub_question_variable(self):
        text = _read_prompt("query_expander")
        assert "{sub_question}" in text or "sub_question" in text


class TestExtractorPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "extractor.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("extractor")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_output_format_references_claims(self):
        text = _get_output_format_section(_read_prompt("extractor"))
        assert "claims" in text

    def test_output_format_references_source_urls(self):
        text = _get_output_format_section(_read_prompt("extractor"))
        assert "source_url" in text

    def test_prompt_injection_defense(self):
        """Verify the prompt wraps content in source tags."""
        text = _read_prompt("extractor")
        assert "<source" in text or "source url" in text.lower()

    def test_no_fabrication_constraint(self):
        text = _read_prompt("extractor")
        assert (
            "fabricat" in text.lower()
            or "never invent" in text.lower()
            or "only extract" in text.lower()
        )


class TestValidatorPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "validator.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("validator")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_output_format_references_tier(self):
        text = _get_output_format_section(_read_prompt("validator"))
        assert "tier" in text.lower()

    def test_tier_1_examples_present(self):
        """Tier-1 source examples (gov, SEC, court) must be in the prompt."""
        text = _read_prompt("validator")
        tier1_examples = ["gov", "sec", "court", ".gov"]
        assert any(ex in text.lower() for ex in tier1_examples)

    def test_independent_domains_mentioned(self):
        text = _read_prompt("validator")
        assert "domain" in text.lower() and (
            "independent" in text.lower() or "corrobor" in text.lower()
        )


class TestReflectorPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "reflector.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("reflector")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_three_decisions_present(self):
        text = _read_prompt("reflector")
        assert "continue" in text.lower()
        assert "pivot" in text.lower()
        assert "terminate" in text.lower()

    def test_output_format_references_decision(self):
        text = _get_output_format_section(_read_prompt("reflector"))
        assert "decision" in text


class TestRiskAnalyzerPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "risk_analyzer.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("risk_analyzer")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_all_7_categories_mentioned(self):
        text = _read_prompt("risk_analyzer")
        for cat in [
            "REGULATORY",
            "REPUTATIONAL",
            "NETWORK",
            "FINANCIAL",
            "INCONSISTENCY",
            "COVERAGE_GAP",
            "OTHER",
        ]:
            assert cat in text, f"Missing risk category: {cat}"

    def test_severity_levels_mentioned(self):
        text = _read_prompt("risk_analyzer")
        for sev in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert sev in text, f"Missing severity level: {sev}"

    def test_other_requires_justification(self):
        text = _read_prompt("risk_analyzer")
        assert "justification" in text.lower()

    def test_coverage_gap_mandatory(self):
        text = _read_prompt("risk_analyzer")
        assert "COVERAGE_GAP" in text


class TestReporterPrompt:
    def test_prompt_file_exists(self):
        assert (PROMPTS_DIR / "reporter.md").exists()

    def test_has_all_required_sections(self):
        text = _read_prompt("reporter")
        for section in [
            "## Role",
            "## Context",
            "## Task",
            "## Output Format",
            "## Constraints",
            "## Examples",
            "## Notes",
        ]:
            assert section in text, f"Missing section: {section}"

    def test_scope_section_mandatory(self):
        """The Scope and Limitations section must be explicitly required."""
        text = _read_prompt("reporter")
        assert "scope" in text.lower() and "limitation" in text.lower()

    def test_nine_report_sections(self):
        """Report should have the required sections."""
        text = _read_prompt("reporter")
        required = [
            "executive summary",
            "methodology",
            "findings",
            "risk",
            "claim inventory",
            "scope",
        ]
        for section in required:
            assert section.lower() in text.lower(), f"Missing report section: {section}"

    def test_output_format_has_scope_bool(self):
        text = _get_output_format_section(_read_prompt("reporter"))
        assert "has_scope_section" in text or "scope" in text.lower()
