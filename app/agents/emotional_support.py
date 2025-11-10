"""Emotional support agent for empathetic conversation."""

from typing import Literal
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.agents.base import create_llm
from app.utils.prompts import EMOTIONAL_SUPPORT_PROMPT
import logging

logger = logging.getLogger(__name__)

llm = create_llm(temperature=1.0)

async def emotional_support_node(state: MedicalChatState) -> Command[Literal[END]]:
    """Emotional support agent that provides empathetic conversation.

    This agent focuses on active listening and emotional validation.

    Args:
        state: Current graph state

    Returns:
        Command with agent response
    """
    # Construct messages with system prompt
    messages = [{"role": "system", "content": EMOTIONAL_SUPPORT_PROMPT}] + state["messages"]

    logger.debug(f"Session {state['session_id']}: Emotional support agent responding")

    # Generate response (async invocation for proper streaming with astream_events)
    response = await llm.ainvoke(messages)

    # Return command with response
    return Command(goto=END, update={"messages": [response]})
