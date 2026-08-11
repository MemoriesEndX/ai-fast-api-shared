from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationEngine
from app.core.security import verify_api_key, validate_tenant_auth
from app.core.rate_limit import check_search_rate_limit

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
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_search_rate_limit),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
):
    app_str = str(request.application.value if hasattr(request.application, 'value') else request.application)
    
    # 1. Tenant Authorization Check
    validate_tenant_auth(client_app, app_str)

    # 2. Application Support Check
    if app_str.strip().lower() != "owl":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_APPLICATION",
                "message": f"Recommendation engine is currently only supported for application 'owl', got '{app_str}'."
            }
        )

    return await engine.get_recommendations(request)
