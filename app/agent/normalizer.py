import re
import unicodedata
from typing import Dict, List

# Common Indonesian chat slang / abbreviations dictionary for intent normalization
INDONESIAN_CHAT_EXPANSIONS: Dict[str, str] = {
    "brp": "berapa",
    "brapa": "berapa",
    "bljr": "belajar",
    "bljar": "belajar",
    "sy": "saya",
    "aq": "saya",
    "ak": "saya",
    "gw": "saya",
    "gua": "saya",
    "gue": "saya",
    "gmn": "gimana",
    "gmnnya": "gimana",
    "bgm": "bagaimana",
    "bgmn": "bagaimana",
    "sdh": "sudah",
    "udh": "sudah",
    "uda": "sudah",
    "dah": "sudah",
    "dgn": "dengan",
    "utk": "untuk",
    "kpd": "kepada",
    "bgt": "banget",
    "bgtu": "begitu",
    "rekom": "rekomendasi",
    "rekomendasiin": "rekomendasi",
    "rekomendasiinnya": "rekomendasi",
    "rekomended": "rekomendasi",
    "recomended": "rekomendasi",
    "recomend": "rekomendasi",
    "recommend": "rekomendasi",
    "vidio": "video",
    "vdo": "video",
    "dok": "dokumen",
    "doc": "dokumen",
    "assestment": "assessment",
    "asesment": "assessment",
    "asessment": "assessment",
    "assesment": "assessment",
    "asesmen": "assessment",
    "profle": "profile",
    "profl": "profile",
    "profil": "profile",
    "prog": "progress",
    "progres": "progress",
    "progess": "progress",
    "proggress": "progress",
    "transkip": "transkrip",
    "trims": "terima kasih",
    "tq": "terima kasih",
    "makasi": "terima kasih",
    "makasih": "terima kasih",
    "tks": "terima kasih",
    "thx": "terima kasih",
    "thanks": "terima kasih",
    "thnx": "terima kasih",
}


class IntentNormalizer:
    """
    Lightweight, deterministic text normalizer for intent routing.
    Performs safe normalization without altering semantic context:
    - Unicode normalization & lowercasing
    - Stripping disruptive punctuation while preserving word boundaries
    - Collapsing repeated identical characters (e.g., 'halooo' -> 'halo', 'progrrrres' -> 'progres')
    - Expanding standard Indonesian informal chat abbreviations & contractions
    - Collapsing redundant whitespace
    """

    @staticmethod
    def collapse_repeated_chars(word: str) -> str:
        """
        Collapses consecutive identical characters of 3 or more down to 1.
        E.g., 'halooo' -> 'halo', 'progrrrres' -> 'progres', 'yessss' -> 'yes'.
        """
        collapsed = re.sub(r"(.)\1{2,}", r"\1", word)
        return collapsed

    @classmethod
    def normalize(cls, text: str) -> str:
        """
        Normalize raw user prompt string for deterministic intent matching.
        """
        if not text:
            return ""

        # 1. Unicode normalization (NFKD) and lowercasing
        normalized = unicodedata.normalize("NFKD", text).lower().strip()

        # 2. Handle repeated words with '2' suffix (e.g. 'modul2' -> 'modul modul')
        normalized = re.sub(r"\b([a-zA-Z]+)2\b", r"\1 \1", normalized)

        # 3. Replace non-alphanumeric chars (except whitespace and hyphens) with spaces
        normalized = re.sub(r"[^\w\s\-]", " ", normalized)

        # 4. Token-by-token normalization
        tokens = normalized.split()
        normalized_tokens: List[str] = []

        for tok in tokens:
            # Strip remaining edge hyphens
            clean_tok = tok.strip("-")
            if not clean_tok:
                continue

            # Collapse repeating characters (e.g., 'halooo' -> 'halo')
            collapsed_tok = cls.collapse_repeated_chars(clean_tok)

            # Check Indonesian slang / abbreviation dictionary
            expanded_tok = INDONESIAN_CHAT_EXPANSIONS.get(collapsed_tok, INDONESIAN_CHAT_EXPANSIONS.get(clean_tok, collapsed_tok))
            normalized_tokens.append(expanded_tok)

        # 5. Join and collapse multiple spaces
        result = " ".join(normalized_tokens)
        return result


intent_normalizer = IntentNormalizer()
