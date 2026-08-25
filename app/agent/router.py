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
    GENERAL_CHAT = "GENERAL_CHAT"


def _matches_any_keyword(text: str, keywords: List[str]) -> bool:
    """Check if any keyword or phrase matches with word boundary in text to prevent substring false positives."""
    for kw in keywords:
        pattern = r'(?:\b|\A)' + re.escape(kw.strip().lower()) + r'(?:\b|\Z)'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


class IntentRouter:
    """Deterministic and pattern-assisted intent router for classifying user requests to appropriate tools."""

    @staticmethod
    def classify_intent(message: str, document_id: Any = None) -> Tuple[List[AgentIntent], List[str]]:
        """
        Analyze user prompt text to detect primary intents and candidate MCP tool names.
        Returns a tuple of (List[AgentIntent], List[tool_names]).
        """
        msg_clean = message.strip()
        msg_lower = msg_clean.lower()
        intents: List[AgentIntent] = []
        tools: List[str] = []

        # Prompt injection detection keyword safeguards
        if "ignore previous instructions" in msg_lower or "ignore authorization" in msg_lower:
            logger.warning("Prompt injection signature detected in user prompt.")

        # 0. Pure Greetings & Conversational Pleasantries Detection
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
        is_pure_greeting = any(re.search(p, msg_lower) for p in greeting_patterns)

        # Off-topic / Casual questions detection (cooking recipes, stories, general advice, etc.)
        is_general_casual = any(k in msg_lower for k in [
            "resep", "masak", "makan malam", "makan siang", "sarapan", "menu makan", "kuliner",
            "cerita", "dongeng", "puisi", "lelucon", "joke", "cuaca", "arti mimpi"
        ])

        # 1. Recommendation Intent (Learning / LMS Course / Module specific)
        learning_rec_keywords = [
            "pembelajaran yang cocok", "pembelajaran apa yang cocok", "rekomendasi pembelajaran",
            "rekomendasikan pembelajaran", "rekomendasi modul", "rekomendasikan modul",
            "saran pembelajaran", "belajar apa berikutnya", "materi selanjutnya",
            "bantu saya memilih", "pilihlah modul", "saran belajar", "modul apa selanjutnya",
            "meningkatkan keterampilan", "prioritas belajar", "rekomendasi pelatihan",
            "rekomendasikan pelatihan", "rekomendasi learning", "rekomendasikan learning"
        ]

        if any(k in msg_lower for k in learning_rec_keywords) or (
            any(k in msg_lower for k in ["cocok", "rekomendasi", "rekomendasikan", "disarankan", "sebaiknya saya ambil"])
            and not is_general_casual
            and any(k in msg_lower for k in ["belajar", "modul", "kursus", "materi", "pelatihan", "training", "course", "lms", "saya", "pembelajaran"])
        ):
            intents.append(AgentIntent.RECOMMENDATION)
            tools.extend([
                "get_user_learning_profile",
                "get_learning_progress",
                "get_user_assessments",
                "get_learning_recommendations"
            ])

        # 2. LMS Progress Intent
        if any(k in msg_lower for k in [
            "progress", "kemajuan", "sudah belajar", "progres", "sudah selesai", "selesaikan",
            "sedang saya ikuti", "sedang dipelajari", "status pembelajaran", "status belajar"
        ]):
            if AgentIntent.RECOMMENDATION not in intents:
                intents.append(AgentIntent.LMS_PROGRESS)
                tools.append("get_learning_progress")

        # 3. Assessment / Exam Intent
        if any(k in msg_lower for k in ["nilai", "assessment", "skor", "ujian", "evaluasi", "tes"]) and not is_general_casual:
            if AgentIntent.RECOMMENDATION not in intents:
                intents.append(AgentIntent.LMS_ASSESSMENT)
                tools.append("get_user_assessments")

        # 4. Profile Intent
        profile_keywords = [
            "profil", "profile", "divisi saya", "jabatan saya", "posisi saya", "data diri saya",
            "user profile", "learning profile"
        ]
        if _matches_any_keyword(msg_lower, profile_keywords) and "get_user_learning_profile" not in tools:
            intents.append(AgentIntent.LMS_PROFILE)
            tools.append("get_user_learning_profile")

        # 5. Video RAG Intent
        if any(k in msg_lower for k in ["video", "menit", "detik", "timestamp", "durasi", "tonton", "rekaman", "transcript video", "materi video"]):
            intents.append(AgentIntent.VIDEO_KNOWLEDGE)
            tools.append("search_video_transcript")

        # 6. PDF Knowledge RAG Intent
        pdf_keywords = [
            "safety induction", "aturan", "dokumen", "kebijakan", "policy", "standar", "sop", "pasal", "pdf", "file",
            "safety policy", "apd", "panduan", "ketentuan", "sanksi", "jarak aman", "kewajiban pekerja", "persyaratan",
            "prosedur", "ijin kerja", "area terbatas", "confined space", "beban maksimal", "angkat manual", "near-miss",
            "pelaporan kecelakaan", "helm keselamatan", "materi safety", "safety", "k3"
        ]
        if _matches_any_keyword(msg_lower, pdf_keywords) and not is_pure_greeting:
            if AgentIntent.VIDEO_KNOWLEDGE not in intents or _matches_any_keyword(msg_lower, ["apd", "policy", "dokumen", "pdf", "sop"]):
                intents.append(AgentIntent.PDF_KNOWLEDGE)
                tools.append("search_pdf_knowledge")

        # 7. Content / Playlist Search & Details Intent
        if any(k in msg_lower for k in ["cari modul", "cari materi", "cari konten", "search content", "cari pelatihan", "pelatihan", "kursus"]):
            intents.append(AgentIntent.CONTENT_SEARCH)
            tools.append("search_learning_content")

        if any(k in msg_lower for k in ["cari playlist", "playlist apa saja", "daftar playlist", "training plan"]):
            intents.append(AgentIntent.PLAYLIST_SEARCH)
            tools.append("search_learning_playlist")

        if "detail modul" in msg_lower or "detail konten" in msg_lower:
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

        # 8. Remaining cases: GENERAL_CHAT vs GENERAL_LMS
        if not tools:
            if is_pure_greeting:
                intents = [AgentIntent.GENERAL_CHAT]
            elif any(k in msg_lower for k in [
                "tujuan pembelajaran", "fungsi hr corner", "materi lms", "sistem lms", "fitur lms", "portal hr"
            ]):
                intents = [AgentIntent.GENERAL_LMS]
            elif is_general_casual or any(k in msg_lower for k in [
                "apa itu", "siapa itu", "bagaimana cara", "jelaskan", "buatkan", "ai", "artificial intelligence",
                "halo", "hai", "selamat", "terima kasih", "siapa kamu", "bisa bantu"
            ]):
                intents = [AgentIntent.GENERAL_CHAT]
            else:
                intents = [AgentIntent.GENERAL_CHAT]

        # Deduplicate tools while preserving ordering
        seen = set()
        dedup_tools = [t for t in tools if not (t in seen or seen.add(t))]

        return intents, dedup_tools


intent_router = IntentRouter()
