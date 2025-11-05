"""Supervisor agent for intent classification and routing."""

from typing import Literal
from pydantic import BaseModel, Field
from langgraph.types import Command
from app.graph.state import MedicalChatState
from app.agents.base import create_llm
from app.utils.prompts import SUPERVISOR_PROMPT
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class AgentClassification(BaseModel):
    """Structured output for agent classification."""

    agent: Literal["emotional_support", "rag_agent", "parenting"] = Field(
        description="The agent to assign based on user intent"
    )
    reasoning: str = Field(description="Brief explanation of why this agent was chosen")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in classification (0-1)"
    )


# Initialize LLM with low temperature for consistent classification
llm = create_llm(temperature=0.1)


def supervisor_node(
    state: MedicalChatState,
) -> Command[str]:
    """Supervisor agent that classifies user intent and assigns appropriate agent.

    This node only runs on the first message in a session.

    Note:
        Return type is Command[str] (not Literal) to support conditional parenting agent.
        Parenting agent routing is handled at runtime based on ENABLE_PARENTING setting.

    Args:
        state: Current graph state with user message

    Returns:
        Command with assigned agent name (one of: emotional_support, rag_agent, parenting)
    """
    # Get the last user message
    last_message = state["messages"][-1]

    # Classify with structured output
    classification = llm.with_structured_output(AgentClassification).invoke(
        SUPERVISOR_PROMPT.format(message=last_message.content)
    )

    # Log classification
    logger.info(
        f"Session {state['session_id']}: Classified as {classification.agent} "
        f"(confidence: {classification.confidence:.2f})"
    )
    logger.debug(f"Classification reasoning: {classification.reasoning}")

    # Runtime validation: fallback if parenting selected but disabled
    if classification.agent == "parenting" and not settings.ENABLE_PARENTING:
        logger.warning(
            "Parenting agent selected but disabled. Routing to emotional_support instead."
        )
        classification.agent = "emotional_support"
        classification.reasoning = (
            f"Parenting agent disabled. Providing emotional support instead. "
            f"Original reasoning: {classification.reasoning}"
        )

    # Return command with assigned agent
    return Command(
        goto=classification.agent,
        update={
            "assigned_agent": classification.agent,
            "metadata": {
                "classification_reasoning": classification.reasoning,
                "classification_confidence": classification.confidence,
            },
        },
    )
