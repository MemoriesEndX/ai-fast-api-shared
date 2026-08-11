from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class UserProfileSchema(BaseModel):
    id: int
    name: Optional[str] = None
    division: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    role: Optional[str] = None
    level: Optional[str] = None


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
    type: str = "content"  # "content", "playlist", "video", "document"
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
    target_role: Optional[str] = None
    application: str = "owl"
    content_ids: List[int] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    application: str = "owl"
    user: UserProfileSchema
    query: Optional[str] = Field(None, description="Optional contextual query (e.g. 'recommend Laravel courses')")
    learning_history: List[Dict[str, Any]] = Field(default_factory=list)
    completed_content: List[Union[int, Dict[str, Any]]] = Field(default_factory=list)
    completed_playlists: List[Union[int, Dict[str, Any]]] = Field(default_factory=list)
    in_progress_content: List[Union[Dict[str, Any], InProgressContentItem]] = Field(default_factory=list)
    assessment_results: List[AssessmentResultItem] = Field(default_factory=list)
    candidates: List[CandidateItem] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=50)
    type_filter: Optional[str] = None  # "content", "playlist", "video", "document"
    category_filter: Optional[str] = None
    division_filter: Optional[str] = None
    include_explanation: bool = True


class ScoreBreakdownSchema(BaseModel):
    division: float = 0.0
    role: float = 0.0
    semantic: float = 0.0
    classification: float = 0.0
    assessment: float = 0.0
    progress: float = 0.0
    position: float = 0.0  # Alias for backward compatibility
    learning_gap: float = 0.0  # Alias for backward compatibility
    relevance: float = 0.0  # Alias for backward compatibility


class RecommendationItem(BaseModel):
    type: str
    id: int
    content_id: Optional[int] = None
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    classification_name: Optional[str] = None
    category: Optional[str] = None  # "CONTINUE_LEARNING", "SKILL_GAP", "ROLE_RELEVANT", "DIVISION_RELEVANT", "RELATED_CONTENT"
    score: int  # 0-100 percentage for backward compatibility
    raw_score: float = 0.0  # 0.0 - 1.0 normalized float score
    reasons: List[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdownSchema
    is_continuation: bool = False


class RecommendationResponse(BaseModel):
    application: str = "owl"
    user_id: int
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    explanation: Optional[str] = None
    explanation_status: str = "success"  # "success" or "unavailable"
    request_id: Optional[str] = None
    generated_at: str
