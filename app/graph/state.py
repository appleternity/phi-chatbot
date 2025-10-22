"""State definitions for medical chatbot graph."""

from typing import Optional
from langgraph.graph import MessagesState


class MedicalChatState(MessagesState):
    """State for medical chatbot graph.

    Extends MessagesState with session management and agent assignment.

    Attributes:
        messages: List of messages in the conversation (inherited from MessagesState)
        session_id: Unique identifier for the conversation session
        assigned_agent: The agent assigned to handle this session
        metadata: Additional metadata for the session
    """

    session_id: str
    assigned_agent: Optional[str] = None  # "emotional_support" | "rag_agent" | None
    metadata: dict = {}
