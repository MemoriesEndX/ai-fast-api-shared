import time
import os
import pytest
from app.schemas.recommendation import (
    RecommendationRequest,
    UserProfileSchema,
    CandidateItem,
    AssessmentResultItem,
)
from app.services.recommendation_service import RecommendationScoringService, RecommendationEngine


def generate_mock_candidates(count: int) -> list[CandidateItem]:
    categories = ["Safety", "Production", "HR", "IT", "Management", "Finance", "Quality"]
    divisions = ["Production", "Human Resources", "Finance", "IT", "Operations"]
    positions = ["Supervisor", "Operator", "Manager", "Staff", "Director"]

    candidates = []
    for i in range(1, count + 1):
        cat = categories[i % len(categories)]
        div = divisions[i % len(divisions)]
        pos = positions[i % len(positions)]
        cand_type = "playlist" if i % 5 == 0 else "content"

        candidates.append(
            CandidateItem(
                id=i,
                type=cand_type,
                title=f"Learning Module {i} - {cat} Masterclass",
                slug=f"learning-module-{i}",
                description=f"Comprehensive course for {div} division and {pos} role.",
                classification_id=(i % 7) + 1,
                classification_name=cat,
                active="Active",
                has_deadline=(i % 10 == 0),
                to_date="2030-12-31" if (i % 10 == 0) else None,
                target_division=div,
                target_position=pos,
                content_ids=[i * 10 + 1, i * 10 + 2] if cand_type == "playlist" else [],
            )
        )
    return candidates


@pytest.mark.parametrize("candidate_count", [10, 50, 100, 500])
def test_recommendation_scoring_benchmark(candidate_count: int):
    """Benchmark candidate generation, scoring, and ranking performance without LLM network overhead."""
    scoring_service = RecommendationScoringService()

    user = UserProfileSchema(
        id=1,
        name="Performance Test User",
        division="Production",
        position="Supervisor",
        department="Safety",
    )

    candidates = generate_mock_candidates(candidate_count)
    request = RecommendationRequest(
        application="owl",
        user=user,
        completed_content=[2, 4, 6],
        completed_playlists=[5],
        in_progress_content=[{"id": 8, "progress": 50}],
        assessment_results=[AssessmentResultItem(assessment_id=1, title="Safety Exam", score=60.0)],
        candidates=candidates,
        limit=10,
    )

    start_time = time.perf_counter()
    recommendations = scoring_service.generate_recommendations(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    print(f"\n[BENCHMARK] {candidate_count} candidates scored and ranked in {elapsed_ms:.3f} ms. Returned {len(recommendations)} recommendations.")

    assert len(recommendations) <= 10
    # Requirement: Deterministic scoring must be fast (e.g. < 250ms for up to 500 candidates)
    assert elapsed_ms < 250.0, f"Scoring {candidate_count} candidates took too long: {elapsed_ms:.2f} ms"

