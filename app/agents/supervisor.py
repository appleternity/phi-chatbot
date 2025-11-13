"""Supervisor agent for intent classification and routing."""

import logging
from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.types import Command

from app.config import settings
from app.graph.state import MedicalChatState
from app.llm import response_llm, internal_llm
from app.utils.prompts import SUPERVISOR_PROMPT
from app.utils.text_utils import normalize_llm_output

logger = logging.getLogger(__name__)

# Valid agent names
VALID_AGENTS: set[Literal["emotional_support", "rag_agent"]] = {
    "emotional_support",
    "rag_agent",
}


def supervisor_node(
    state: MedicalChatState,
) -> Command[str]:
    """Supervisor agent that classifies user intent and assigns appropriate agent.

    This node only runs on the first message in a session.

    Emits stage events:
    - routing:started - When classification begins
    - routing:complete - When agent is assigned (includes assigned_agent metadata)

    Args:
        state: Current graph state with user message

    Returns:
        Command with assigned agent name (one of: emotional_support, rag_agent)

    Raises:
        ValueError: If LLM returns invalid agent name
    """
    # Get stream writer for emitting stage events
    writer = get_stream_writer()

    # Emit routing started
    writer({"type": "stage", "stage": "routing", "status": "started"})

    # Get the last user message
    last_message = state["messages"][-1]

    # Invoke LLM for classification (plain string output)
    response = internal_llm.invoke(SUPERVISOR_PROMPT.format(message=last_message.content))
    agent_name = normalize_llm_output(response.content)

    # Validate agent name
    if agent_name not in VALID_AGENTS:
        logger.error(
            f"Session {state['session_id']}: Invalid agent '{agent_name}' returned by supervisor. "
            f"Expected one of: {VALID_AGENTS}"
        )
        raise ValueError(
            f"Invalid agent classification: '{agent_name}'. "
            f"Must be one of: {', '.join(VALID_AGENTS)}"
        )

    # Log classification
    logger.info(f"Session {state['session_id']}: Classified as '{agent_name}'")

    # Emit routing complete with assigned agent
    writer({
        "type": "stage",
        "stage": "routing",
        "status": "complete",
        "metadata": {"assigned_agent": agent_name}
    })

    # Return command with assigned agent
    return Command(
        goto=agent_name,
        update={"assigned_agent": agent_name},
    )
