from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationEngine
from app.core.security import verify_api_key, validate_tenant_auth
from app.core.rate_limit import check_search_rate_limit

router = APIRouter(tags=["Recommendation Engine 2.0"])


def get_recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine()


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Generate personalized learning recommendations (2.0)",
    description="Deterministically ranks candidate contents and playlists based on user division, role, semantic relevance, classification, assessment skill gap, and ongoing progress with optional grounded Qwen explanation.",
)
async def get_recommendations(
    request_data: RecommendationRequest,
    raw_request: Request,
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_search_rate_limit),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
):
    app_str = str(request_data.application.value if hasattr(request_data.application, 'value') else request_data.application).strip().lower()

    # 1. Tenant Authorization Check
    validate_tenant_auth(client_app, app_str)

    # 2. Application Support Check (owl, hr-corner)
    if app_str not in ("owl", "hr-corner"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_APPLICATION",
                "message": f"Recommendation engine is currently supported for 'owl' and 'hr-corner', got '{app_str}'."
            }
        )

    res = await engine.get_recommendations(request_data)
    req_id = getattr(raw_request.state, "request_id", None)
    if req_id:
        res.request_id = req_id
    return res


@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Fetch recommendations via GET query",
    description="Convenience GET endpoint fetching recommendations for authenticated user context.",
)
async def get_recommendations_query(
    raw_request: Request,
    application: str = Query(..., description="Application tenant (owl, hr-corner)"),
    user_id: int = Query(..., description="User ID"),
    limit: int = Query(5, ge=1, le=50, description="Recommendation limit"),
    query: Optional[str] = Query(None, description="Optional contextual query"),
    type_filter: Optional[str] = Query(None, description="Optional type filter (content, playlist, video, document)"),
    category_filter: Optional[str] = Query(None, description="Optional category filter"),
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_search_rate_limit),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
):
    app_str = application.strip().lower()
    validate_tenant_auth(client_app, app_str)

    if app_str not in ("owl", "hr-corner"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_APPLICATION", "message": f"Unsupported application '{app_str}'."}
        )

    # Delegate to recommendation tool / LMS client if candidates list is empty
    from app.tools.recommendation_tools import get_learning_recommendations
    res_dict = await get_learning_recommendations(user_id=user_id, limit=limit)
    res_obj = RecommendationResponse(**res_dict)

    req_id = getattr(raw_request.state, "request_id", None)
    if req_id:
        res_obj.request_id = req_id
    return res_obj
