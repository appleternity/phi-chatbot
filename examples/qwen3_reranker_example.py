"""
Example usage of Qwen3Reranker for semantic search result reranking.

This example demonstrates:
1. Standalone reranker usage
2. Integration pattern with PostgreSQLRetriever
3. Performance benchmarking
4. Error handling

Run with: python -m examples.qwen3_reranker_example
"""

import logging
import time
from typing import List

from app.core.qwen3_reranker import Qwen3Reranker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_basic_usage():
    """Example 1: Basic reranking with standalone reranker."""
    logger.info("=== Example 1: Basic Usage ===")

    # Initialize reranker (lazy loading)
    reranker = Qwen3Reranker(device="mps", batch_size=8)
    logger.info(f"Initialized: {reranker}")

    # Sample query and documents
    query = "What are the common side effects of aripiprazole?"
    documents = [
        "Aripiprazole is an atypical antipsychotic that acts as a partial agonist at dopamine D2 receptors.",
        "Common side effects of aripiprazole include nausea, headache, dizziness, akathisia, and insomnia.",
        "The recommended starting dose of aripiprazole for adults is 10-15 mg once daily.",
        "Serious side effects may include neuroleptic malignant syndrome, tardive dyskinesia, and metabolic changes.",
        "Aripiprazole was approved by the FDA in 2002 for the treatment of schizophrenia.",
    ]

    # Rerank documents
    logger.info(f"Reranking {len(documents)} documents...")
    start = time.time()
    scores = reranker.rerank(query, documents)
    elapsed = time.time() - start

    logger.info(f"Reranking completed in {elapsed:.2f}s")

    # Display results sorted by relevance
    logger.info("\nResults (sorted by relevance):")
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    for i, (doc, score) in enumerate(ranked, 1):
        logger.info(f"{i}. Score: {score:.3f} - {doc[:80]}...")

    return scores


def example_2_with_metadata():
    """Example 2: Reranking with original indices preserved."""
    logger.info("\n=== Example 2: Rerank with Metadata ===")

    reranker = Qwen3Reranker(device="cpu")  # Use CPU for this example

    query = "medication dosing information"
    documents = [
        "Common side effects include nausea and headache.",
        "The recommended starting dose is 10-15 mg once daily.",
        "Aripiprazole is metabolized primarily by CYP2D6 and CYP3A4.",
        "Dosing adjustments are required for hepatic or renal impairment.",
    ]

    # Rerank with metadata
    ranked = reranker.rerank_with_metadata(query, documents)

    logger.info("\nResults with original indices:")
    for idx, score in ranked:
        logger.info(f"Index {idx} (score: {score:.3f}): {documents[idx][:60]}...")

    return ranked


def example_3_custom_instruction():
    """Example 3: Using custom instructions for domain-specific reranking."""
    logger.info("\n=== Example 3: Custom Instructions ===")

    reranker = Qwen3Reranker(device="mps")

    query = "side effects of aripiprazole"
    documents = [
        "Common side effects include nausea, headache, and dizziness.",
        "The mechanism of action involves dopamine D2 receptor modulation.",
        "Serious adverse effects are rare but include neuroleptic malignant syndrome.",
    ]

    # Default instruction
    logger.info("Using default instruction...")
    scores_default = reranker.rerank(query, documents)

    # Custom medical instruction
    custom_instruction = "Retrieve detailed medical information about medication adverse effects and safety profiles"
    logger.info(f"Using custom instruction: '{custom_instruction}'")
    scores_custom = reranker.rerank(query, documents, instruction=custom_instruction)

    # Compare results
    logger.info("\nComparison:")
    for i, (doc, score_def, score_cust) in enumerate(zip(documents, scores_default, scores_custom)):
        logger.info(
            f"{i+1}. Default: {score_def:.3f}, Custom: {score_cust:.3f} - {doc[:50]}..."
        )

    return scores_default, scores_custom


def example_4_device_fallback():
    """Example 4: Device fallback demonstration."""
    logger.info("\n=== Example 4: Device Fallback ===")

    # Try different devices
    devices_to_test = ["mps", "cuda", "cpu"]

    for device in devices_to_test:
        logger.info(f"\nAttempting to initialize with device: {device}")
        reranker = Qwen3Reranker(device=device, batch_size=8)
        logger.info(f"Successfully initialized on: {reranker.device}")
        if reranker.device != device:
            logger.warning(f"Fallback occurred: requested {device}, got {reranker.device}")
        break  # Only test first available device

    return reranker


def example_5_performance_benchmark():
    """Example 5: Performance benchmarking for different configurations."""
    logger.info("\n=== Example 5: Performance Benchmark ===")

    query = "medication side effects"
    documents = [
        f"Document {i}: This is sample medical text about medication effects."
        for i in range(20)  # 20 documents for realistic benchmark
    ]

    configs = [
        ("MPS, batch=8", "mps", 8),
        ("CPU, batch=8", "cpu", 8),
        ("CPU, batch=4", "cpu", 4),
    ]

    results = []
    for name, device, batch_size in configs:
        reranker = Qwen3Reranker(device=device, batch_size=batch_size)

        # Warmup (loads model)
        logger.info(f"Warming up {name}...")
        _ = reranker.rerank(query, documents[:5])

        # Benchmark
        logger.info(f"Benchmarking {name}...")
        start = time.time()
        scores = reranker.rerank(query, documents)
        elapsed = time.time() - start

        target_met = "✅" if elapsed < 2.0 else "⚠️"
        logger.info(f"{target_met} {name}: {elapsed:.2f}s ({len(documents)} docs)")
        results.append((name, elapsed))

    return results


def example_6_integration_pattern():
    """Example 6: Integration pattern for PostgreSQLRetriever."""
    logger.info("\n=== Example 6: Integration Pattern ===")

    logger.info("This example shows the integration pattern for PostgreSQLRetriever:")

    code = """
from app.core.qwen3_reranker import Qwen3Reranker
from app.core.retriever import DocumentRetriever, Document
from typing import List, Optional

class PostgreSQLRetriever(DocumentRetriever):
    def __init__(
        self,
        db_url: str,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
        reranker_model: str = "Qwen/Qwen3-Reranker-0.6B",
        use_reranking: bool = True
    ):
        self.use_reranking = use_reranking
        self._reranker: Optional[Qwen3Reranker] = None
        self.reranker_model_name = reranker_model

    @property
    def reranker(self) -> Qwen3Reranker:
        '''Lazy load reranker on first use.'''
        if self._reranker is None:
            self._reranker = Qwen3Reranker(
                model_name=self.reranker_model_name,
                device="mps",
                batch_size=8
            )
        return self._reranker

    async def search(self, query: str, top_k: int = 5) -> List[Document]:
        '''Two-stage semantic search with reranking.'''
        # Stage 1: Retrieve candidates (4x oversampling)
        candidate_count = top_k * 4 if self.use_reranking else top_k
        candidates = await self._vector_search(query, top_k=candidate_count)

        # Stage 2: Rerank
        if self.use_reranking and len(candidates) > top_k:
            texts = [doc.content for doc in candidates]
            rerank_scores = self.reranker.rerank(query, texts)

            # Add rerank scores to metadata
            for doc, score in zip(candidates, rerank_scores):
                doc.metadata['rerank_score'] = float(score)

            # Sort by rerank_score (highest first)
            candidates.sort(key=lambda d: d.metadata['rerank_score'], reverse=True)

        return candidates[:top_k]
"""

    logger.info(code)


def main():
    """Run all examples."""
    logger.info("Starting Qwen3Reranker examples...\n")

    try:
        # Example 1: Basic usage
        example_1_basic_usage()

        # Example 2: With metadata
        example_2_with_metadata()

        # Example 3: Custom instructions
        example_3_custom_instruction()

        # Example 4: Device fallback
        example_4_device_fallback()

        # Example 5: Performance benchmark
        example_5_performance_benchmark()

        # Example 6: Integration pattern
        example_6_integration_pattern()

        logger.info("\n" + "="*60)
        logger.info("✅ All examples completed successfully!")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"\n✗ Example failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
