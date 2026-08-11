import uuid
from typing import List, Dict, Any, Optional
from app.core.config import settings


class ConversationManager:
    """In-memory conversation history manager with configurable history limits."""

    def __init__(self, max_history: int = settings.CHAT_MAX_HISTORY):
        self.max_history = max_history
        self._conversations: Dict[str, List[Dict[str, str]]] = {}

    def get_or_create_conversation_id(self, conversation_id: Optional[str] = None) -> str:
        """Return existing conversation_id or generate a new unique UUID thread ID."""
        if conversation_id and conversation_id.strip():
            return conversation_id.strip()
        return f"conv_{uuid.uuid4().hex[:12]}"

    def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns for a conversation thread."""
        return self._conversations.get(conversation_id, [])

    def add_turn(self, conversation_id: str, user_message: str, assistant_response: str) -> None:
        """Append a user/assistant turn pair and trim history to max_history limit."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        history = self._conversations[conversation_id]
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_response})

        # Keep only top 2 * max_history messages (max_history user/assistant pairs)
        max_messages = self.max_history * 2
        if len(history) > max_messages:
            self._conversations[conversation_id] = history[-max_messages:]

    def clear(self, conversation_id: str) -> None:
        """Clear conversation history for a given thread ID."""
        self._conversations.pop(conversation_id, None)


# Singleton instance
conversation_manager = ConversationManager()
