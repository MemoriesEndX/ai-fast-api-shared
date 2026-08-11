import logging
import re
from typing import List, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger("ai_service.agent.router")


class AgentIntent(str, Enum):
    LMS_PROFILE = "LMS_PROFILE"
    LMS_PROGRESS = "LMS_PROGRESS"
    LMS_ASSESSMENT = "LMS_ASSESSMENT"
    CONTENT_SEARCH = "CONTENT_SEARCH"
    PLAYLIST_SEARCH = "PLAYLIST_SEARCH"
    CONTENT_DETAIL = "CONTENT_DETAIL"
    PLAYLIST_DETAIL = "PLAYLIST_DETAIL"
    RECOMMENDATION = "RECOMMENDATION"
    PDF_KNOWLEDGE = "PDF_KNOWLEDGE"
    VIDEO_KNOWLEDGE = "VIDEO_KNOWLEDGE"
    GENERAL_LMS = "GENERAL_LMS"


class IntentRouter:
    """Deterministic and pattern-assisted intent router for classifying user requests to appropriate tools."""

    @staticmethod
    def classify_intent(message: str, document_id: Any = None) -> Tuple[List[AgentIntent], List[str]]:
        """
        Analyze user prompt text to detect primary intents and candidate MCP tool names.
        Returns a tuple of (List[AgentIntent], List[tool_names]).
        """
        msg_lower = message.lower()
        intents: List[AgentIntent] = []
        tools: List[str] = []

        # Prompt injection detection keyword safeguards
        if "ignore previous instructions" in msg_lower or "ignore authorization" in msg_lower:
            logger.warning("Prompt injection signature detected in user prompt.")

        # 1. Recommendation Intent
        if any(k in msg_lower for k in [
            "cocok", "rekomendasi", "disarankan", "sebaiknya saya ambil", "saran pembelajaran", "rekomendasikan",
            "belajar apa berikutnya", "materi selanjutnya", "bantu saya memilih", "pilihlah modul", "saran belajar"
        ]):
            intents.append(AgentIntent.RECOMMENDATION)
            tools.extend([
                "get_user_learning_profile",
                "get_learning_progress",
                "get_user_assessments",
                "get_learning_recommendations"
            ])

        # 2. LMS Progress Intent
        if any(k in msg_lower for k in ["progress", "kemajuan", "sudah belajar", "progres", "sudah selesai", "sedang saya ikuti", "sedang dipelajari"]):
            if AgentIntent.RECOMMENDATION not in intents:
                intents.append(AgentIntent.LMS_PROGRESS)
                tools.append("get_learning_progress")

        # 3. Assessment / Exam Intent
        if any(k in msg_lower for k in ["nilai", "assessment", "skor", "ujian", "evaluasi", "tes"]):
            if AgentIntent.RECOMMENDATION not in intents:
                intents.append(AgentIntent.LMS_ASSESSMENT)
                tools.append("get_user_assessments")

        # 4. Profile Intent
        if any(k in msg_lower for k in ["profil", "divisi saya", "jabatan saya", "posisi saya"]) and "get_user_learning_profile" not in tools:
            intents.append(AgentIntent.LMS_PROFILE)
            tools.append("get_user_learning_profile")

        # 5. Video RAG Intent
        if any(k in msg_lower for k in ["video", "menit", "detik", "timestamp", "durasi", "tonton", "rekaman"]):
            intents.append(AgentIntent.VIDEO_KNOWLEDGE)
            tools.append("search_video_transcript")

        # 6. PDF Knowledge RAG Intent
        if any(k in msg_lower for k in [
            "aturan", "dokumen", "kebijakan", "policy", "standar", "sop", "pasal", "pdf", "file", "safety policy",
            "apd", "panduan", "ketentuan", "sanksi", "jarak aman", "kewajiban pekerja", "persyaratan", "prosedur"
        ]):
            if AgentIntent.VIDEO_KNOWLEDGE not in intents or any(x in msg_lower for x in ["apd", "policy", "dokumen", "pdf"]):
                intents.append(AgentIntent.PDF_KNOWLEDGE)
                tools.append("search_pdf_knowledge")

        # 7. Content / Playlist Search & Details Intent
        if any(k in msg_lower for k in ["cari modul", "cari materi", "cari konten", "search content"]):
            intents.append(AgentIntent.CONTENT_SEARCH)
            tools.append("search_learning_content")

        if any(k in msg_lower for k in ["cari playlist", "playlist apa saja", "daftar playlist"]):
            intents.append(AgentIntent.PLAYLIST_SEARCH)
            tools.append("search_learning_playlist")

        if "detail modul" in msg_lower or "detail konten" in msg_lower:
            intents.append(AgentIntent.CONTENT_DETAIL)
            tools.append("get_content_detail")

        if "detail playlist" in msg_lower or "isi playlist" in msg_lower:
            intents.append(AgentIntent.PLAYLIST_DETAIL)
            tools.append("get_playlist_detail")

        # Fallback if specific document_id scoping is provided
        if document_id is not None and "search_pdf_knowledge" not in tools and "search_video_transcript" not in tools:
            intents.append(AgentIntent.PDF_KNOWLEDGE)
            tools.append("search_pdf_knowledge")

        # Default fallback to GENERAL_LMS if no specific tool matched
        if not tools:
            intents.append(AgentIntent.GENERAL_LMS)

        # Deduplicate tools while preserving ordering
        seen = set()
        dedup_tools = [t for t in tools if not (t in seen or seen.add(t))]

        return intents, dedup_tools


intent_router = IntentRouter()
