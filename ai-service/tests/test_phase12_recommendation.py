import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.recommendation import (
    RecommendationRequest,
    UserProfileSchema,
    CandidateItem,
    AssessmentResultItem,
)
from app.services.recommendation_service import RecommendationEngine, RecommendationScoringService

client = TestClient(app)

OWL_HEADERS = {"Authorization": "Bearer owl-secret-api-key"}
HR_HEADERS = {"Authorization": "Bearer hr-corner-secret-api-key"}


def test_cold_start_recommendation():
    """Verify new user without history gets fallback recommendations based on division/role."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=999, name="New User", division="IT", role="Backend Developer"),
        learning_history=[],
        completed_content=[],
        completed_playlists=[],
        in_progress_content=[],
        assessment_results=[],
        candidates=[
            CandidateItem(id=1, type="content", title="Laravel REST API", target_division="IT", target_role="Backend Developer", application="owl"),
            CandidateItem(id=2, type="content", title="Basic Finance 101", target_division="Finance", target_role="Accountant", application="owl"),
        ],
        limit=5,
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert len(recs) == 2
    assert recs[0].id == 1
    assert recs[0].raw_score > recs[1].raw_score
    assert any("division" in r.lower() for r in recs[0].reasons)


def test_division_matching_signal():
    """Verify division match yields higher score than non-division match."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=101, division="Engineering"),
        candidates=[
            CandidateItem(id=10, type="content", title="Engineering Safety", target_division="Engineering", application="owl"),
            CandidateItem(id=20, type="content", title="Marketing Basics", target_division="Marketing", application="owl"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert recs[0].id == 10
    assert recs[0].score_breakdown.division > recs[1].score_breakdown.division


def test_remedial_assessment_gap_signal():
    """Verify user with low assessment score receives remedial content tagged as SKILL_GAP."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=102, division="IT"),
        assessment_results=[AssessmentResultItem(assessment_id=1, title="API Security", score=45.0)],
        candidates=[
            CandidateItem(id=30, type="content", title="API Security Fundamentals", classification_name="API Security", application="owl"),
            CandidateItem(id=40, type="content", title="General Accounting", classification_name="Finance", application="owl"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert recs[0].id == 30
    assert recs[0].category == "SKILL_GAP"
    assert any("remedial" in r.lower() for r in recs[0].reasons)


def test_ongoing_learning_continuation():
    """Verify in-progress course (45%) is prioritized as CONTINUE_LEARNING."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=103, division="IT"),
        in_progress_content=[{"id": 50, "progress": 45, "finish": 0}],
        candidates=[
            CandidateItem(id=50, type="content", title="Docker Advanced Containerization", application="owl"),
            CandidateItem(id=60, type="content", title="New Vue.js Guide", application="owl"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert recs[0].id == 50
    assert recs[0].is_continuation is True
    assert recs[0].category == "CONTINUE_LEARNING"


def test_completed_content_exclusion():
    """Verify completed content ID is strictly excluded from candidate list."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=104, division="IT"),
        completed_content=[70],
        candidates=[
            CandidateItem(id=70, type="content", title="Completed Course", application="owl"),
            CandidateItem(id=80, type="content", title="Available Course", application="owl"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert len(recs) == 1
    assert recs[0].id == 80


def test_tenant_isolation_recommendation():
    """Verify HR Corner content candidate is excluded for OWL tenant request."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=105, division="IT"),
        candidates=[
            CandidateItem(id=1, type="content", title="OWL Course", application="owl"),
            CandidateItem(id=2, type="content", title="HR Secret Course", application="hr-corner"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert len(recs) == 1
    assert recs[0].id == 1


def test_contextual_query_recommendation():
    """Verify query context boosts semantic score for matching candidates."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=106, division="IT"),
        query="Laravel",
        candidates=[
            CandidateItem(id=90, type="content", title="Building REST API with Laravel", application="owl"),
            CandidateItem(id=91, type="content", title="Python Data Science", application="owl"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert recs[0].id == 90
    assert any("laravel" in r.lower() for r in recs[0].reasons)


def test_duplicate_candidate_deduplication():
    """Verify duplicate candidate ID returns single recommendation item."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=107, division="IT"),
        candidates=[
            CandidateItem(id=100, type="content", title="Duplicate Course", application="owl"),
            CandidateItem(id=100, type="content", title="Duplicate Course", application="owl"),
        ],
    )
    scoring_service = RecommendationScoringService()
    recs = scoring_service.generate_recommendations(request)
    assert len(recs) == 1


@pytest.mark.asyncio
async def test_qwen_failure_graceful_fallback():
    """Verify engine returns structured recommendations when Qwen explanation raises an Exception."""
    request = RecommendationRequest(
        application="owl",
        user=UserProfileSchema(id=108, division="IT"),
        candidates=[CandidateItem(id=200, type="content", title="Resilient Course", application="owl")],
    )
    mock_llm = AsyncMock()
    mock_llm.generate_explanation.side_effect = Exception("llama-server connection timeout")

    engine = RecommendationEngine(llm_service=mock_llm)
    response = await engine.get_recommendations(request)

    assert len(response.recommendations) == 1
    assert response.explanation is None
    assert response.explanation_status == "unavailable"


def test_recommendation_api_endpoint():
    """Verify POST /api/v1/recommendations endpoint returns 200 with recommendation payload."""
    payload = {
        "application": "owl",
        "user": {"id": 109, "name": "API User", "division": "IT", "role": "Developer"},
        "candidates": [
            {"id": 300, "type": "content", "title": "API Test Course", "active": "Active", "application": "owl"}
        ],
        "limit": 5,
    }
    response = client.post("/api/v1/recommendations", headers=OWL_HEADERS, json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["application"] == "owl"
    assert res["user_id"] == 109
    assert len(res["recommendations"]) == 1
    assert res["recommendations"][0]["id"] == 300


def test_chat_recommendation_intent_routing():
    """Verify POST /api/v1/chat message 'Rekomendasikan pembelajaran untuk saya' routes to RECOMMENDATION."""
    payload = {
        "application": "owl",
        "user_id": 110,
        "message": "Rekomendasikan pembelajaran yang cocok untuk saya",
    }
    response = client.post("/api/v1/chat", headers=OWL_HEADERS, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert isinstance(data["message"], str)
