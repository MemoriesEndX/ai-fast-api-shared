import difflib
import logging
from typing import Dict, List, Optional, Tuple, Any
from app.agent.intents import AgentIntent

logger = logging.getLogger("ai_service.agent.fuzzy_matcher")

# Canonical phrase dictionary mapping AgentIntent to reference phrases
INTENT_PHRASE_DICTIONARY: Dict[AgentIntent, List[str]] = {
    AgentIntent.LMS_PROGRESS: [
        "progress",
        "progress saya",
        "progress belajar",
        "progress belajar saya",
        "kemajuan belajar",
        "kemajuan belajar saya",
        "perkembangan belajar",
        "perkembangan belajar saya",
        "status pembelajaran",
        "status pembelajaran saya",
        "status belajar",
        "sudah belajar sampai mana",
        "sekarang saya sudah belajar sampai mana",
        "gimana perkembangan belajar saya",
        "bagaimana perkembangan belajar saya",
        "materi yang sedang saya pelajari",
        "progress modul",
        "kemajuan kursus",
        "berapa progress saya",
        "berapa progress belajar saya",
        "berapa kemajuan belajar saya",
    ],
    AgentIntent.LMS_PROFILE: [
        "profile",
        "profile saya",
        "profil",
        "profil saya",
        "learning profile",
        "profile belajar",
        "profil belajar",
        "data diri saya",
        "divisi saya",
        "jabatan saya",
        "posisi saya",
        "informasi profil saya",
        "biodata saya",
        "akun profil saya",
    ],
    AgentIntent.LMS_ASSESSMENT: [
        "assessment",
        "assessment saya",
        "asesmen",
        "asesmen saya",
        "hasil assessment",
        "hasil assessment saya",
        "hasil asesmen",
        "hasil asesmen saya",
        "nilai ujian",
        "nilai ujian saya",
        "skor evaluasi",
        "skor evaluasi saya",
        "hasil tes",
        "hasil tes saya",
        "hasil kuis",
        "ujian saya",
        "nilai saya",
        "hasil ujian saya bagaimana",
        "hasil ujian",
        "skor ujian",
    ],
    AgentIntent.RECOMMENDATION: [
        "rekomendasi belajar",
        "rekomendasi pembelajaran",
        "rekomendasi modul",
        "rekomendasikan pembelajaran",
        "rekomendasi pelatihan",
        "rekomendasikan modul",
        "apa yang harus saya pelajari",
        "course yang cocok",
        "materi yang sebaiknya saya pelajari",
        "belajar apa berikutnya",
        "materi selanjutnya",
        "saran belajar",
        "saran pembelajaran",
        "modul apa selanjutnya",
        "pembelajaran yang cocok",
        "prioritas belajar",
        "apa yang sebaiknya saya pelajari selanjutnya",
        "materi apa yang cocok untuk saya",
        "rekomendasikan pelatihan untuk saya",
        "course yang cocok untuk saya",
        "modul yang direkomendasikan",
    ],
    AgentIntent.PDF_KNOWLEDGE: [
        "safety induction",
        "dokumen pdf",
        "isi pdf",
        "file pdf",
        "dokumen safety",
        "aturan keselamatan",
        "kebijakan k3",
        "sop keselamatan",
        "panduan apd",
        "isi dokumen",
        "standar keselamatan",
        "ketentuan keselamatan",
        "dokumen kebijakan",
        "sop kerja",
        "isi dokumen safety induction",
        "apa isi dokumen safety induction",
        "apa isi dokumen",
        "aturan keselamatan kerja",
        "prosedur keselamatan",
        "file dokumen",
    ],
    AgentIntent.VIDEO_KNOWLEDGE: [
        "video pembelajaran",
        "transkrip video",
        "isi video",
        "materi video",
        "rekaman video",
        "video safety",
        "tonton video",
        "timestamp video",
        "durasi video",
        "rekaman webinar",
        "video training",
        "tolong jelaskan isi video safety",
        "jelaskan isi video safety",
        "transkrip video safety",
        "isi materi video",
    ],
    AgentIntent.CONTENT_SEARCH: [
        "cari modul",
        "cari materi",
        "cari konten",
        "search content",
        "cari pelatihan",
        "cari kursus",
        "temukan modul",
        "temukan materi",
        "daftar modul",
        "katalog modul",
    ],
    AgentIntent.PLAYLIST_SEARCH: [
        "cari playlist",
        "playlist apa saja",
        "daftar playlist",
        "training plan",
        "rencana pelatihan",
        "kumpulan modul",
        "daftar program pelatihan",
    ],
    AgentIntent.CONTENT_DETAIL: [
        "detail modul",
        "detail konten",
        "isi modul",
        "penjelasan modul",
        "deskripsi modul",
        "informasi detail modul",
    ],
    AgentIntent.PLAYLIST_DETAIL: [
        "detail playlist",
        "isi playlist",
        "materi dalam playlist",
        "daftar modul dalam playlist",
        "informasi detail playlist",
    ],
    AgentIntent.GENERAL_LMS: [
        "tujuan pembelajaran",
        "fungsi hr corner",
        "materi lms",
        "sistem lms",
        "fitur lms",
        "portal hr",
        "cara menggunakan lms",
    ],
}


class FuzzyIntentMatcher:
    """
    High-performance, deterministic Hybrid Fuzzy Intent Matcher.
    Uses token-set pre-indexing, SequenceMatcher ratio, n-gram sliding window matching,
    confidence scoring, and ambiguity margin evaluation.
    """

    HIGH_CONFIDENCE_THRESHOLD = 0.78
    AMBIGUITY_MARGIN = 0.08

    def __init__(self, phrase_dict: Optional[Dict[AgentIntent, List[str]]] = None):
        self.phrase_dict = phrase_dict or INTENT_PHRASE_DICTIONARY
        self._preindex_phrases()

    def _preindex_phrases(self) -> None:
        """Pre-index and tokenize dictionary phrases for optimized sub-millisecond matching."""
        self._indexed: Dict[AgentIntent, List[Dict[str, Any]]] = {}
        for intent, phrases in self.phrase_dict.items():
            self._indexed[intent] = []
            for phrase in phrases:
                tokens = phrase.split()
                self._indexed[intent].append({
                    "phrase": phrase,
                    "tokens": tokens,
                    "token_set": set(tokens),
                    "p_len": len(tokens),
                    "char_len": len(phrase),
                })

    def match_intent(
        self,
        normalized_message: str,
        threshold: float = HIGH_CONFIDENCE_THRESHOLD,
        ambiguity_margin: float = AMBIGUITY_MARGIN,
    ) -> Optional[Tuple[AgentIntent, float, str]]:
        """
        Evaluate normalized user prompt against the pre-indexed intent phrase dictionary.
        Returns (AgentIntent, confidence_score, matched_phrase) if confident and non-ambiguous,
        otherwise returns None (signaling fallback to GENERAL_CHAT).
        """
        if not normalized_message:
            return None

        q_tokens = normalized_message.split()
        q_set = set(q_tokens)
        q_len = len(q_tokens)

        intent_scores: List[Tuple[AgentIntent, float, str]] = []

        for intent, items in self._indexed.items():
            best_intent_score = 0.0
            best_phrase = ""

            for item in items:
                phrase = item["phrase"]
                p_tokens = item["tokens"]
                p_set = item["token_set"]
                p_len = item["p_len"]

                # 1. Exact string match
                if normalized_message == phrase:
                    best_intent_score = 1.0
                    best_phrase = phrase
                    break

                # 2. Exact token set containment
                exact_common = p_set.intersection(q_set)
                if len(exact_common) == p_len:
                    score = 1.0 if p_len > 1 or q_len == 1 else 0.95
                    if score > best_intent_score:
                        best_intent_score = score
                        best_phrase = phrase
                    continue

                # 3. Fuzzy token matching
                matched_tokens = len(exact_common)
                total_sim = float(matched_tokens)

                unmatched_p = [t for t in p_tokens if t not in exact_common]
                unmatched_q = [t for t in q_tokens if t not in exact_common]

                for pt in unmatched_p:
                    best_sim = 0.0
                    for qt in unmatched_q:
                        if abs(len(pt) - len(qt)) > 3:
                            continue
                        sim = difflib.SequenceMatcher(None, pt, qt).quick_ratio()
                        if sim >= 0.75:
                            sim = difflib.SequenceMatcher(None, pt, qt).ratio()
                            if sim > best_sim:
                                best_sim = sim
                    if best_sim >= 0.80:
                        matched_tokens += 1
                        total_sim += best_sim

                coverage = matched_tokens / p_len
                if coverage == 0:
                    continue

                full_ratio = difflib.SequenceMatcher(None, normalized_message, phrase).ratio()

                # Sliding window sequence match
                window_ratio = 0.0
                if q_len >= p_len:
                    for i in range(q_len - p_len + 1):
                        window = " ".join(q_tokens[i : i + p_len])
                        ratio = difflib.SequenceMatcher(None, window, phrase).quick_ratio()
                        if ratio > 0.6:
                            ratio = difflib.SequenceMatcher(None, window, phrase).ratio()
                            if ratio > window_ratio:
                                window_ratio = ratio

                if coverage >= 1.0:
                    score = max(0.85 * (total_sim / p_len), window_ratio, full_ratio)
                elif coverage >= 0.67 and p_len > 1:
                    score = max(0.75 * (total_sim / p_len), window_ratio, full_ratio)
                else:
                    score = max(window_ratio, full_ratio)

                if score > best_intent_score:
                    best_intent_score = score
                    best_phrase = phrase

            intent_scores.append((intent, best_intent_score, best_phrase))

        # Sort descending by score
        intent_scores.sort(key=lambda x: x[1], reverse=True)

        if not intent_scores:
            return None

        best_intent, best_score, best_phrase = intent_scores[0]
        second_best_score = intent_scores[1][1] if len(intent_scores) > 1 else 0.0

        # Critical False Positive Guard: Prevent "file" matching substring in "profile"
        if best_intent == AgentIntent.PDF_KNOWLEDGE:
            has_pdf_context = any(k in normalized_message for k in ["pdf", "dokumen", "safety", "sop", "k3", "aturan", "kebijakan", "panduan", "apd"])
            if not has_pdf_context:
                return None

        # 1. Confidence threshold evaluation
        if best_score < threshold:
            logger.debug(f"Fuzzy match rejected: best_score {best_score} < threshold {threshold} for intent {best_intent}")
            return None

        # 2. Ambiguity evaluation
        if (best_score - second_best_score) < ambiguity_margin and second_best_score >= (threshold - 0.05):
            logger.info(
                f"Fuzzy match ambiguous: top '{best_intent.value}' ({best_score}) vs second '{intent_scores[1][0].value}' ({second_best_score}). Falling back to GENERAL_CHAT."
            )
            return None

        return best_intent, best_score, best_phrase


fuzzy_intent_matcher = FuzzyIntentMatcher()
