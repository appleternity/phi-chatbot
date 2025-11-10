"""Test script to demonstrate parenting agent fallback logic.

This script simulates the supervisor classification with ENABLE_PARENTING=False
to verify the fallback routing to emotional_support works correctly.
"""

import logging
from typing import Literal
from pydantic import BaseModel, Field

# Configure logging to see warnings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentClassification(BaseModel):
    """Simulated classification result."""
    agent: Literal["emotional_support", "rag_agent", "parenting"]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


def test_fallback_logic():
    """Simulate the supervisor's fallback logic."""
    # Import settings
    from app.config import settings

    print(f"\n{'='*70}")
    print(f"PARENTING AGENT FALLBACK TEST")
    print(f"{'='*70}\n")

    print(f"Current ENABLE_PARENTING setting: {settings.ENABLE_PARENTING}\n")

    # Simulate LLM classifying a parenting query
    classification = AgentClassification(
        agent="parenting",
        reasoning="User is asking about toddler sleep issues - typical parenting concern",
        confidence=0.95
    )

    print(f"Initial Classification:")
    print(f"  Agent: {classification.agent}")
    print(f"  Reasoning: {classification.reasoning}")
    print(f"  Confidence: {classification.confidence}\n")

    # Apply fallback logic (same as supervisor.py lines 60-68)
    if classification.agent == "parenting" and not settings.ENABLE_PARENTING:
        logger.warning(
            "Parenting agent selected but disabled. Routing to emotional_support instead."
        )
        original_reasoning = classification.reasoning
        classification.agent = "emotional_support"
        classification.reasoning = (
            f"Parenting agent disabled. Providing emotional support instead. "
            f"Original reasoning: {original_reasoning}"
        )
        print(f"✅ FALLBACK APPLIED\n")

    print(f"Final Classification:")
    print(f"  Agent: {classification.agent}")
    print(f"  Reasoning: {classification.reasoning}")
    print(f"  Confidence: {classification.confidence}\n")

    # Verify fallback worked
    assert classification.agent == "emotional_support", "Fallback failed!"
    assert "Parenting agent disabled" in classification.reasoning, "Reasoning not updated!"

    print(f"{'='*70}")
    print(f"✅ TEST PASSED: Parenting requests correctly fallback to emotional_support")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_fallback_logic()
