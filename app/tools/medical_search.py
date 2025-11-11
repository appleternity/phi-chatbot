"""Medical knowledge base search tool for RAG agent."""

import logging
from langchain_core.tools import tool
from app.retrieval import SimpleRetriever, RerankRetriever, AdvancedRetriever
from app.config import settings

logger = logging.getLogger(__name__)


def _format_retrieved_documents(docs: list[dict]) -> str:
    """Format retrieved documents for LLM consumption.

    Args:
        docs: List of retrieved document dictionaries

    Returns:
        Markdown-formatted string with document information
    """
    if not docs:
        return "No relevant information found in the knowledge base."

    formatted = "# Retrieved Medical Information\n\n"
    for i, doc in enumerate(docs, 1):
        # Build breadcrumb for source
        source_parts = [
            doc.get("source_document"),
            doc.get("chapter_title"),
            doc.get("section_title"),
            doc.get("subsection_title"),
        ]
        source_path = " > ".join(filter(None, source_parts))
        if not source_path:
            source_path = "Unknown Source"

        formatted += f"## Source {i}: {source_path}\n\n"
        formatted += f"### Content:\n{doc.get('chunk_text', 'No content.')}\\n\n"
        formatted += "---\n\n"

    return formatted


def create_medical_search_tool(
    retriever: SimpleRetriever | RerankRetriever | AdvancedRetriever
):
    """Factory function to create medical search tool with injected retriever.

    Args:
        retriever: Document retriever instance

    Returns:
        Async tool function for medical knowledge search
    """

    @tool
    async def search_medical_knowledge(query: str) -> str:
        """Search medical knowledge base for information about medications, conditions, and treatments.

        Use this tool when you need to retrieve specific medical information from the knowledge base.
        The tool searches through medical documentation and returns relevant excerpts.

        Args:
            query: The medical question or topic to search for (e.g., "aripiprazole mechanism of action")

        Returns:
            Formatted medical information from the knowledge base
        """
        logger.info(f"Tool called with query: {query}")

        try:
            # Call retriever with query string
            # Note: Retriever will wrap this in a message internally
            docs = await retriever.search(
                query,  # Just pass the query string
                top_k=settings.top_k_documents,
            )

            logger.info(f"Retrieved {len(docs)} documents")
            return _format_retrieved_documents(docs)

        except Exception as e:
            logger.error(f"Error in medical search tool: {e}", exc_info=True)
            return f"Error searching medical knowledge base: {str(e)}"

    return search_medical_knowledge
