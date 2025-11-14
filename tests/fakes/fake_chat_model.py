"""Deterministic fake chat model for testing.

This fake LLM eliminates API calls, randomness, and latency from tests,
providing 50-100x speedup and fully deterministic behavior.
"""

from typing import Any, List, Optional
import json
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

from tests.fakes.response_registry import RESPONSE_PATTERNS


class FakeChatModel(BaseChatModel):
    """Deterministic fake chat model for testing.

    Returns predefined responses based on input message patterns.
    This eliminates:
    - API calls (50-100x faster)
    - Randomness (fully deterministic)
    - API costs (zero cost)
    - Network dependency (offline testing)

    Usage:
        llm = FakeChatModel()
        response = llm.invoke([HumanMessage(content="I'm feeling anxious")])
    """

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate deterministic response based on input patterns."""
        # Debug: Print messages to understand structure (disabled)
        # print(f"DEBUG FakeChatModel received {len(messages)} messages")
        # for i, msg in enumerate(messages):
        #     content_preview = msg.content[:200] if hasattr(msg, 'content') else 'N/A'
        #     print(f"  Message {i}: type={type(msg).__name__}, content={content_preview}...")

        last_message = messages[-1].content.lower() if hasattr(messages[-1], 'content') else ""

        # Check if this is a classification request
        # Patterns:
        # 1. Supervisor: "supervisor", "agent", "emotional_support or rag_agent"
        # 2. RAG classification: "classify", "categories", "retrieve or respond"
        all_content = " ".join(str(msg.content).lower() for msg in messages if hasattr(msg, 'content'))
        is_supervisor_classification = (("supervisor" in all_content or "agent" in all_content) and
                                        ("emotional_support" in all_content or "rag_agent" in all_content))
        is_rag_classification = ("classify" in all_content and "categories" in all_content and
                                 ("retrieve" in all_content or "respond" in all_content))

        if is_supervisor_classification:
            # Supervisor classification - return PLAIN TEXT (emotional_support or rag_agent)
            # Extract the actual user message from the supervisor prompt
            # Format: "...User message: <actual message>\n\nRespond with ONLY..."
            user_msg_match = re.search(r'user message:\s*(.+?)(?:\s*respond with only|$)', last_message, re.IGNORECASE | re.DOTALL)
            actual_message = user_msg_match.group(1).strip() if user_msg_match else last_message

            # Use keywords from response registry
            supervisor_patterns = RESPONSE_PATTERNS["supervisor_classification"]
            emotional_keywords = supervisor_patterns["emotional_keywords"]
            medical_keywords = supervisor_patterns["medical_keywords"]

            # Return PLAIN TEXT agent name
            if any(keyword in actual_message for keyword in emotional_keywords):
                agent_name = "emotional_support"
            elif any(keyword in actual_message for keyword in medical_keywords):
                agent_name = "rag_agent"
            else:
                # Default to RAG agent for generic or medical queries
                agent_name = supervisor_patterns["default_agent"]

            response = AIMessage(content=agent_name)

        elif is_rag_classification:
            # RAG classification - return "retrieve" or "respond"
            # Extract the actual user message from the classification prompt
            user_msg_match = re.search(r'user message:\s*"(.+?)"', last_message, re.IGNORECASE | re.DOTALL)
            actual_message = user_msg_match.group(1).strip() if user_msg_match else last_message

            # Use keywords from response registry
            rag_patterns = RESPONSE_PATTERNS["rag_classification"]
            greeting_keywords = rag_patterns["greeting_keywords"]
            medical_keywords = rag_patterns["medical_keywords"]

            # Classify (case-insensitive matching with word boundaries)
            actual_message_lower = actual_message.lower()

            # Use word boundary matching to avoid false positives (e.g., "hi" in "children")
            matched_greeting = any(
                re.search(r'\b' + re.escape(keyword) + r'\b', actual_message_lower)
                for keyword in greeting_keywords
            )
            matched_medical = any(keyword in actual_message_lower for keyword in medical_keywords)

            if matched_greeting:
                classification = "respond"
            elif matched_medical:
                classification = "retrieve"
            else:
                # Default to retrieve for safety
                classification = rag_patterns["default"]

            response = AIMessage(content=classification)

        # Check if this is RAG/medical context (includes retrieved information)
        # IMPORTANT: This must come BEFORE emotional support check!
        elif any("retrieved information" in str(msg.content).lower() or
                 "based on the retrieved information" in str(msg.content).lower() or
                 "conversation context" in str(msg.content).lower() or
                 "user question" in str(msg.content).lower()
                 for msg in messages if hasattr(msg, 'content')):
            # RAG agent responses - simulate retrieval-augmented generation
            # Check what the query is about by looking at all messages
            all_msg_content = " ".join(str(msg.content).lower() for msg in messages if hasattr(msg, 'content'))

            # Use medical responses from response registry
            medical_responses = RESPONSE_PATTERNS["medical_responses"]

            # Check for medication keywords in priority order
            response_content = None
            for keyword, response_text in medical_responses.items():
                if keyword != "default" and keyword in all_msg_content:
                    response_content = response_text
                    break

            # Default response if no specific match
            if response_content is None:
                response_content = medical_responses["default"]

            response = AIMessage(content=response_content)

        # Check if this is emotional support context
        elif any("empathetic" in str(msg.content).lower() or "emotional support" in str(msg.content).lower()
                 for msg in messages if hasattr(msg, 'content')):
            # Emotional support responses - use response registry
            emotional_responses = RESPONSE_PATTERNS["emotional_responses"]

            # Check for emotional keywords
            response_content = None
            for keyword, response_text in emotional_responses.items():
                if keyword != "default" and keyword in last_message:
                    response_content = response_text
                    break

            # Default response if no specific match
            if response_content is None:
                response_content = emotional_responses["default"]

            response = AIMessage(content=response_content)

        # Keep the original RAG check for backward compatibility
        elif any("medical" in str(msg.content).lower()
                 for msg in messages if hasattr(msg, 'content')):
            # RAG agent responses - simulate retrieval-augmented generation
            # Use medical responses from response registry
            medical_responses = RESPONSE_PATTERNS["medical_responses"]

            # Check for medication keywords
            response_content = None
            for keyword, response_text in medical_responses.items():
                if keyword != "default" and keyword in last_message:
                    response_content = response_text
                    break

            # Default response if no specific match
            if response_content is None:
                response_content = medical_responses["default"]

            response = AIMessage(content=response_content)

        # Default response
        else:
            default_responses = RESPONSE_PATTERNS["default_responses"]
            response = AIMessage(content=default_responses["general"])

        generation = ChatGeneration(message=response)
        return ChatResult(generations=[generation])

    def bind_tools(self, tools, **kwargs):
        """Bind tools to the model.

        For FakeChatModel, we just return self since tool execution is simulated.
        This prevents NotImplementedError when agents use llm.bind_tools().

        Args:
            tools: Sequence of tools to bind to the model.
            **kwargs: Additional arguments (ignored for fake model).

        Returns:
            Self for method chaining.
        """
        return self

    def with_structured_output(self, schema, **kwargs):
        """Return a runnable that parses output to match the given schema.

        For FakeChatModel, this creates a wrapper that parses the JSON response
        into the specified Pydantic model or dict schema.

        Args:
            schema: The output schema (Pydantic class, TypedDict, or dict).
            **kwargs: Additional arguments (ignored for fake model).

        Returns:
            Runnable that returns structured output.
        """
        from typing import Any as TypingAny
        from pydantic import BaseModel

        original_generate = self._generate

        def parse_json_to_model(result):
            """Parse JSON response into Pydantic model."""
            # Get the last message content (should be JSON)
            last_message = result.generations[0].message
            content = last_message.content

            # Parse JSON string to dict
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, return None
                return None

            # If schema is a Pydantic model, instantiate it
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                return schema(**data)
            else:
                # Otherwise return the dict
                return data

        # Create a wrapper runnable
        class StructuredOutputRunnable:
            def __init__(self, llm):
                self.llm = llm

            def invoke(self, input: TypingAny, config: Any = None) -> Any:
                # Call original generate
                result = self.llm.invoke(input, config=config)
                # Parse to structured output
                content = result.content if hasattr(result, 'content') else str(result)
                try:
                    data = json.loads(content)
                    if isinstance(schema, type) and issubclass(schema, BaseModel):
                        return schema(**data)
                    return data
                except:
                    return None

        return StructuredOutputRunnable(self)

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM type."""
        return "fake-chat-model"
