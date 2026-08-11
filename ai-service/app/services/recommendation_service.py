import logging
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationItem,
    ScoreBreakdownSchema,
    CandidateItem,
    UserProfileSchema,
    AssessmentResultItem,
)
from app.services.llm_service import BaseLLMService, get_llm_service

logger = logging.getLogger("ai_service.recommendation")


class RecommendationScoringService:
    """Service responsible for deterministic scoring and ranking of learning candidates."""

    def __init__(self):
        self.weight_division = settings.RECOMMENDATION_WEIGHT_DIVISION
        self.weight_position = settings.RECOMMENDATION_WEIGHT_POSITION
        self.weight_gap = settings.RECOMMENDATION_WEIGHT_GAP
        self.weight_assessment = settings.RECOMMENDATION_WEIGHT_ASSESSMENT
        self.weight_relevance = settings.RECOMMENDATION_WEIGHT_RELEVANCE

    def extract_completed_ids(
        self,
        completed_content: List[Any],
        in_progress_content: List[Any],
    ) -> Set[int]:
        """Extract set of completed content IDs from history and progress list."""
        completed_ids: Set[int] = set()

        for item in completed_content:
            if isinstance(item, int):
                completed_ids.add(item)
            elif isinstance(item, dict):
                cid = item.get("id") or item.get("content_id")
                if cid is not None:
                    completed_ids.add(int(cid))
            elif hasattr(item, "id") and item.id is not None:
                completed_ids.add(int(item.id))
            elif hasattr(item, "content_id") and item.content_id is not None:
                completed_ids.add(int(item.content_id))

        for item in in_progress_content:
            if isinstance(item, dict):
                finish = item.get("finish", 0)
                progress = item.get("progress", 0)
                cid = item.get("id") or item.get("content_id")
                if (int(finish) == 1 or int(progress) >= 100) and cid is not None:
                    completed_ids.add(int(cid))
            elif hasattr(item, "finish") and hasattr(item, "progress"):
                if (int(item.finish) == 1 or int(item.progress) >= 100):
                    cid = getattr(item, "id", None) or getattr(item, "content_id", None)
                    if cid is not None:
                        completed_ids.add(int(cid))

        return completed_ids

    def extract_completed_playlist_ids(self, completed_playlists: List[Any]) -> Set[int]:
        """Extract set of completed playlist IDs."""
        playlist_ids: Set[int] = set()
        for item in completed_playlists:
            if isinstance(item, int):
                playlist_ids.add(item)
            elif isinstance(item, dict):
                pid = item.get("id") or item.get("trainingplan_id")
                if pid is not None:
                    playlist_ids.add(int(pid))
            elif hasattr(item, "id") and item.id is not None:
                playlist_ids.add(int(item.id))
        return playlist_ids

    def extract_completed_classifications(
        self,
        completed_content: List[Any],
        learning_history: List[Dict[str, Any]],
    ) -> Set[str]:
        """Extract set of category/classification names completed by user."""
        classifications: Set[str] = set()

        for item in completed_content:
            if isinstance(item, dict):
                cname = item.get("classification_name")
                if cname:
                    classifications.add(cname.strip().lower())

        for hist in learning_history:
            if isinstance(hist, dict):
                cname = hist.get("classification_name") or hist.get("category")
                if cname:
                    classifications.add(cname.strip().lower())

        return classifications

    def is_candidate_accessible(
        self,
        candidate: CandidateItem,
        completed_content_ids: Set[int],
        completed_playlist_ids: Set[int],
        type_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> bool:
        """Filter out inactive, completed, expired, or non-matching candidates."""
        # Active status check
        active_str = str(candidate.active).strip().lower()
        if active_str not in ["active", "1", "true", "ok"]:
            return False

        # Deadline check
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if candidate.has_deadline:
            if candidate.to_date and candidate.to_date < today_str:
                return False
            if candidate.from_date and candidate.from_date > today_str:
                return False

        # Completed content/playlist exclusion
        cand_type = candidate.type.strip().lower()
        if cand_type == "content":
            if candidate.id in completed_content_ids:
                return False
        elif cand_type == "playlist":
            if candidate.id in completed_playlist_ids:
                return False
            if candidate.content_ids and set(candidate.content_ids).issubset(completed_content_ids):
                return False

        # Type filter
        if type_filter and cand_type != type_filter.strip().lower():
            return False

        # Category filter
        if category_filter:
            cand_cat = (candidate.classification_name or "").strip().lower()
            if cand_cat != category_filter.strip().lower():
                return False

        return True

    def score_candidate(
        self,
        candidate: CandidateItem,
        user: UserProfileSchema,
        completed_content_ids: Set[int],
        completed_playlist_ids: Set[int],
        assessment_results: List[AssessmentResultItem],
        completed_classifications: Set[str],
    ) -> Tuple[float, List[str], ScoreBreakdownSchema]:
        """Compute deterministic relevance score and human-readable reasons for a candidate."""
        reasons: List[str] = []
        div_score = 0.0
        pos_score = 0.0
        gap_score = 0.0
        ass_score = 0.0
        rel_score = 0.0

        user_div = (user.division or "").strip().lower()
        cand_div = (candidate.target_division or "").strip().lower()
        cand_title = candidate.title.lower()
        cand_desc = (candidate.description or "").lower()
        cand_class = (candidate.classification_name or "").strip().lower()

        # 1. Division Match
        if user_div:
            if cand_div and cand_div == user_div:
                div_score = self.weight_division
                reasons.append(f"Matches user division ({user.division})")
            elif user_div in cand_title or user_div in cand_desc or (cand_class and user_div in cand_class):
                div_score = round(self.weight_division * 0.7, 1)
                reasons.append(f"Content scope aligns with division ({user.division})")

        # 2. Position / Department Match
        user_pos = (user.position or user.department or user.team or "").strip().lower()
        cand_pos = (candidate.target_position or "").strip().lower()

        if user_pos:
            if cand_pos and cand_pos == user_pos:
                pos_score = self.weight_position
                reasons.append(f"Matches user position ({user.position or user.department})")
            elif user_pos in cand_title or user_pos in cand_desc:
                pos_score = round(self.weight_position * 0.6, 1)
                reasons.append(f"Content aligns with position role ({user.position or user.department})")

        # 3. Learning Gap Detection
        if cand_class and cand_class in completed_classifications:
            gap_score = self.weight_gap
            reasons.append(f"Addresses learning gap following completed {candidate.classification_name}")
        elif completed_classifications and cand_class:
            gap_score = round(self.weight_gap * 0.5, 1)
            reasons.append(f"Expands knowledge into related category ({candidate.classification_name})")
        elif not completed_content_ids:
            gap_score = round(self.weight_gap * 0.5, 1)
            reasons.append("Recommended baseline foundational learning")

        # 4. Assessment Performance Weakness Signal
        low_assessments = [a for a in assessment_results if a.score < 70.0]
        if low_assessments:
            matched = False
            for ass in low_assessments:
                ass_title = (ass.title or "").lower()
                if (cand_class and cand_class in ass_title) or (ass_title and ass_title in cand_title):
                    ass_score = self.weight_assessment
                    reasons.append(f"Recommended for reinforcement based on assessment score ({ass.score})")
                    matched = True
                    break
            if not matched:
                ass_score = round(self.weight_assessment * 0.5, 1)
                reasons.append("Reinforces skills after lower assessment performance")

        # 5. Content Relevance / Baseline
        rel_score = self.weight_relevance
        if not reasons:
            reasons.append("General learning relevance")

        total_score = min(100.0, div_score + pos_score + gap_score + ass_score + rel_score)
        breakdown = ScoreBreakdownSchema(
            division=div_score,
            position=pos_score,
            learning_gap=gap_score,
            assessment=ass_score,
            relevance=rel_score,
        )

        return total_score, reasons, breakdown

    def generate_recommendations(
        self,
        request: RecommendationRequest,
    ) -> List[RecommendationItem]:
        """Generate, score, filter, and rank candidate learning items."""
        completed_content_ids = self.extract_completed_ids(
            request.completed_content,
            request.in_progress_content,
        )
        completed_playlist_ids = self.extract_completed_playlist_ids(
            request.completed_playlists,
        )
        completed_classifications = self.extract_completed_classifications(
            request.completed_content,
            request.learning_history,
        )

        scored_items: List[RecommendationItem] = []

        for candidate in request.candidates:
            if not self.is_candidate_accessible(
                candidate,
                completed_content_ids,
                completed_playlist_ids,
                type_filter=request.type_filter,
                category_filter=request.category_filter,
            ):
                continue

            score, reasons, breakdown = self.score_candidate(
                candidate,
                request.user,
                completed_content_ids,
                completed_playlist_ids,
                request.assessment_results,
                completed_classifications,
            )

            scored_items.append(
                RecommendationItem(
                    type=candidate.type,
                    id=candidate.id,
                    title=candidate.title,
                    slug=candidate.slug,
                    classification_name=candidate.classification_name,
                    score=int(round(score)),
                    reasons=reasons,
                    score_breakdown=breakdown,
                )
            )

        # Sort descending by score, tie-break by ID
        scored_items.sort(key=lambda x: (x.score, x.id), reverse=True)

        # Limit
        limit = min(request.limit, settings.RECOMMENDATION_MAX_LIMIT)
        return scored_items[:limit]


class RecommendationEngine:
    """Engine orchestrating candidate scoring and Qwen natural language explanation."""

    def __init__(
        self,
        scoring_service: Optional[RecommendationScoringService] = None,
        llm_service: Optional[BaseLLMService] = None,
    ):
        self.scoring_service = scoring_service or RecommendationScoringService()
        self.llm_service = llm_service or get_llm_service()

    async def get_recommendations(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        """Process recommendation request, rank candidates, and generate Qwen explanation."""
        recommendations = self.scoring_service.generate_recommendations(request)
        timestamp = datetime.now(timezone.utc).isoformat()

        if not recommendations:
            return RecommendationResponse(
                application="owl",
                user_id=request.user.id,
                recommendations=[],
                explanation="Belum ada rekomendasi yang sesuai untuk profil dan kriteria pencarian Anda.",
                explanation_status="success",
                generated_at=timestamp,
            )

        # Build prompt for Qwen explanation
        explanation = None
        explanation_status = "success"

        try:
            system_prompt = (
                "Anda adalah AI Learning Advisor untuk platform OWL LMS. "
                "Berikan penjelasan singkat (1-2 kalimat) dalam bahasa Indonesia yang ramah, "
                "jelas, dan profesional mengenai mengapa rekomendasi pembelajaran berikut sangat sesuai "
                "dengan profil divisi dan posisi pengguna. Jangan menyebutkan numeric score secara teknis."
            )
            top_rec_bullets = "\n".join(
                f"- {rec.title} ({rec.type}): {', '.join(rec.reasons)}"
                for rec in recommendations[:3]
            )
            user_info = (
                f"User: {request.user.name or 'Pengguna'}\n"
                f"Divisi: {request.user.division or 'Umum'}\n"
                f"Posisi: {request.user.position or request.user.department or 'Staff'}\n"
            )
            user_prompt = f"{user_info}\nRekomendasi Pilihan:\n{top_rec_bullets}\n\nPenjelasan Singkat:"

            explanation = await self.llm_service.generate_explanation(system_prompt, user_prompt)
            if not explanation:
                explanation_status = "unavailable"
        except Exception as exc:
            logger.warning(f"Qwen explanation generation failed: {exc}")
            explanation = None
            explanation_status = "unavailable"

        return RecommendationResponse(
            application="owl",
            user_id=request.user.id,
            recommendations=recommendations,
            explanation=explanation,
            explanation_status=explanation_status,
            generated_at=timestamp,
        )
