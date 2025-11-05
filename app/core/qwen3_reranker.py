"""
Qwen3-Reranker-0.6B implementation for semantic search result reranking.

This module provides a two-stage retrieval system where pgvector similarity search
retrieves candidates, and Qwen3-Reranker improves result quality through relevance scoring.

Key Features:
- Two-stage retrieval: retrieve top_k * 4 candidates, rerank to top_k
- MPS (Apple Silicon) acceleration support
- Lazy loading for optimized startup time
- Batch processing with <2s target for 20 candidates
- Yes/no token-based relevance scoring with log_softmax normalization

References:
- Model: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- Research: specs/002-semantic-search/research.md
- Tasks: T030-T036 in specs/002-semantic-search/tasks.md
"""

import logging
from typing import List, Optional, Tuple
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)


class Qwen3Reranker:
    """
    Qwen3-Reranker-0.6B for semantic search result reranking.

    Implements yes/no token-based relevance scoring for query-document pairs.

    Architecture:
    - Causal language model (AutoModelForCausalLM)
    - Input: formatted (query, document) pairs with instruction template
    - Output: yes/no token logits → relevance scores (0.0-1.0)
    - Device: MPS (Apple Silicon) or CPU fallback
    - Precision: torch.float32 for MPS compatibility

    Performance Targets:
    - <2s processing time for 20 candidates
    - Batch size 8 for optimal throughput
    - Lazy loading to reduce startup time

    Usage:
        reranker = Qwen3Reranker(model_name="Qwen/Qwen3-Reranker-0.6B", device="mps")
        scores = reranker.rerank(query="side effects", documents=["doc1", "doc2", ...])
        # scores: [0.92, 0.87, 0.45, ...] (higher = more relevant)
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Reranker-0.6B",
        device: str = "mps",
        batch_size: int = 8,
        max_length: int = 8192
    ):
        """
        Initialize Qwen3 Reranker with model and tokenizer.

        Args:
            model_name: HuggingFace model ID (default: Qwen/Qwen3-Reranker-0.6B)
            device: Inference device - "mps", "cuda", or "cpu"
            batch_size: Batch size for reranking (default: 8)
            max_length: Maximum token length (default: 8192)
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length

        # Device configuration with fallback
        self.device = self._configure_device(device)

        # Model and tokenizer will be lazy loaded on first rerank() call
        self._model: Optional[AutoModelForCausalLM] = None
        self._tokenizer: Optional[AutoTokenizer] = None

        # Token IDs for yes/no scoring (loaded with model)
        self._token_yes_id: Optional[int] = None
        self._token_no_id: Optional[int] = None

        # Prompt template tokens (loaded with tokenizer)
        self._prefix_tokens: Optional[List[int]] = None
        self._suffix_tokens: Optional[List[int]] = None

        logger.info(
            f"Initialized Qwen3Reranker with device={self.device}, "
            f"batch_size={self.batch_size}, max_length={self.max_length}"
        )


    def _configure_device(self, device: str) -> str:
        """
        Configure and validate device with automatic fallback.

        Args:
            device: Requested device ("mps", "cuda", or "cpu")

        Returns:
            Validated device string
        """
        # MPS (Apple Silicon) support
        if device == "mps":
            if torch.backends.mps.is_available():
                logger.info("Using MPS (Apple Metal Performance Shaders) for reranking")
                return "mps"
            else:
                logger.warning("MPS requested but not available, falling back to CPU")
                return "cpu"

        # CUDA (NVIDIA GPU) support
        elif device == "cuda":
            if torch.cuda.is_available():
                logger.info(f"Using CUDA GPU for reranking: {torch.cuda.get_device_name(0)}")
                return "cuda"
            else:
                logger.warning("CUDA requested but not available, falling back to CPU")
                return "cpu"

        # CPU fallback
        elif device == "cpu":
            logger.info("Using CPU for reranking")
            return "cpu"

        else:
            logger.warning(f"Invalid device '{device}', falling back to CPU")
            return "cpu"

    def _load_model(self) -> None:
        """
        Lazy load model and tokenizer on first use.

        Loads:
        - AutoModelForCausalLM with torch.float32 for MPS compatibility
        - AutoTokenizer with left padding
        - Yes/no token IDs for relevance scoring
        - Prefix/suffix tokens for prompt template

        Raises:
            Exceptions from transformers/torch propagate naturally
        """
        if self._model is not None:
            return  # Already loaded

        logger.info(f"Loading Qwen3-Reranker model: {self.model_name}")

        # Load tokenizer with left padding for batch processing
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            padding_side='left'
        )
        logger.info("Tokenizer loaded successfully")

        # Load model with torch.float32 for MPS compatibility
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float32  # MPS requires float32 (no float16 support)
        ).to(self.device).eval()
        logger.info(f"Model loaded successfully on device: {self.device}")

        # Extract token IDs for yes/no scoring
        self._token_yes_id = self._tokenizer.convert_tokens_to_ids("yes")
        self._token_no_id = self._tokenizer.convert_tokens_to_ids("no")

        assert self._token_yes_id is not None and self._token_no_id is not None, (
            f"Failed to extract yes/no token IDs. yes={self._token_yes_id}, no={self._token_no_id}"
        )

        logger.info(f"Extracted token IDs: yes={self._token_yes_id}, no={self._token_no_id}")

        # Precompute prefix and suffix tokens for prompt template
        # Template format based on Qwen3-Reranker documentation
        prefix = (
            "<|im_start|>system\n"
            "Judge whether the Document meets the requirements based on the Query and "
            "the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."
            "<|im_end|>\n<|im_start|>user\n"
        )
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

        self._prefix_tokens = self._tokenizer.encode(prefix, add_special_tokens=False)
        self._suffix_tokens = self._tokenizer.encode(suffix, add_special_tokens=False)

        logger.info(
            f"Prefix tokens: {len(self._prefix_tokens)}, "
            f"Suffix tokens: {len(self._suffix_tokens)}"
        )

    def format_instruction(
        self,
        instruction: Optional[str],
        query: str,
        document: str
    ) -> str:
        """
        Format query-document pair with instruction template.

        Template format:
            <Instruct>: {instruction}
            <Query>: {query}
            <Document>: {document}

        Args:
            instruction: Task-specific instruction (None = default)
            query: Search query text
            document: Document text to rerank

        Returns:
            Formatted instruction string
        """
        if instruction is None:
            instruction = "Given a web search query, retrieve relevant passages that answer the query"

        return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {document}"

    @torch.no_grad()
    def rerank(
        self,
        query: str,
        documents: List[str],
        instruction: Optional[str] = None
    ) -> List[float]:
        """
        Rerank documents and return relevance scores.

        Two-stage retrieval workflow:
        1. PostgreSQL retrieves top_k * 4 candidates (e.g., 20 for top_k=5)
        2. Qwen3-Reranker scores all candidates
        3. Return top_k documents sorted by rerank_score

        Processing pipeline:
        1. Format (query, document) pairs with instruction template
        2. Tokenize with yes/no token IDs
        3. Add prefix and suffix tokens to form complete prompt
        4. Compute logits with torch.no_grad() for efficiency
        5. Extract yes/no token probabilities
        6. Apply log_softmax normalization
        7. Return relevance scores (0.0-1.0, higher = more relevant)

        Performance:
        - Target: <2s for 20 candidates
        - Batch size: 8 (configurable)
        - Device: MPS or CPU

        Args:
            query: Search query string
            documents: List of document strings to rerank
            instruction: Optional task-specific instruction

        Returns:
            List of relevance scores (0.0-1.0, same order as input documents)
            Higher score = more relevant to query

        Raises:
            Exceptions from torch/transformers propagate naturally

        Example:
            reranker = Qwen3Reranker()
            scores = reranker.rerank(
                query="side effects of aripiprazole",
                documents=["doc1 text", "doc2 text", "doc3 text"]
            )
            # scores: [0.92, 0.87, 0.45] (higher = more relevant)
        """
        assert documents, "Documents list cannot be empty"

        # Lazy load model on first call
        self._load_model()

        # Format all (query, document) pairs with instruction template
        pairs = [
            self.format_instruction(instruction, query, doc)
            for doc in documents
        ]

        # Tokenize pairs
        inputs = self._tokenizer(
            pairs,
            padding=True,
            truncation='longest_first',
            return_tensors="pt",
            max_length=self.max_length - len(self._prefix_tokens) - len(self._suffix_tokens)
        )

        # Add prefix and suffix tokens to each input
        # Final format: [prefix_tokens] + [tokenized_pair] + [suffix_tokens]
        modified_input_ids = []
        for i, ele in enumerate(inputs['input_ids']):
            modified_input_ids.append(
                self._prefix_tokens + ele.tolist() + self._suffix_tokens
            )

        # Convert back to tensor
        inputs['input_ids'] = torch.tensor(modified_input_ids, dtype=torch.long)

        # Update attention mask to match new input_ids length
        inputs['attention_mask'] = torch.ones_like(inputs['input_ids'])

        # Move to device
        for key in inputs:
            inputs[key] = inputs[key].to(self.device)

        # Compute logits with torch.no_grad() for inference efficiency
        outputs = self._model(**inputs)
        batch_logits = outputs.logits[:, -1, :]  # Last token logits (yes/no prediction)

        # Extract yes/no token probabilities
        yes_logits = batch_logits[:, self._token_yes_id]
        no_logits = batch_logits[:, self._token_no_id]

        # Stack and normalize with log_softmax
        stacked_logits = torch.stack([no_logits, yes_logits], dim=1)
        log_probs = torch.nn.functional.log_softmax(stacked_logits, dim=1)

        # Convert to probabilities (exp of log_probs)
        # Extract "yes" probabilities as relevance scores
        relevance_scores = log_probs[:, 1].exp().tolist()

        logger.debug(
            f"Reranked {len(documents)} documents. "
            f"Score range: [{min(relevance_scores):.3f}, {max(relevance_scores):.3f}]"
        )

        return relevance_scores

    def rerank_with_metadata(
        self,
        query: str,
        documents: List[str],
        instruction: Optional[str] = None
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents and return (index, score) tuples sorted by score.

        Useful for sorting documents while preserving original indices.

        Args:
            query: Search query string
            documents: List of document strings to rerank
            instruction: Optional task-specific instruction

        Returns:
            List of (original_index, relevance_score) tuples sorted by score (descending)

        Example:
            reranker = Qwen3Reranker()
            ranked = reranker.rerank_with_metadata(query, documents)
            # ranked: [(2, 0.92), (0, 0.87), (1, 0.45)]
            # Document at index 2 is most relevant with score 0.92
        """
        scores = self.rerank(query, documents, instruction)

        # Create (index, score) tuples and sort by score (descending)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        return indexed_scores

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Qwen3Reranker(model={self.model_name}, device={self.device}, "
            f"batch_size={self.batch_size}, loaded={self._model is not None})"
        )
