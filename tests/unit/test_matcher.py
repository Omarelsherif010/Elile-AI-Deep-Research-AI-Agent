"""Unit tests for eval/matcher.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from eval.matcher import (
    cosine_similarity,
    exact_match,
    fuzzy_match,
    match_facts,
    match_risks,
    semantic_match,
)
from eval.schemas import (
    MatchStrategy,
    PersonaDefinition,
    PersonaType,
    PlantedFact,
    PlantedRisk,
    ResearchDimension,
    Tier,
)

from research_agent.schemas import RiskCategory, RiskFlag, RiskSeverity, ValidatedClaim


class TestExactMatch:
    def test_exact_equal(self) -> None:
        assert exact_match("Founded Vellinor Capital", "Founded Vellinor Capital") == 1.0

    def test_exact_normalized(self) -> None:
        assert exact_match("Founded Vellinor Capital!", "founded vellinor capital") == 1.0

    def test_exact_not_equal(self) -> None:
        assert exact_match("Founded Vellinor Capital", "Founded Other Capital") == 0.0


class TestFuzzyMatch:
    def test_fuzzy_high_score(self) -> None:
        score = fuzzy_match(
            "Aria Vellinor founded Vellinor Capital in 2019",
            "Founded Vellinor Capital in 2019",
        )
        assert score >= 80.0

    def test_fuzzy_low_score(self) -> None:
        score = fuzzy_match(
            "Completely unrelated text",
            "Founded Vellinor Capital",
        )
        assert score < 60.0


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == 1.0

    def test_orthogonal_vectors(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestSemanticMatch:
    def test_semantic_match(self) -> None:
        embedder = MagicMock()
        embedder.embed = MagicMock(side_effect=lambda text: {
            "hello world": [1.0, 0.0],
            "hello there": [0.9, 0.1],
        }.get(text, [0.0, 0.0]))

        score = semantic_match("hello world", "hello there", embedder)
        assert 0.0 < score <= 1.0


class TestMatchFacts:
    def _make_persona(self) -> PersonaDefinition:
        return PersonaDefinition(
            id="persona_test",
            target_name="Test Person",
            target_context="Test",
            persona_type=PersonaType.synthetic,
            description="Test",
            ethical_notes="Test",
            plant_site_root="eval/plant_site/test",
            planted_facts=[
                PlantedFact(
                    id="fact_t01",
                    statement="Founded TestCo in 2019",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.professional_history,
                    fact_type="role",
                    match_strategy=MatchStrategy.exact,
                    match_threshold=100.0,
                    notes="test",
                    source_urls=["https://example.com"],
                ),
                PlantedFact(
                    id="fact_t02",
                    statement="Advisory board member at AI Institute",
                    difficulty=Tier.medium,
                    expected_dimension=ResearchDimension.network,
                    fact_type="network",
                    match_strategy=MatchStrategy.fuzzy,
                    match_threshold=80.0,
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
        )

    def test_exact_match_found(self) -> None:
        persona = self._make_persona()
        # Claim text will be " founded testco in 2019" — wait, empty subject + predicate + object?
        # Let's make subject empty so claim text is exactly the fact statement.
        claims = [
            ValidatedClaim(
                subject="",
                predicate="Founded",
                object="TestCo in 2019",
                source_urls=["https://example.com"],
                extraction_confidence=0.9,
                confidence=0.85,
            ),
        ]
        matches = match_facts(persona, claims)
        assert len(matches) == 2
        assert matches[0].planted_fact_id == "fact_t01"
        assert matches[0].matched_claim_id is not None
        assert matches[0].match_score == 1.0

    def test_no_match(self) -> None:
        persona = self._make_persona()
        claims = [
            ValidatedClaim(
                subject="Test Person",
                predicate="did something else",
                object="entirely",
                source_urls=["https://example.com"],
                extraction_confidence=0.5,
                confidence=0.5,
            ),
        ]
        matches = match_facts(persona, claims)
        assert matches[0].matched_claim_id is None
        assert matches[0].match_score == 0.0

    def test_fuzzy_match_found(self) -> None:
        persona = self._make_persona()
        claims = [
            ValidatedClaim(
                subject="Test Person",
                predicate="is advisory board member at",
                object="AI Institute",
                source_urls=["https://example.com"],
                extraction_confidence=0.8,
                confidence=0.75,
            ),
        ]
        matches = match_facts(persona, claims)
        assert len(matches) == 2
        assert matches[1].planted_fact_id == "fact_t02"
        assert matches[1].matched_claim_id is not None
        assert matches[1].match_score >= 80.0

    def test_semantic_match_with_embedder(self) -> None:
        persona = PersonaDefinition(
            id="persona_test",
            target_name="Test Person",
            target_context="Test",
            persona_type=PersonaType.synthetic,
            description="Test",
            ethical_notes="Test",
            plant_site_root="eval/plant_site/test",
            planted_facts=[
                PlantedFact(
                    id="fact_t03",
                    statement="Advocated for transparent AI governance",
                    difficulty=Tier.hard,
                    expected_dimension=ResearchDimension.public_statements,
                    fact_type="statement",
                    match_strategy=MatchStrategy.semantic,
                    match_threshold=0.75,
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
        )
        claims = [
            ValidatedClaim(
                subject="Test Person",
                predicate="publicly supported",
                object="open and transparent AI governance frameworks",
                source_urls=["https://example.com"],
                extraction_confidence=0.8,
                confidence=0.8,
            ),
        ]
        embedder = MagicMock()
        embedder.embed = MagicMock(return_value=[0.5, 0.5])
        matches = match_facts(persona, claims, embedder)
        assert matches[0].planted_fact_id == "fact_t03"
        assert matches[0].match_strategy_used == MatchStrategy.semantic

    def test_semantic_without_embedder_falls_back_to_fuzzy(self) -> None:
        persona = PersonaDefinition(
            id="persona_test",
            target_name="Test Person",
            target_context="Test",
            persona_type=PersonaType.synthetic,
            description="Test",
            ethical_notes="Test",
            plant_site_root="eval/plant_site/test",
            planted_facts=[
                PlantedFact(
                    id="fact_t03",
                    statement="Advocated for transparent AI governance",
                    difficulty=Tier.hard,
                    expected_dimension=ResearchDimension.public_statements,
                    fact_type="statement",
                    match_strategy=MatchStrategy.semantic,
                    match_threshold=0.75,
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
        )
        claims = [
            ValidatedClaim(
                subject="Test Person",
                predicate="advocated for",
                object="transparent AI governance",
                source_urls=["https://example.com"],
                extraction_confidence=0.8,
                confidence=0.8,
            ),
        ]
        matches = match_facts(persona, claims)
        assert len(matches) == 1
        assert matches[0].match_strategy_used == MatchStrategy.fuzzy


class TestMatchRisks:
    def test_category_match(self) -> None:
        persona = PersonaDefinition(
            id="persona_test",
            target_name="Test Person",
            target_context="Test",
            persona_type=PersonaType.synthetic,
            description="Test",
            ethical_notes="Test",
            plant_site_root="eval/plant_site/test",
            planted_facts=[
                PlantedFact(
                    id="fact_t01",
                    statement="Test fact",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.biographical,
                    fact_type="biographical",
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
            planted_risks=[
                PlantedRisk(
                    id="risk_t01",
                    risk_category=RiskCategory.REGULATORY,
                    expected_severity=RiskSeverity.MEDIUM,
                    description="Preliminary inquiry by regulator",
                    evidence_source_urls=["https://example.com"],
                ),
            ],
        )
        flags = [
            RiskFlag(
                type=RiskCategory.REGULATORY,
                severity=RiskSeverity.MEDIUM,
                description="Preliminary inquiry opened by regulator",
                evidence_claim_ids=[],
                confidence=0.8,
            ),
        ]
        matches = match_risks(persona, flags)
        assert len(matches) == 1
        assert matches[0].planted_risk_id == "risk_t01"
        assert matches[0].matched_flag_index == 0
        assert matches[0].severity_match is True

    def test_no_match_wrong_category(self) -> None:
        persona = PersonaDefinition(
            id="persona_test",
            target_name="Test Person",
            target_context="Test",
            persona_type=PersonaType.synthetic,
            description="Test",
            ethical_notes="Test",
            plant_site_root="eval/plant_site/test",
            planted_facts=[
                PlantedFact(
                    id="fact_t01",
                    statement="Test fact",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.biographical,
                    fact_type="biographical",
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
            planted_risks=[
                PlantedRisk(
                    id="risk_t01",
                    risk_category=RiskCategory.REGULATORY,
                    expected_severity=RiskSeverity.MEDIUM,
                    description="Preliminary inquiry",
                    evidence_source_urls=["https://example.com"],
                ),
            ],
        )
        flags = [
            RiskFlag(
                type=RiskCategory.NETWORK,
                severity=RiskSeverity.MEDIUM,
                description="Preliminary inquiry",
                evidence_claim_ids=[],
                confidence=0.8,
            ),
        ]
        matches = match_risks(persona, flags)
        assert matches[0].matched_flag_index is None

    def test_no_flags(self) -> None:
        persona = PersonaDefinition(
            id="persona_test",
            target_name="Test Person",
            target_context="Test",
            persona_type=PersonaType.synthetic,
            description="Test",
            ethical_notes="Test",
            plant_site_root="eval/plant_site/test",
            planted_facts=[
                PlantedFact(
                    id="fact_t01",
                    statement="Test fact",
                    difficulty=Tier.easy,
                    expected_dimension=ResearchDimension.biographical,
                    fact_type="biographical",
                    notes="test",
                    source_urls=["https://example.com"],
                ),
            ],
            planted_risks=[
                PlantedRisk(
                    id="risk_t01",
                    risk_category=RiskCategory.REGULATORY,
                    expected_severity=RiskSeverity.MEDIUM,
                    description="Preliminary inquiry",
                    evidence_source_urls=["https://example.com"],
                ),
            ],
        )
        matches = match_risks(persona, [])
        assert matches[0].matched_flag_index is None
