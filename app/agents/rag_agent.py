"""RAG agent for medical information retrieval.

Tool-based architecture: LLM decides when to retrieve from knowledge base.
"""

import logging
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from app.retrieval import SimpleRetriever, RerankRetriever, AdvancedRetriever
from app.agents.base import create_llm
from app.utils.prompts import RAG_AGENT_PROMPT
from app.tools.medical_search import create_medical_search_tool

logger = logging.getLogger(__name__)


def create_rag_agent(retriever: SimpleRetriever | RerankRetriever | AdvancedRetriever):
    """Factory function to create RAG agent with tool-based retrieval.

    The agent uses a StateGraph pattern where the LLM can decide whether to:
    1. Call the medical_search tool to retrieve information
    2. Respond directly without retrieval (for greetings, clarifications, etc.)

    Args:
        retriever: Document retriever instance (non-serializable)

    Returns:
        Compiled LangGraph agent ready for invocation
    """
    # Create LLM
    llm = create_llm(temperature=1.0)

    # Create medical search tool with injected retriever
    medical_search_tool = create_medical_search_tool(retriever)
    tools = [medical_search_tool]

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Create tool node for executing tool calls
    tool_node = ToolNode(tools)

    async def call_model(state: MessagesState):
        """Call LLM with tools bound.

        The LLM will decide whether to call medical_search tool or respond directly.
        """
        messages = state["messages"]

        # Add system message if not present
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            messages = [SystemMessage(content=RAG_AGENT_PROMPT)] + list(messages)

        logger.debug(f"Calling LLM with {len(messages)} messages")
        response = await llm_with_tools.ainvoke(messages)

        return {"messages": [response]}

    def should_continue(state: MessagesState):
        """Determine if we should continue to tools or end.

        Returns:
            "tools" if there are tool calls to execute, END otherwise
        """
        messages = state["messages"]
        last_message = messages[-1]

        # Check if LLM made tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.debug(f"Tool calls detected: {len(last_message.tool_calls)}")
            return "tools"

        logger.debug("No tool calls, ending conversation")
        return END

    # Build the graph
    builder = StateGraph(MessagesState)

    # Add nodes
    builder.add_node("agent", call_model)
    builder.add_node("tools", tool_node)

    # Add edges
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        should_continue,
        ["tools", END]
    )
    builder.add_edge("tools", "agent")

    # Compile and return
    graph = builder.compile()
    logger.info("RAG agent compiled successfully")

    return graph
