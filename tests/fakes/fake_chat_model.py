"""Deterministic fake chat model for testing.

This fake LLM eliminates API calls, randomness, and latency from tests,
providing 50-100x speedup and fully deterministic behavior.
"""

from typing import Any, List, Optional
import json
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun


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
            import re
            user_msg_match = re.search(r'user message:\s*(.+?)(?:\s*respond with only|$)', last_message, re.IGNORECASE | re.DOTALL)
            actual_message = user_msg_match.group(1).strip() if user_msg_match else last_message

            # Check for emotional support keywords
            emotional_keywords = ["anxious", "feeling", "depressed", "sad", "stressed", "worried", "emotional",
                                 "upset", "down", "struggling", "need to talk", "need someone"]

            # Check for medical/RAG keywords
            medical_keywords = ["medication", "drug", "medicine", "treatment", "dose", "dosage",
                               "side effect", "prescription", "antidepressant", "ssri", "what is"]

            # Return PLAIN TEXT agent name
            if any(keyword in actual_message for keyword in emotional_keywords):
                agent_name = "emotional_support"
            elif any(keyword in actual_message for keyword in medical_keywords):
                agent_name = "rag_agent"
            else:
                # Default to RAG agent for generic or medical queries
                agent_name = "rag_agent"

            response = AIMessage(content=agent_name)

        elif is_rag_classification:
            # RAG classification - return "retrieve" or "respond"
            # Extract the actual user message from the classification prompt
            import re
            user_msg_match = re.search(r'user message:\s*"(.+?)"', last_message, re.IGNORECASE | re.DOTALL)
            actual_message = user_msg_match.group(1).strip() if user_msg_match else last_message

            # Check for greeting/conversational keywords
            greeting_keywords = ["thank", "thanks", "hello", "hi", "hey", "goodbye", "bye"]

            # Check for medical keywords
            medical_keywords = ["medication", "drug", "medicine", "treatment", "dose", "dosage",
                               "side effect", "prescription", "antidepressant", "ssri", "what is",
                               "how does", "tell me about", "aripiprazole", "sertraline", "lexapro"]

            # Classify (case-insensitive matching with word boundaries)
            actual_message_lower = actual_message.lower()

            # Use word boundary matching to avoid false positives (e.g., "hi" in "children")
            import re as regex_module
            matched_greeting = any(
                regex_module.search(r'\b' + re.escape(keyword) + r'\b', actual_message_lower)
                for keyword in greeting_keywords
            )
            matched_medical = any(keyword in actual_message_lower for keyword in medical_keywords)

            if matched_greeting:
                classification = "respond"
            elif matched_medical:
                classification = "retrieve"
            else:
                # Default to retrieve for safety
                classification = "retrieve"

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

            if "sertraline" in all_msg_content or "zoloft" in all_msg_content:
                response = AIMessage(
                    content="Based on the medical information: Sertraline (Zoloft) is a selective serotonin reuptake inhibitor (SSRI) antidepressant. "
                           "It is commonly used to treat depression, anxiety disorders, OCD, PTSD, and panic disorder. "
                           "The typical dosage ranges from 50-200mg daily. Common side effects may include nausea, insomnia, and dizziness. "
                           "Always consult with a healthcare provider before starting or changing medication."
                )
            elif "bupropion" in all_msg_content or "wellbutrin" in all_msg_content:
                response = AIMessage(
                    content="Based on the medical information: Bupropion (Wellbutrin) is a norepinephrine-dopamine reuptake inhibitor (NDRI) antidepressant. "
                           "It is used to treat depression and seasonal affective disorder, and also helps with smoking cessation. "
                           "The typical dosage ranges from 150-300mg daily. Common side effects may include insomnia, dry mouth, and headache."
                )
            elif "aripiprazole" in all_msg_content:
                response = AIMessage(
                    content="Based on the medical information: Aripiprazole is an antipsychotic medication used for schizophrenia and bipolar disorder. "
                           "For children, special dosing considerations apply. Always consult a pediatric psychiatrist for proper dosing and monitoring."
                )
            elif "antidepressant" in all_msg_content:
                response = AIMessage(
                    content="Antidepressants are medications used to treat depression and other mood disorders. "
                           "Common types include SSRIs (like Sertraline), SNRIs, and NDRIs (like Bupropion). "
                           "They work by adjusting neurotransmitter levels in the brain. Always work with a healthcare provider to find the right treatment."
                )
            elif "side effect" in all_msg_content:
                response = AIMessage(
                    content="Common side effects of antidepressants can include nausea, changes in appetite, sleep disturbances, and dizziness. "
                           "Most side effects are temporary and diminish as your body adjusts. If you experience severe or persistent side effects, "
                           "contact your healthcare provider."
                )
            else:
                response = AIMessage(
                    content="I can provide information about medications and mental health treatments based on the retrieved medical information. "
                           "What specific medication or treatment would you like to know about?"
                )

        # Check if this is emotional support context
        elif any("empathetic" in str(msg.content).lower() or "emotional support" in str(msg.content).lower()
                 for msg in messages if hasattr(msg, 'content')):
            # Emotional support responses
            if "anxious" in last_message or "anxiety" in last_message:
                response = AIMessage(
                    content="I understand that you're feeling anxious, and I want you to know that your feelings are completely valid. "
                           "Anxiety can be overwhelming, but you're not alone in this. Would you like to talk more about what's been causing you stress?"
                )
            elif "depressed" in last_message or "sad" in last_message:
                response = AIMessage(
                    content="I hear that you're feeling down, and I'm really sorry you're going through this. "
                           "It's important to acknowledge these feelings. Remember that it's okay to not be okay sometimes. "
                           "I'm here to listen and support you."
                )
            else:
                response = AIMessage(
                    content="I understand you're going through a difficult time. It's completely normal to feel this way. "
                           "I'm here to listen and support you. What's been on your mind?"
                )

        # Keep the original RAG check for backward compatibility
        elif any("medical" in str(msg.content).lower()
                 for msg in messages if hasattr(msg, 'content')):
            # RAG agent responses - simulate retrieval-augmented generation
            if "sertraline" in last_message or "zoloft" in last_message:
                response = AIMessage(
                    content="Based on the medical information: Sertraline (Zoloft) is a selective serotonin reuptake inhibitor (SSRI) antidepressant. "
                           "It is commonly used to treat depression, anxiety disorders, OCD, PTSD, and panic disorder. "
                           "The typical dosage ranges from 50-200mg daily. Common side effects may include nausea, insomnia, and dizziness. "
                           "Always consult with a healthcare provider before starting or changing medication."
                )
            elif "bupropion" in last_message or "wellbutrin" in last_message:
                response = AIMessage(
                    content="Based on the medical information: Bupropion (Wellbutrin) is a norepinephrine-dopamine reuptake inhibitor (NDRI) antidepressant. "
                           "It is used to treat depression and seasonal affective disorder, and also helps with smoking cessation. "
                           "The typical dosage ranges from 150-300mg daily. Common side effects may include insomnia, dry mouth, and headache."
                )
            elif "antidepressant" in last_message:
                response = AIMessage(
                    content="Antidepressants are medications used to treat depression and other mood disorders. "
                           "Common types include SSRIs (like Sertraline), SNRIs, and NDRIs (like Bupropion). "
                           "They work by adjusting neurotransmitter levels in the brain. Always work with a healthcare provider to find the right treatment."
                )
            elif "side effect" in last_message:
                response = AIMessage(
                    content="Common side effects of antidepressants can include nausea, changes in appetite, sleep disturbances, and dizziness. "
                           "Most side effects are temporary and diminish as your body adjusts. If you experience severe or persistent side effects, "
                           "contact your healthcare provider."
                )
            else:
                response = AIMessage(
                    content="I can provide information about medications and mental health treatments. "
                           "What specific medication or treatment would you like to know about?"
                )

        # Default response
        else:
            response = AIMessage(
                content="I'm here to help with medical questions and emotional support. "
                       "How can I assist you today?"
            )

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
