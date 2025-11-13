"""Singleton LLM instances for centralized access.

This module provides pre-configured singleton LLM instances that are created
at module import time. All agents and retrievers should import these instances
instead of calling create_llm() directly.

Instances:
    - response_llm: User-facing responses (temp=0.7, streaming enabled)
    - internal_llm: Internal operations (temp=1.0, streaming disabled, tagged)

Thread Safety:
    Python's module import mechanism provides built-in thread safety.
    Instances are created once at import time and shared across the application.
"""

from langchain_core.language_models import BaseChatModel

from app.llm.factory import create_llm

# Singleton instance for user-facing agent responses
# Configuration: temperature=1.0 (high creativity for diverse variations)
# Streaming: Enabled for better UX
# Tags: None
response_llm: BaseChatModel = create_llm(temperature=1.0)

# Singleton instance for internal operations (query expansion, classification)
# Configuration: temperature=1.0 (high creativity for diverse variations)
# Streaming: Disabled (unnecessary for internal operations)
# Tags: ["internal-llm"] (metadata for tracking/debugging)
internal_llm: BaseChatModel = create_llm(
    temperature=0.5,
    disable_streaming=True,
    tags=["internal-llm"]
)

__all__ = ["response_llm", "internal_llm"]
