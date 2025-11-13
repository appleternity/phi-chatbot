"""Emotional support agent for empathetic conversation."""

import logging
from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.graph import END
from langgraph.types import Command

from app.graph.state import MedicalChatState
from app.llm import response_llm
from app.utils.prompts import EMOTIONAL_SUPPORT_PROMPT

logger = logging.getLogger(__name__)


async def emotional_support_node(state: MedicalChatState) -> Command[Literal[END]]:
    """Emotional support agent that provides empathetic conversation.

    This agent focuses on active listening and emotional validation.

    Emits stage events:
    - generation:started - Before starting response generation

    Args:
        state: Current graph state

    Returns:
        Command with agent response
    """
    # Get stream writer for emitting stage events
    writer = get_stream_writer()

    # Emit generation started
    writer({
        "type": "stage",
        "stage": "generation",
        "status": "started"
    })

    # Construct messages with system prompt
    messages = [{"role": "system", "content": EMOTIONAL_SUPPORT_PROMPT}] + state["messages"]

    logger.debug(f"Session {state['session_id']}: Emotional support agent responding")

    # Generate response (async invocation for proper streaming with astream_events)
    response = await response_llm.ainvoke(messages)

    # Return command with response
    return Command(goto=END, update={"messages": [response]})
