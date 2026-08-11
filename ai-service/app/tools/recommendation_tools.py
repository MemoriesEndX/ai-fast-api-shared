import logging
from typing import Dict, Any, Optional
from app.mcp.registry import register_tool
from app.integrations.lms_client import LMSClientService
from app.services.recommendation_service import recommendation_engine
from app.schemas.recommendation import (
    RecommendationRequest,
    UserProfileSchema,
    CandidateItem,
    AssessmentResultItem,
)
from app.tools.auth import UserAuthContext

logger = logging.getLogger("ai_service.tools.recommendation")
lms_client = LMSClientService()


@register_tool(
    name="get_learning_recommendations",
    description="Generate personalized LMS learning recommendations for user using deterministic scoring engine.",
    input_schema={"user_id": "integer", "limit": "integer (default 5)"},
    output_schema={"user_id": "integer", "recommendations": "array", "explanation": "string"},
    requires_auth=True,
)
async def get_learning_recommendations(user_id: int, limit: int = 5, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #8: Call Phase 6 Recommendation Engine."""
    uid = auth_context.user_id if auth_context else user_id
    safe_limit = min(max(1, limit), 20)

    # 1. Fetch user data from LMS Client
    profile_raw = await lms_client.get_user_profile(uid)
    progress_raw = await lms_client.get_learning_progress(uid)
    assessments_raw = await lms_client.get_user_assessments(uid)
    content_catalog = await lms_client.search_content(query="", limit=20)
    playlist_catalog = await lms_client.search_playlist(query="", limit=10)

    # 2. Extract completed items
    progress_items = progress_raw.get("items", [])
    completed_content = [item["content_id"] for item in progress_items if item.get("finish") == 1 or item.get("progress") == 100]
    in_progress = [{"id": item["content_id"], "progress": item.get("progress", 0)} for item in progress_items if item.get("finish") != 1 and item.get("progress", 0) < 100]

    # 3. Assemble candidates
    app_tenant = auth_context.application if auth_context else "owl"
    candidates = []
    for c in content_catalog.get("items", []):
        candidates.append(
            CandidateItem(
                id=c["id"],
                type="content",
                title=c["title"],
                classification_name=c.get("classification_name"),
                active=c.get("active", "Active"),
                application=app_tenant,
            )
        )
    for p in playlist_catalog.get("items", []):
        candidates.append(
            CandidateItem(
                id=p["id"],
                type="playlist",
                title=p["title"],
                classification_name=p.get("classification_name"),
                active=p.get("active", "Active"),
                application=app_tenant,
            )
        )


    # 4. Construct RecommendationRequest
    user_schema = UserProfileSchema(
        id=profile_raw.get("user_id", uid),
        name=profile_raw.get("name", "User"),
        division=profile_raw.get("division"),
        position=profile_raw.get("position"),
        department=profile_raw.get("department"),
        team=profile_raw.get("team"),
        role=profile_raw.get("role"),
    )

    assessment_items = [
        AssessmentResultItem(
            assessment_id=a.get("assessment_id", 0),
            content_id=a.get("content_id"),
            title=a.get("title"),
            score=float(a.get("score", 100.0)),
        )
        for a in assessments_raw.get("items", [])
    ]

    request = RecommendationRequest(
        application=auth_context.application if auth_context else "owl",
        user=user_schema,
        completed_content=completed_content,
        completed_playlists=[],
        in_progress_content=in_progress,
        assessment_results=assessment_items,
        candidates=candidates,
        limit=safe_limit,
    )

    # 5. Delegate to RecommendationEngine
    response = await recommendation_engine.recommend(request)
    return response.model_dump()
