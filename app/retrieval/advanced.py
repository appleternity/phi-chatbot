"""Advanced retrieval strategy: query expansion + search + rerank.

Most sophisticated retrieval approach using LLM query expansion.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from app.db.connection import DatabasePool
from app.retrieval.utils import extract_retrieval_query, format_conversation_context
from app.embeddings import EmbeddingProvider
from app.core.qwen3_reranker import Qwen3Reranker
from app.agents.base import create_llm

logger = logging.getLogger(__name__)


class AdvancedRetriever:
    """Advanced retrieval: query expansion + multi-query search + reranking.

    Process:
        1. LLM expands query into 3 variations
        2. Search all variations in parallel
        3. Merge and deduplicate results
        4. Rerank with Qwen3-Reranker
        5. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding provider (local/cloud)
        reranker: Qwen3-Reranker for scoring
        llm: LLM for query expansion
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: EmbeddingProvider,
        reranker: Qwen3Reranker,
        table_name: str = "vector_chunks",
    ):
        """Initialize advanced retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            reranker: Initialized reranker model
            table_name: Table name (default: "vector_chunks")
        """
        self.pool = pool
        self.encoder = encoder
        self.reranker = reranker
        self.table_name = table_name
        self.llm = create_llm(temperature=1.0, disable_streaming=True, tags=["internal-llm"])

        logger.info(f"AdvancedRetriever initialized (table={table_name}, query expansion + reranking)")

    async def expand_query(
        self,
        query: str,
        conversation_context: Optional[str] = None
    ) -> List[str]:
        """Expand query into 4 diverse variations using LLM.

        Generates 4 query variations optimized for semantic search:
        1. SPECIFIC: Technical/medical terminology variation
        2. BROADER: Contextual variation covering related topics
        3. KEYWORDS: Keyword-based variation for matching
        4. CONTEXTUAL: Variation considering conversation history

        IMPORTANT: All variations are generated in English, even if the input
        query is in Chinese, to match the English medical knowledge base.

        Args:
            query: User query (may be in Chinese or English)
            conversation_context: Optional conversation history for better context

        Returns:
            List of 4 query variation strings (all in English)
        """
        # Build expansion prompt with optional conversation context
        context_section = ""
        context_instruction = ""
        if conversation_context:
            context_section = f"""
Conversation History (for context only):
{conversation_context}

"""
            context_instruction = """
- For CONTEXTUAL variation: Consider the conversation history, but FOCUS PRIMARILY on the latest user question
- The conversation provides background context, but the latest query is the main search intent
"""

        expansion_prompt = f"""You are a medical search query optimization assistant.

{context_section}Task: Generate 4 diverse English search query variations for the following user question.

User Query: {query}

Requirements:
1. All variations MUST be in ENGLISH only (even if the user query is in Chinese)
2. Keep each variation CONCISE (under 15 words maximum)
3. Each variation should target different aspects to maximize retrieval coverage{context_instruction}

Generate these 4 variations:

1. SPECIFIC: Use precise medical/technical terminology
   - Include specific medical terms, drug names, conditions
   - Target healthcare professionals' language
   - Focus on clinical/pharmacological aspects

2. BROADER: Cover related topics and context
   - Include related conditions, categories, or concepts
   - Consider patient-friendly terminology
   - Think about "what else would someone searching this want to know?"

3. KEYWORDS: Essential keywords only (no full sentences)
   - Extract core keywords
   - Medical terms + condition terms
   - Optimized for semantic matching

4. CONTEXTUAL: Combine user intent with any conversation context
   - What is the user really trying to find out?
   - Consider implied questions from context
   - Maintain focus on the latest query

Format your response EXACTLY as:
SPECIFIC: <variation>
BROADER: <variation>
KEYWORDS: <variation>
CONTEXTUAL: <variation>

Now generate variations:"""

        # Generate variations with LLM
        response = self.llm.invoke([{"role": "user", "content": expansion_prompt}])
        response_text = response.content

        # Parse response
        queries = []

        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('SPECIFIC:'):
                specific = line.replace('SPECIFIC:', '').strip()
                if specific:
                    queries.append(specific)
            elif line.startswith('BROADER:'):
                broader = line.replace('BROADER:', '').strip()
                if broader:
                    queries.append(broader)
            elif line.startswith('KEYWORDS:'):
                keywords = line.replace('KEYWORDS:', '').strip()
                if keywords:
                    queries.append(keywords)
            elif line.startswith('CONTEXTUAL:'):
                contextual = line.replace('CONTEXTUAL:', '').strip()
                if contextual:
                    queries.append(contextual)

        # Warning if parsing failed to get all 4 variations
        if len(queries) < 4:
            logger.warning(
                f"Query expansion parsing incomplete: expected 4 variations, got {len(queries)}. "
                f"LLM response may not have followed format. Using fallback strategy."
            )
            # Fallback: use original query to fill gaps
            while len(queries) < 4:
                queries.append(query)

        logger.info(f"Expanded query into {len(queries)} variations (all English)")
        for i, q in enumerate(queries, 1):
            logger.debug(f"  {i}: {q}...")

        return queries

    async def search(
        self,
        query: List[BaseMessage],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search with query expansion and reranking.

        Args:
            query: List of conversation messages.
                   For AdvancedRetriever, uses last 5 messages to provide rich context
                   for LLM-based query expansion. This enables better understanding of
                   follow-up questions and conversational context.
            top_k: Number of final results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries sorted by rerank_score
        """
        # Extract query string from last human message
        # TODO: do we need extract_retrieval_query or format_conversation_context functions?
        # TODO: do we need to keep query_str and conversation_context separate?
        query_str = extract_retrieval_query(query, max_history=1)

        # Format last 5 messages for query expansion context (richer understanding)
        # Exclude the last message to avoid duplication with query_str
        if len(query) > 1:
            conversation_context = format_conversation_context(
                query,
                max_messages=5,
                exclude_last_n=1  # EXPLICIT: Don't duplicate the query message!
            )
        else:
            conversation_context = None

        # Validate
        assert query_str and query_str.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Advanced search: query='{query_str[:50]}...', top_k={top_k}")
        if conversation_context:
            logger.debug(f"Using conversation context with {len(conversation_context)} chars")

        # Stage 1: Expand query with conversation context
        queries = await self.expand_query(query_str, conversation_context)

        # Stage 2: Search all query variations
        all_candidates = []
        seen_chunk_ids = set()

        # TODO: Can we do it in batch
        # Let's keep it simple for now. but please keep this todo.
        for i, q in enumerate(queries, 1):
            logger.info(f"Searching with query variation {i}: {q}...")
            # Generate embedding
            query_embedding = self.encoder.encode(q).tolist()

            # Build SQL query
            sql, params = self._build_query(query_embedding, top_k, filters)

            # Execute search
            results = await self.pool.fetch(sql, *params)

            # Deduplicate by chunk_id
            for row in results:
                chunk_id = row["chunk_id"]
                if chunk_id not in seen_chunk_ids:
                    all_candidates.append(row)
                    seen_chunk_ids.add(chunk_id)

            logger.debug(f"Query {i}: found {len(results)} results")

        if not all_candidates:
            logger.warning("No candidates found from any query variation")
            return []

        logger.info(
            f"Collected {len(all_candidates)} unique candidates "
            f"from {len(queries)} query variations"
        )

        # Stage 3: Rerank all candidates with ORIGINAL query
        candidate_texts = [row["chunk_text"] for row in all_candidates]
        rerank_scores = self.reranker.rerank(query_str, candidate_texts)

        # Combine scores with candidates
        results_with_scores = []
        for row, score in zip(all_candidates, rerank_scores):
            result = {
                "chunk_id": row["chunk_id"],
                "chunk_text": row["chunk_text"],
                "source_document": row["source_document"],
                "chapter_title": row["chapter_title"],
                "section_title": row["section_title"],
                "subsection_title": row["subsection_title"],
                "summary": row["summary"],
                "token_count": row["token_count"],
                "similarity_score": float(row["similarity_score"]),
                "rerank_score": float(score),
            }
            results_with_scores.append(result)

        # Sort by rerank_score (descending)
        results_with_scores.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Take top_k
        final_results = results_with_scores[:top_k]

        logger.info(
            f"Reranked {len(all_candidates)} → {len(final_results)} results "
            f"(score range: {final_results[0]['rerank_score']:.3f} - "
            f"{final_results[-1]['rerank_score']:.3f})"
        )

        return final_results

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query (same as other retrievers)."""
        sql = f"""
        SELECT
            chunk_id,
            chunk_text,
            source_document,
            chapter_title,
            section_title,
            subsection_title,
            summary,
            token_count,
            1 - (embedding <=> $1) AS similarity_score
        FROM "{self.table_name}"
        """

        params = [embedding]
        param_index = 2

        # NOTE: what is filters here?
        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ["source_document", "chapter_title"]:
                    where_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)

        return sql, params
