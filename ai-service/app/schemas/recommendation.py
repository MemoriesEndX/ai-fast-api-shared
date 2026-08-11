from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class UserProfileSchema(BaseModel):
    id: int
    name: Optional[str] = None
    division: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None


class AssessmentResultItem(BaseModel):
    assessment_id: Optional[int] = None
    content_id: Optional[int] = None
    title: Optional[str] = None
    score: float = 0.0


class InProgressContentItem(BaseModel):
    id: Optional[int] = None
    content_id: Optional[int] = None
    title: Optional[str] = None
    progress: int = 0
    finish: int = 0


class CompletedContentItem(BaseModel):
    id: Optional[int] = None
    content_id: Optional[int] = None
    title: Optional[str] = None
    classification_name: Optional[str] = None


class CandidateItem(BaseModel):
    id: int
    type: str = "content"  # "content" or "playlist"
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    classification_id: Optional[int] = None
    classification_name: Optional[str] = None
    active: str = "Active"
    has_deadline: bool = False
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    target_division: Optional[str] = None
    target_position: Optional[str] = None
    content_ids: List[int] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    application: str = "owl"
    user: UserProfileSchema
    learning_history: List[Dict[str, Any]] = Field(default_factory=list)
    completed_content: List[Union[int, Dict[str, Any]]] = Field(default_factory=list)
    completed_playlists: List[Union[int, Dict[str, Any]]] = Field(default_factory=list)
    in_progress_content: List[Union[Dict[str, Any], InProgressContentItem]] = Field(default_factory=list)
    assessment_results: List[AssessmentResultItem] = Field(default_factory=list)
    candidates: List[CandidateItem] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=50)
    type_filter: Optional[str] = None  # "content", "playlist"
    category_filter: Optional[str] = None


class ScoreBreakdownSchema(BaseModel):
    division: float = 0.0
    position: float = 0.0
    learning_gap: float = 0.0
    assessment: float = 0.0
    relevance: float = 0.0


class RecommendationItem(BaseModel):
    type: str
    id: int
    title: str
    slug: Optional[str] = None
    classification_name: Optional[str] = None
    score: int
    reasons: List[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdownSchema


class RecommendationResponse(BaseModel):
    application: str = "owl"
    user_id: int
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    explanation: Optional[str] = None
    explanation_status: str = "success"  # "success" or "unavailable"
    generated_at: str
