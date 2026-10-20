"""tests/test_opportunity_matcher.py
----------------------------------
Unit tests for the Semantic Opportunity Matcher and Colab Evaluator.
"""

from pathlib import Path
import pytest

from tools.evaluate_opportunity_fit import (
    SemanticOpportunityMatcher,
    MatchEvaluation,
    PROFILE_COMPETENCY_VECTORS,
)
from tools.eval_opportunities_colab import ColabOpportunityEvaluator


def test_matcher_profile_vectors_structure():
    """Ensure all 4 empirical pillars are configured with keywords and weights."""
    assert "SPARK" in PROFILE_COMPETENCY_VECTORS
    assert "BiasAperture" in PROFILE_COMPETENCY_VECTORS
    assert "Fleet_Orchestrator" in PROFILE_COMPETENCY_VECTORS
    assert "Brainstorm_Formal_Logic" in PROFILE_COMPETENCY_VECTORS

    total_weight = sum(p["weight"] for p in PROFILE_COMPETENCY_VECTORS.values())
    assert abs(total_weight - 1.0) < 1e-4


def test_matcher_evaluate_catalog():
    """Ensure catalog evaluation ranks top matches and returns valid evaluations."""
    matcher = SemanticOpportunityMatcher()
    evaluations = matcher.evaluate_catalog(top_k=5)
    assert len(evaluations) > 0
    for e in evaluations:
        assert isinstance(e, MatchEvaluation)
        assert 0.0 <= e.overall_fit_ratio <= 1.0
        assert 0.0 <= e.visa_feasibility_score <= 1.0
        assert e.net_alpha_index_kusd > 0
        assert e.visa_pathway in ("UAE_GOLDEN_VISA", "UN_G4_DIPLOMATIC", "EMPLOYER_SPONSORED")
        assert len(e.gap_closure_actions) > 0


def test_matcher_edge_ai_opportunity_ranking():
    """Verifies that an edge AI posting (like SPARK) yields high SPARK pillar overlap."""
    matcher = SemanticOpportunityMatcher()
    sample_opp = {
        "id": "TEST-EDGE-01",
        "title": "Staff TinyML & Embedded Edge AI Systems Architect",
        "organization": "Test Robotics",
        "category": "SOVEREIGN_GCC",
        "location": "Dubai",
        "compensation_est": "$200,000 USD",
        "tax_status": "TAX_FREE",
        "visa_pathway": "UAE_GOLDEN_VISA",
        "relevance_tags": ["tinyml", "esp32", "freertos", "kinematics", "wearables"],
        "description": "Develop low-power INT8 neural networks and fall detection wearables on ESP32-S3.",
        "url": "https://example.com"
    }
    score, breakdown = matcher.compute_fit_score(sample_opp)
    assert breakdown["SPARK"] >= 0.80
    assert score >= 0.70


def test_colab_evaluator_dry_run():
    """Verifies that the Colab evaluator dry-run executes cleanly with 0 CU billed."""
    evaluator = ColabOpportunityEvaluator(dry_run=True)
    report = evaluator.run_evaluation()
    assert report["status"] == "SUCCESS"
    assert report["cost_units_billed"] == 0.0
    assert "Simulated" in report["accelerator"]
