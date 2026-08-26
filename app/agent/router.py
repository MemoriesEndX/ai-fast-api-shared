import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from app.agent.intents import AgentIntent
from app.agent.normalizer import intent_normalizer
from app.agent.fuzzy_matcher import fuzzy_intent_matcher

logger = logging.getLogger("ai_service.agent.router")


def _matches_any_keyword(text: str, keywords: List[str]) -> bool:
    """Check if any keyword or phrase matches with word boundary in text to prevent substring false positives."""
    for kw in keywords:
        pattern = r'(?:\b|\A)' + re.escape(kw.strip().lower()) + r'(?:\b|\Z)'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# Canonical tool mapping for single-intent resolution
INTENT_TOOL_MAPPING: Dict[AgentIntent, List[str]] = {
    AgentIntent.LMS_PROGRESS: ["get_learning_progress"],
    AgentIntent.LMS_PROFILE: ["get_user_learning_profile"],
    AgentIntent.LMS_ASSESSMENT: ["get_user_assessments"],
    AgentIntent.RECOMMENDATION: ["get_learning_recommendations"],
    AgentIntent.PDF_KNOWLEDGE: ["search_pdf_knowledge"],
    AgentIntent.VIDEO_KNOWLEDGE: ["search_video_transcript"],
    AgentIntent.CONTENT_SEARCH: ["search_learning_content"],
    AgentIntent.PLAYLIST_SEARCH: ["search_learning_playlist"],
    AgentIntent.CONTENT_DETAIL: ["get_content_detail"],
    AgentIntent.PLAYLIST_DETAIL: ["get_playlist_detail"],
    AgentIntent.GENERAL_LMS: [],
    AgentIntent.GENERAL_CHAT: [],
}


class IntentRouter:
    """
    Deterministic, pattern-assisted, and Hybrid Fuzzy Intent Router.
    Priority order:
    1. Text Normalization (Indonesian slang, repeated chars, contractions, punctuation)
    2. Deterministic / Exact / Regex / Keyword Rules (First priority, sub-millisecond, highly accurate)
    3. Confident & Ambiguity-guarded Hybrid Fuzzy Matcher (Typo resilience, natural language paraphrasing)
    4. GENERAL_CHAT fallback (Safe default, no tools, no private vector queries)
    """

    @staticmethod
    def classify_intent(message: str, document_id: Any = None) -> Tuple[List[AgentIntent], List[str]]:
        """
        Analyze user prompt text to detect primary intents and candidate MCP tool names.
        Returns a tuple of (List[AgentIntent], List[tool_names]).
        """
        msg_clean = message.strip()
        msg_lower = msg_clean.lower()
        normalized_msg = intent_normalizer.normalize(message)
        
        intents: List[AgentIntent] = []
        tools: List[str] = []

        # Prompt injection detection keyword safeguards
        if "ignore previous instructions" in msg_lower or "ignore authorization" in msg_lower or "ignore previous instructions" in normalized_msg:
            logger.warning("Prompt injection signature detected in user prompt.")

        # =========================================================================
        # 0. Pure Greetings & Conversational Pleasantries Detection
        # =========================================================================
        greeting_patterns = [
            r"^(halo|hai|hei|helo|hello|hi|hey)[\s\.,!\?]*$",
            r"^selamat\s+(pagi|siang|sore|malam|datang|hari|sejahtera)[\s\.,!\?]*$",
            r"^(apa\s+kabar|gimana\s+kabarnya|bagaimana\s+kabarmu|kabar\s+baik)[\s\.,!\?]*$",
            r"^(terima\s+kasih|makasih|thanks|thank\s+you|syukron|matur\s+nuwun)[\s\.,!\?]*$",
            r"^(siapa\s+kamu|kamu\s+siapa|siapa\s+namamu|siapakah\s+kamu|perkenalkan\s+dirimu)[\s\.,!\?]*$",
            r"^(bisa\s+bantu\s+saya|bisa\s+tolong\s+saya|tolong\s+bantu\s+saya|bantu\s+saya)[\s\.,!\?]*$",
            r"^good\s+(morning|afternoon|evening|night|day)[\s\.,!\?]*$",
            r"^(how\s+are\s+you|who\s+are\s+you)[\s\.,!\?]*$",
        ]
        is_pure_greeting = any(re.search(p, msg_lower) for p in greeting_patterns) or any(re.search(p, normalized_msg) for p in greeting_patterns)

        # Off-topic / Casual questions detection (cooking recipes, stories, general advice, etc.)
        casual_kw = [
            "resep", "masak", "makan malam", "makan siang", "sarapan", "menu makan", "kuliner",
            "cerita", "dongeng", "puisi", "lelucon", "joke", "cuaca", "arti mimpi"
        ]
        is_general_casual = _matches_any_keyword(msg_lower, casual_kw) or _matches_any_keyword(normalized_msg, casual_kw)

        # If pure greeting or explicit casual without any document ID, route directly to GENERAL_CHAT
        if (is_pure_greeting or is_general_casual) and document_id is None:
            return [AgentIntent.GENERAL_CHAT], []

        # =========================================================================
        # 1. Deterministic / Exact Keyword & Regex Intent Detection
        # =========================================================================
        progress_kw = [
            "progress", "kemajuan", "sudah belajar", "progres", "sudah selesai", "selesaikan",
            "sedang saya ikuti", "sedang dipelajari", "status pembelajaran", "status belajar"
        ]
        has_progress_kw = _matches_any_keyword(msg_lower, progress_kw) or _matches_any_keyword(normalized_msg, progress_kw)

        assessment_kw = ["nilai", "assessment", "skor", "ujian", "evaluasi", "tes", "asesmen", "kuis"]
        has_assessment_kw = (_matches_any_keyword(msg_lower, assessment_kw) or _matches_any_keyword(normalized_msg, assessment_kw)) and not is_general_casual

        profile_kw = [
            "profil", "profile", "divisi saya", "jabatan saya", "posisi saya", "data diri saya",
            "user profile", "learning profile"
        ]
        has_profile_kw = _matches_any_keyword(msg_lower, profile_kw) or _matches_any_keyword(normalized_msg, profile_kw)

        # Check if comprehensive multi-tool analysis is explicitly requested
        is_multi_analysis = (
            ("analisis" in msg_lower or "evaluasi" in msg_lower or "tampilkan semua" in msg_lower or "lengkap" in msg_lower or "semua" in msg_lower or "analisis" in normalized_msg)
            and sum([has_progress_kw, has_assessment_kw, has_profile_kw]) >= 2
        ) or (
            has_progress_kw and has_assessment_kw and has_profile_kw
        )

        # Recommendation Intent
        learning_rec_keywords = [
            "pembelajaran yang cocok", "pembelajaran apa yang cocok", "rekomendasi pembelajaran",
            "rekomendasikan pembelajaran", "rekomendasi modul", "rekomendasikan modul",
            "saran pembelajaran", "belajar apa berikutnya", "materi selanjutnya",
            "bantu saya memilih", "pilihlah modul", "saran belajar", "modul apa selanjutnya",
            "meningkatkan keterampilan", "prioritas belajar", "rekomendasi pelatihan",
            "rekomendasikan pelatihan", "rekomendasi learning", "rekomendasikan learning"
        ]

        is_rec_intent = any(k in msg_lower for k in learning_rec_keywords) or any(k in normalized_msg for k in learning_rec_keywords) or (
            any(k in msg_lower or k in normalized_msg for k in ["cocok", "rekomendasi", "rekomendasikan", "disarankan", "sebaiknya saya ambil"])
            and not is_general_casual
            and any(k in msg_lower or k in normalized_msg for k in ["belajar", "modul", "kursus", "materi", "pelatihan", "training", "course", "lms", "saya", "pembelajaran"])
        )

        if is_rec_intent:
            intents.append(AgentIntent.RECOMMENDATION)
            tools.append("get_learning_recommendations")
            if is_multi_analysis:
                if has_profile_kw or "analisis" in msg_lower or "analisis" in normalized_msg:
                    intents.append(AgentIntent.LMS_PROFILE)
                    tools.append("get_user_learning_profile")
                if has_progress_kw or "analisis" in msg_lower or "analisis" in normalized_msg:
                    intents.append(AgentIntent.LMS_PROGRESS)
                    tools.append("get_learning_progress")
                if has_assessment_kw or "analisis" in msg_lower or "analisis" in normalized_msg:
                    intents.append(AgentIntent.LMS_ASSESSMENT)
                    tools.append("get_user_assessments")
            else:
                if has_progress_kw:
                    intents.append(AgentIntent.LMS_PROGRESS)
                    tools.append("get_learning_progress")
                if has_assessment_kw:
                    intents.append(AgentIntent.LMS_ASSESSMENT)
                    tools.append("get_user_assessments")
                if has_profile_kw:
                    intents.append(AgentIntent.LMS_PROFILE)
                    tools.append("get_user_learning_profile")

        # LMS Progress Intent
        if has_progress_kw and "get_learning_progress" not in tools:
            intents.append(AgentIntent.LMS_PROGRESS)
            tools.append("get_learning_progress")

        # Assessment Intent
        if has_assessment_kw and "get_user_assessments" not in tools:
            intents.append(AgentIntent.LMS_ASSESSMENT)
            tools.append("get_user_assessments")

        # Profile Intent
        if has_profile_kw and "get_user_learning_profile" not in tools:
            intents.append(AgentIntent.LMS_PROFILE)
            tools.append("get_user_learning_profile")

        # Video RAG Intent
        video_kw = ["video", "menit", "detik", "timestamp", "durasi", "tonton", "rekaman", "transcript video", "transkrip video", "materi video"]
        if _matches_any_keyword(msg_lower, video_kw) or _matches_any_keyword(normalized_msg, video_kw):
            intents.append(AgentIntent.VIDEO_KNOWLEDGE)
            tools.append("search_video_transcript")

        # PDF Knowledge RAG Intent
        pdf_keywords = [
            "safety induction", "aturan", "dokumen", "kebijakan", "policy", "standar", "sop", "pasal", "pdf", "file",
            "safety policy", "apd", "panduan", "ketentuan", "sanksi", "jarak aman", "kewajiban pekerja", "persyaratan",
            "prosedur", "ijin kerja", "area terbatas", "confined space", "beban maksimal", "angkat manual", "near-miss",
            "pelaporan kecelakaan", "helm keselamatan", "materi safety", "safety", "k3"
        ]
        if (_matches_any_keyword(msg_lower, pdf_keywords) or _matches_any_keyword(normalized_msg, pdf_keywords)) and not is_pure_greeting:
            if AgentIntent.VIDEO_KNOWLEDGE not in intents or _matches_any_keyword(msg_lower, ["apd", "policy", "dokumen", "pdf", "sop"]):
                intents.append(AgentIntent.PDF_KNOWLEDGE)
                tools.append("search_pdf_knowledge")

        # Content / Playlist Search & Details Intent
        content_search_kw = ["cari modul", "cari materi", "cari konten", "search content", "cari pelatihan", "pelatihan", "kursus"]
        if any(k in msg_lower or k in normalized_msg for k in content_search_kw):
            intents.append(AgentIntent.CONTENT_SEARCH)
            tools.append("search_learning_content")

        playlist_search_kw = ["cari playlist", "playlist apa saja", "daftar playlist", "training plan"]
        if any(k in msg_lower or k in normalized_msg for k in playlist_search_kw):
            intents.append(AgentIntent.PLAYLIST_SEARCH)
            tools.append("search_learning_playlist")

        if "detail modul" in msg_lower or "detail konten" in msg_lower or "detail modul" in normalized_msg:
            intents.append(AgentIntent.CONTENT_DETAIL)
            tools.append("get_content_detail")

        if "detail playlist" in msg_lower or "isi playlist" in msg_lower or "materi dalam playlist" in msg_lower:
            intents.append(AgentIntent.PLAYLIST_DETAIL)
            tools.append("get_playlist_detail")

        # Fallback if specific document_id scoping is provided (and not pure greeting)
        if document_id is not None and not is_pure_greeting:
            if "search_pdf_knowledge" not in tools and "search_video_transcript" not in tools:
                intents.append(AgentIntent.PDF_KNOWLEDGE)
                tools.append("search_pdf_knowledge")

        # =========================================================================
        # 2. Hybrid Fuzzy Intent Matching Fallback (if no exact domain tool matched)
        # =========================================================================
        if not tools:
            # First, check LMS general domain concepts
            if _matches_any_keyword(msg_lower, [
                "tujuan pembelajaran", "fungsi hr corner", "materi lms", "sistem lms", "fitur lms", "portal hr"
            ]) or _matches_any_keyword(normalized_msg, [
                "tujuan pembelajaran", "fungsi hr corner", "materi lms", "sistem lms", "fitur lms", "portal hr"
            ]):
                intents = [AgentIntent.GENERAL_LMS]
            else:
                # Run Hybrid Fuzzy Intent Matcher on normalized message
                fuzzy_res = fuzzy_intent_matcher.match_intent(normalized_msg)
                if fuzzy_res is not None:
                    fuzzy_intent, fuzzy_score, fuzzy_phrase = fuzzy_res
                    logger.info(
                        f"Fuzzy Intent accepted: '{fuzzy_intent.value}' (score: {fuzzy_score:.2f}, phrase: '{fuzzy_phrase}') for message: '{message}'"
                    )
                    intents = [fuzzy_intent]
                    mapped_tools = INTENT_TOOL_MAPPING.get(fuzzy_intent, [])
                    tools.extend(mapped_tools)
                else:
                    intents = [AgentIntent.GENERAL_CHAT]

        # Deduplicate tools while preserving ordering
        seen = set()
        dedup_tools = [t for t in tools if not (t in seen or seen.add(t))]

        return intents, dedup_tools


intent_router = IntentRouter()
