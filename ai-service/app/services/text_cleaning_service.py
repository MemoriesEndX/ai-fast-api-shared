import re


class TextCleaningService:
    """Service abstraction for cleaning extracted PDF text while preserving structural context."""

    def clean_text(self, text: str) -> str:
        """Clean raw extracted PDF text while preserving structure."""
        if not text:
            return ""

        # Replace carriage returns with standard newlines
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

        # Replace 3 or more consecutive newlines with double newline (preserve paragraphs)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # Replace multiple horizontal spaces/tabs with single space (preserve line breaks)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

        # Remove page header/footer artifacts (e.g. Page 1 of 10)
        cleaned = re.sub(r"(?i)page\s+\d+\s+of\s+\d+", "", cleaned)

        # Strip surrounding whitespace from lines
        lines = [line.strip() for line in cleaned.split("\n")]
        cleaned = "\n".join(lines)

        return cleaned.strip()
