from typing import List, Dict, Any, Tuple
from app.services.prompt_service import PromptService


class RAGPromptService:
    """Service abstraction for formatting RAG prompts with retrieved context chunks."""

    def __init__(self, prompt_service: PromptService = None):
        self.prompt_service = prompt_service or PromptService()

    def build_rag_prompt(
        self,
        application: str,
        user_message: str,
        context_chunks: List[Dict[str, Any]],
        max_context_chars: int = 2500,
    ) -> Tuple[str, str]:
        """Build system instruction and context-augmented user prompt."""
        base_system = self.prompt_service.get_system_prompt(application)

        rag_system = (
            f"{base_system}\n\n"
            "STRICT INSTRUCTION: Answer the user question using ONLY the provided CONTEXT below. "
            "If the answer cannot be found or deduced from the context, clearly state: "
            "\"Informasi tersebut tidak ditemukan dalam materi yang tersedia.\" "
            "Do NOT invent, hallucinate, or extrapolate facts outside the provided context."
        )

        if not context_chunks:
            return rag_system, user_message

        # Assemble retrieved context chunks while respecting token/char length limits
        context_blocks = []
        current_len = 0

        for chunk in context_chunks:
            title = chunk.get("title", "Document")
            idx = chunk.get("chunk_index", 0)
            text = chunk.get("text", "").strip()

            block = f"[Source: {title} | Chunk {idx}]\n{text}"
            if current_len + len(block) > max_context_chars:
                break

            context_blocks.append(block)
            current_len += len(block)

        joined_context = "\n\n".join(context_blocks)

        augmented_user_prompt = (
            f"CONTEXT:\n"
            f"---------------------\n"
            f"{joined_context}\n"
            f"---------------------\n\n"
            f"USER QUESTION: {user_message}"
        )

        return rag_system, augmented_user_prompt
