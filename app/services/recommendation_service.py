import logging
import math
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
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import BaseLLMService, get_llm_service

logger = logging.getLogger("ai_service.recommendation")


class RecommendationScoringService:
    """Recommendation Engine 2.0: Deterministic, transparent, multi-factor scoring & ranking service."""

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.w_division = settings.RECOMMENDATION_WEIGHT_DIVISION
        self.w_role = settings.RECOMMENDATION_WEIGHT_ROLE
        self.w_semantic = settings.RECOMMENDATION_WEIGHT_SEMANTIC
        self.w_classification = settings.RECOMMENDATION_WEIGHT_CLASSIFICATION
        self.w_assessment = settings.RECOMMENDATION_WEIGHT_ASSESSMENT
        self.w_progress = settings.RECOMMENDATION_WEIGHT_PROGRESS

        self.embedding_service = embedding_service or EmbeddingService()

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
                if int(getattr(item, "finish", 0)) == 1 or int(getattr(item, "progress", 0)) >= 100:
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
                pid = item.get("id") or item.get("trainingplan_id") or item.get("playlist_id")
                if pid is not None:
                    playlist_ids.add(int(pid))
            elif hasattr(item, "id") and item.id is not None:
                playlist_ids.add(int(item.id))
        return playlist_ids

    def extract_in_progress_map(self, in_progress_content: List[Any]) -> Dict[int, int]:
        """Extract mapping of content_id -> progress percentage for ongoing items."""
        in_prog_map: Dict[int, int] = {}
        for item in in_progress_content:
            if isinstance(item, dict):
                cid = item.get("id") or item.get("content_id")
                prog = item.get("progress", 0)
                finish = item.get("finish", 0)
                if cid is not None and int(finish) != 1 and int(prog) < 100:
                    in_prog_map[int(cid)] = int(prog)
            elif hasattr(item, "content_id") or hasattr(item, "id"):
                cid = getattr(item, "id", None) or getattr(item, "content_id", None)
                prog = getattr(item, "progress", 0)
                finish = getattr(item, "finish", 0)
                if cid is not None and int(finish) != 1 and int(prog) < 100:
                    in_prog_map[int(cid)] = int(prog)
        return in_prog_map

    def extract_completed_classifications(
        self,
        completed_content: List[Any],
        learning_history: List[Dict[str, Any]],
    ) -> Set[str]:
        """Extract set of category/classification names completed by user."""
        classifications: Set[str] = set()

        for item in completed_content:
            if isinstance(item, dict):
                cname = item.get("classification_name") or item.get("category")
                if cname:
                    classifications.add(str(cname).strip().lower())

        for hist in learning_history:
            if isinstance(hist, dict):
                cname = hist.get("classification_name") or hist.get("category") or hist.get("title")
                if cname:
                    classifications.add(str(cname).strip().lower())

        return classifications

    def is_candidate_accessible(
        self,
        candidate: CandidateItem,
        application: str,
        completed_content_ids: Set[int],
        completed_playlist_ids: Set[int],
        type_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        division_filter: Optional[str] = None,
    ) -> bool:
        """Hard Filtering: Exclude completed, inactive, expired, or cross-tenant candidates."""
        # Tenant scope check
        if candidate.application and candidate.application.strip().lower() != application.strip().lower():
            return False

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
        if cand_type in ("content", "video", "document"):
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

        # Division filter
        if division_filter:
            cand_div = (candidate.target_division or "").strip().lower()
            if cand_div and cand_div != division_filter.strip().lower():
                return False

        return True

    def calculate_semantic_similarity(
        self,
        text_a: str,
        text_b: str,
        vec_a: Optional[List[float]] = None,
        vec_b: Optional[List[float]] = None,
    ) -> float:
        """Compute cosine similarity between text_a and text_b using EmbeddingService."""
        if not text_a or not text_b:
            return 0.0
        try:
            if vec_a is None:
                vec_a = self.embedding_service.embed_text(text_a)
            if vec_b is None:
                vec_b = self.embedding_service.embed_text(text_b)
            dot = sum(a * b for a, b in zip(vec_a, vec_b))
            norm_a = math.sqrt(sum(a * a for a in vec_a))
            norm_b = math.sqrt(sum(b * b for b in vec_b))
            if norm_a > 0 and norm_b > 0:
                sim = dot / (norm_a * norm_b)
                return max(0.0, min(1.0, float(sim)))
        except Exception as exc:
            logger.warning(f"Semantic similarity calculation fallback due to: {exc}")
        # Fallback to Jaccard word token overlap
        tokens_a = set(text_a.lower().split())
        tokens_b = set(text_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        overlap = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        return float(overlap / union) if union > 0 else 0.0

    def score_candidate(
        self,
        candidate: CandidateItem,
        user: UserProfileSchema,
        query: Optional[str],
        completed_content_ids: Set[int],
        in_progress_map: Dict[int, int],
        assessment_results: List[AssessmentResultItem],
        completed_classifications: Set[str],
        user_context_vec: Optional[List[float]] = None,
        cand_vec: Optional[List[float]] = None,
    ) -> Tuple[float, float, List[str], ScoreBreakdownSchema, str, bool]:
        """
        Compute normalized scores in [0.0, 1.0] for candidate across 6 factors:
        1. Division Match
        2. Role Match
        3. Semantic Relevance
        4. Classification Match
        5. Assessment Skill Gap Signal
        6. In-Progress Continuation Signal
        """
        reasons: List[str] = []
        div_score = 0.0
        role_score = 0.0
        sem_score = 0.0
        class_score = 0.0
        ass_score = 0.0
        prog_score = 0.0
        is_continuation = False

        user_div = (user.division or "").strip().lower()
        user_role = (user.role or user.position or user.department or "").strip().lower()
        cand_div = (candidate.target_division or "").strip().lower()
        cand_role = (candidate.target_role or candidate.target_position or "").strip().lower()
        cand_title = candidate.title.lower()
        cand_desc = (candidate.description or "").lower()
        cand_class = (candidate.classification_name or "").strip().lower()

        # 1. Division Match (0.0 - 1.0)
        if user_div:
            if cand_div and cand_div == user_div:
                div_score = 1.0
                reasons.append(f"Matches your division ({user.division})")
            elif user_div in cand_title or user_div in cand_desc or (cand_class and user_div in cand_class):
                div_score = 0.7
                reasons.append(f"Content scope aligns with your division ({user.division})")

        # 2. Role Match (0.0 - 1.0)
        if user_role:
            if cand_role and cand_role == user_role:
                role_score = 1.0
                reasons.append(f"Matches your role ({user.role or user.position})")
            elif user_role in cand_title or user_role in cand_desc:
                role_score = 0.7
                reasons.append(f"Content aligns with your position role ({user.role or user.position})")

        # 3. Semantic Relevance (0.0 - 1.0)
        user_context_text = f"{user_div} {user_role} {query or ''} {' '.join(completed_classifications)}".strip()
        cand_text = f"{candidate.title} {candidate.description or ''} {candidate.classification_name or ''}".strip()
        sem_score = self.calculate_semantic_similarity(
            user_context_text,
            cand_text,
            vec_a=user_context_vec,
            vec_b=cand_vec,
        )
        if (div_score > 0 or role_score > 0) and sem_score < 0.5:
            sem_score = 0.5
        if query and query.lower() in cand_title:
            sem_score = max(sem_score, 0.9)

        if sem_score >= 0.6:
            if query:
                reasons.append(f"Matches your query '{query}'")
            else:
                reasons.append("Semantically relevant to your learning history and goals")

        # 4. Classification Match (0.0 - 1.0)
        if cand_class and cand_class in completed_classifications:
            class_score = 1.0
            reasons.append(f"Addresses learning topic following {candidate.classification_name}")
        elif completed_classifications and cand_class:
            class_score = 0.5
            reasons.append(f"Expands knowledge into related category ({candidate.classification_name})")

        # 5. Assessment Performance / Remedial Skill Gap Signal (0.0 - 1.0)
        low_assessments = [a for a in assessment_results if a.score < 70.0]
        if low_assessments:
            for ass in low_assessments:
                ass_title = (ass.title or "").lower()
                if (cand_class and cand_class in ass_title) or (ass_title and ass_title in cand_title):
                    ass_score = 1.0
                    reasons.append(f"Recommended for remedial reinforcement (Assessment score: {ass.score}%)")
                    break

        # 6. In-Progress Continuation Signal (0.0 - 1.0)
        if candidate.id in in_progress_map:
            prog_val = in_progress_map[candidate.id]
            prog_score = 1.0
            is_continuation = True
            reasons.append(f"Continue your ongoing learning ({prog_val}% completed)")

        # Cold start fallback if user has no history or matching attributes
        if not reasons:
            reasons.append("Recommended based on your organizational profile")

        # Weighted Sum Calculation & Normalization [0.0, 1.0]
        total_weight = (
            self.w_division
            + self.w_role
            + self.w_semantic
            + self.w_classification
            + self.w_assessment
            + self.w_progress
        )
        if total_weight <= 0:
            total_weight = 1.0

        raw_score = (
            (div_score * self.w_division)
            + (role_score * self.w_role)
            + (sem_score * self.w_semantic)
            + (class_score * self.w_classification)
            + (ass_score * self.w_assessment)
            + (prog_score * self.w_progress)
        ) / total_weight

        raw_score = max(0.0, min(1.0, float(raw_score)))
        percentage_score = int(round(raw_score * 100))

        # Categorization Badge Assignment
        if is_continuation:
            category = "CONTINUE_LEARNING"
        elif ass_score >= 0.8:
            category = "SKILL_GAP"
        elif role_score >= 0.7:
            category = "ROLE_RELEVANT"
        elif div_score >= 0.7:
            category = "DIVISION_RELEVANT"
        else:
            category = "RELATED_CONTENT"

        # Populate breakdown for both 2.0 and backward compatibility schema
        breakdown = ScoreBreakdownSchema(
            division=round(div_score * 30.0, 1),
            role=round(role_score, 2),
            semantic=round(sem_score, 2),
            classification=round(class_score, 2),
            assessment=round(ass_score * 15.0, 1),
            progress=round(prog_score, 2),
            position=round(role_score * 25.0, 1),
            learning_gap=round(class_score * 20.0, 1),
            relevance=round(sem_score * 10.0, 1),
        )

        return raw_score, percentage_score, reasons, breakdown, category, is_continuation

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
        in_progress_map = self.extract_in_progress_map(request.in_progress_content)
        completed_classifications = self.extract_completed_classifications(
            request.completed_content,
            request.learning_history,
        )

        user_div = (request.user.division or "").strip().lower()
        user_role = (request.user.role or request.user.position or request.user.department or "").strip().lower()
        user_context_text = f"{user_div} {user_role} {request.query or ''} {' '.join(completed_classifications)}".strip()
        user_context_vec = self.embedding_service.embed_text(user_context_text) if user_context_text else None

        valid_candidates: List[CandidateItem] = []
        cand_texts: List[str] = []
        seen_candidates: Set[Tuple[str, int]] = set()

        for candidate in request.candidates:
            cand_key = (candidate.type.strip().lower(), candidate.id)
            if cand_key in seen_candidates:
                continue
            seen_candidates.add(cand_key)

            if not self.is_candidate_accessible(
                candidate,
                application=request.application,
                completed_content_ids=completed_content_ids,
                completed_playlist_ids=completed_playlist_ids,
                type_filter=request.type_filter,
                category_filter=request.category_filter,
                division_filter=request.division_filter,
            ):
                continue

            valid_candidates.append(candidate)
            cand_texts.append(f"{candidate.title} {candidate.description or ''} {candidate.classification_name or ''}".strip())

        cand_vectors = self.embedding_service.embed_batch(cand_texts) if cand_texts else []
        scored_items: List[RecommendationItem] = []

        for idx, candidate in enumerate(valid_candidates):
            c_vec = cand_vectors[idx] if idx < len(cand_vectors) else None

            raw_score, score, reasons, breakdown, category, is_continuation = self.score_candidate(
                candidate,
                request.user,
                request.query,
                completed_content_ids,
                in_progress_map,
                request.assessment_results,
                completed_classifications,
                user_context_vec=user_context_vec,
                cand_vec=c_vec,
            )

            scored_items.append(
                RecommendationItem(
                    type=candidate.type,
                    id=candidate.id,
                    content_id=candidate.id if candidate.type in ("content", "video", "document") else None,
                    title=candidate.title,
                    slug=candidate.slug,
                    description=candidate.description,
                    classification_name=candidate.classification_name,
                    category=category,
                    score=score,
                    raw_score=raw_score,
                    reasons=reasons,
                    score_breakdown=breakdown,
                    is_continuation=is_continuation,
                )
            )

        # Sort descending by raw_score, tie-break by ID
        scored_items.sort(key=lambda x: (x.raw_score, x.id), reverse=True)

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
        import time
        from app.core.metrics import metrics_registry
        start_time = time.time()
        app_label = str(request.application)
        metrics_registry.inc("recommendation_requests_total", labels={"application": app_label})

        recommendations = self.scoring_service.generate_recommendations(request)
        timestamp = datetime.now(timezone.utc).isoformat()

        if not recommendations:
            duration = time.time() - start_time
            metrics_registry.observe("recommendation_latency_seconds", duration, labels={"application": app_label})
            return RecommendationResponse(
                application=request.application,
                user_id=request.user.id,
                recommendations=[],
                explanation="Belum ada rekomendasi yang sesuai untuk profil dan kriteria pencarian Anda.",
                explanation_status="success",
                generated_at=timestamp,
            )

        explanation = None
        explanation_status = "success"

        if request.include_explanation:
            try:
                system_prompt = (
                    "Anda adalah AI Learning Advisor untuk platform OWL / HR Corner LMS. "
                    "Berikan penjelasan singkat (1-2 kalimat) dalam bahasa Indonesia yang ramah, "
                    "jelas, dan profesional mengenai mengapa rekomendasi pembelajaran berikut sangat sesuai "
                    "dengan divisi dan posisi pengguna. HANYA gunakan fakta dari alasan yang diberikan. "
                    "JANGAN mengarang informasi yang tidak ada."
                )
                top_rec_bullets = "\n".join(
                    f"- {rec.title} ({rec.type}): {', '.join(rec.reasons)}"
                    for rec in recommendations[:3]
                )
                user_info = (
                    f"User: {request.user.name or 'Pengguna'}\n"
                    f"Divisi: {request.user.division or 'Umum'}\n"
                    f"Role/Posisi: {request.user.role or request.user.position or request.user.department or 'Staff'}\n"
                )
                user_prompt = f"{user_info}\nRekomendasi Pilihan:\n{top_rec_bullets}\n\nPenjelasan Singkat:"
                explanation = await self.llm_service.generate_explanation(system_prompt, user_prompt)
                if not explanation:
                    explanation_status = "unavailable"
            except Exception as exc:
                logger.warning(f"Qwen explanation generation failed: {exc}")
                explanation = None
                explanation_status = "unavailable"

        duration = time.time() - start_time
        metrics_registry.observe("recommendation_latency_seconds", duration, labels={"application": app_label})

        return RecommendationResponse(
            application=request.application,
            user_id=request.user.id,
            recommendations=recommendations,
            explanation=explanation,
            explanation_status=explanation_status,
            generated_at=timestamp,
        )

    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """Alias for get_recommendations."""
        return await self.get_recommendations(request)


# Singleton instance
recommendation_engine = RecommendationEngine()
