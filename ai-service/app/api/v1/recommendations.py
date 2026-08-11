from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationEngine

router = APIRouter(tags=["OWL Recommendation Engine"])


def get_recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine()


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Generate personalized OWL LMS learning recommendations",
    description="Deterministically ranks candidate contents and playlists based on user division, position, learning gap, assessment scores, and provides optional Qwen natural language explanation.",
)
async def get_recommendations(
    request: RecommendationRequest,
    engine: RecommendationEngine = Depends(get_recommendation_engine),
):
    # Requirement 19: Application Tenant Isolation
    if request.application.strip().lower() != "owl":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_APPLICATION",
                "message": f"Recommendation engine is currently only supported for application 'owl', got '{request.application}'."
            }
        )

    return await engine.get_recommendations(request)
