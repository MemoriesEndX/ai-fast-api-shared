import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer owl-secret-api-key"}


@pytest.fixture
def base_user():
    return {
        "id": 123,
        "name": "Budi Santoso",
        "division": "Production",
        "position": "Supervisor",
        "department": "Safety",
    }


@pytest.fixture
def sample_candidates():
    return [
        {
            "id": 101,
            "type": "content",
            "title": "Basic Safety Induction",
            "classification_name": "Safety",
            "target_division": "Production",
            "target_position": "Operator",
            "active": "Active",
            "has_deadline": False,
        },
        {
            "id": 102,
            "type": "content",
            "title": "Advanced Safety Management",
            "description": "Safety management for production supervisors",
            "classification_name": "Safety",
            "target_division": "Production",
            "target_position": "Supervisor",
            "active": "Active",
            "has_deadline": False,
        },
        {
            "id": 103,
            "type": "playlist",
            "title": "Production Safety Leadership Playlist",
            "classification_name": "Safety",
            "target_division": "Production",
            "target_position": "Supervisor",
            "active": "Active",
            "has_deadline": False,
            "content_ids": [201, 202],
        },
        {
            "id": 104,
            "type": "content",
            "title": "HR Payroll System Overview",
            "classification_name": "HR",
            "target_division": "Human Resources",
            "target_position": "Staff",
            "active": "Active",
            "has_deadline": False,
        },
        {
            "id": 105,
            "type": "content",
            "title": "Old Archived Safety Code",
            "classification_name": "Safety",
            "target_division": "Production",
            "active": "Inactive",
            "has_deadline": False,
        },
    ]


def test_recommendation_user_no_history(base_user, sample_candidates):
    """Test recommendation generation for a user with no prior learning history."""
    payload = {
        "application": "owl",
        "user": base_user,
        "learning_history": [],
        "completed_content": [],
        "completed_playlists": [],
        "candidates": sample_candidates,
        "limit": 5,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert data["user_id"] == 123
    assert len(data["recommendations"]) > 0

    top = data["recommendations"][0]
    assert top["id"] in [102, 103]  # Advanced Safety Management or Safety Playlist (Production + Supervisor match)
    assert top["score"] > 50
    assert "score_breakdown" in top
    assert top["score_breakdown"]["division"] == 30.0
    assert top["score_breakdown"]["position"] == 25.0


def test_recommendation_completed_content_exclusion(base_user, sample_candidates):
    """Test that completed candidate contents are excluded from recommendations."""
    payload = {
        "application": "owl",
        "user": base_user,
        "completed_content": [102],  # User already completed ID 102
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    rec_ids = [r["id"] for r in data["recommendations"]]
    assert 102 not in rec_ids


def test_recommendation_inactive_content_exclusion(base_user, sample_candidates):
    """Test that inactive contents are strictly excluded."""
    payload = {
        "application": "owl",
        "user": base_user,
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    rec_ids = [r["id"] for r in data["recommendations"]]
    assert 105 not in rec_ids  # Candidate 105 is Inactive


def test_recommendation_in_progress_content(base_user, sample_candidates):
    """Test in-progress content behavior (not finished yet)."""
    payload = {
        "application": "owl",
        "user": base_user,
        "in_progress_content": [{"id": 101, "progress": 40, "finish": 0}],
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    # 101 should still be included since finish=0 and progress<100
    rec_ids = [r["id"] for r in data["recommendations"]]
    assert 101 in rec_ids


def test_recommendation_low_assessment_score_signal(base_user, sample_candidates):
    """Test low assessment score triggers reinforcement learning score boost."""
    payload = {
        "application": "owl",
        "user": base_user,
        "assessment_results": [
            {"assessment_id": 1, "title": "Safety Basics Exam", "score": 55.0}
        ],
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    rec_102 = next(r for r in data["recommendations"] if r["id"] == 102)
    assert rec_102["score_breakdown"]["assessment"] == 15.0
    assert any("assessment" in reason.lower() for reason in rec_102["reasons"])


def test_recommendation_division_and_position_relevance(base_user, sample_candidates):
    """Test division and position matching logic."""
    payload = {
        "application": "owl",
        "user": {
            "id": 999,
            "division": "Human Resources",
            "position": "Staff",
        },
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    top = data["recommendations"][0]
    assert top["id"] == 104  # HR Payroll System Overview
    assert top["score_breakdown"]["division"] == 30.0
    assert top["score_breakdown"]["position"] == 25.0


def test_recommendation_playlist_candidate(base_user, sample_candidates):
    """Test playlist recommendation candidate handling."""
    payload = {
        "application": "owl",
        "user": base_user,
        "type_filter": "playlist",
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert all(r["type"] == "playlist" for r in data["recommendations"])
    assert data["recommendations"][0]["id"] == 103


def test_recommendation_tenant_isolation(base_user, sample_candidates):
    """Test rejection of non-owl applications (e.g., hr-corner)."""
    payload = {
        "application": "hr-corner",
        "user": base_user,
        "candidates": sample_candidates,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code in (400, 403)
    data = response.json()
    assert "TENANT_ACCESS_DENIED" in str(data)


def test_recommendation_limit_parameter(base_user, sample_candidates):
    """Test limit parameter enforcement."""
    payload = {
        "application": "owl",
        "user": base_user,
        "candidates": sample_candidates,
        "limit": 2,
    }
    response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data["recommendations"]) <= 2


@pytest.mark.asyncio
async def test_recommendation_qwen_failure_resilience(base_user, sample_candidates):
    """Test recommendation engine survives when Qwen / LLM server fails."""
    payload = {
        "application": "owl",
        "user": base_user,
        "candidates": sample_candidates,
    }

    with patch(
        "app.services.llm_service.LlamaCppLLMService.generate_explanation",
        new=AsyncMock(side_effect=Exception("llama-server connection timeout")),
    ):
        response = client.post("/api/v1/recommendations", json=payload, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommendations"]) > 0
        assert data["explanation"] is None
        assert data["explanation_status"] == "unavailable"
