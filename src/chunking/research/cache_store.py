"""
DEPRECATED: This module is no longer used in production.

Moved to research/ on 2025-11-01 as part of simplification effort.
Production code now uses output-file-based skip logic instead of caching.

Kept for historical reference and potential future research needs.

---

Cache storage interfaces and implementations for chunking system.

This module provides abstraction over caching mechanisms with file-based
implementation for structure analysis results.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================================
# Abstract Interface
# ============================================================================


class CacheStore(ABC):
    """Abstract interface for cache storage"""

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data by key.

        Args:
            key: Cache key (typically content hash)

        Returns:
            Cached data dict or None if not found
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """
        Store data in cache.

        Args:
            key: Cache key (typically content hash)
            value: Data to cache (must be JSON-serializable)
        """
        pass


# ============================================================================
# File-Based Implementation
# ============================================================================


class FileCacheStore(CacheStore):
    """File-based cache implementation using JSON files with content-hash based keys"""

    def __init__(
        self,
        cache_dir: Path = Path(".cache")
    ):
        """
        Initialize file cache store.

        Args:
            cache_dir: Root directory for cache files (default: .cache)
        """
        self.cache_dir = cache_dir
        self.structures_dir = cache_dir / "structures"
        self.llm_responses_dir = cache_dir / "llm_responses"

        # Create cache directories
        self.structures_dir.mkdir(parents=True, exist_ok=True)
        self.llm_responses_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached structure by key.

        Cache is valid until document content changes (key is content hash).
        """
        cache_file = self.structures_dir / f"{key}.json"

        if cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text())
                return cached_data
            except (json.JSONDecodeError, IOError):
                # Invalid cache file, return None
                return None

        return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        """
        Store structure in cache.

        Cache persists until document content changes (key is content hash).

        Args:
            key: Cache key (content hash)
            value: Data to cache (must be JSON-serializable)
        """
        cache_file = self.structures_dir / f"{key}.json"

        try:
            cache_file.write_text(json.dumps(value, indent=2, default=str))
        except (IOError, TypeError):
            # Log error but don't fail the operation
            # Caching is optional, should not break the pipeline
            pass

    def clear(self) -> int:
        """
        Clear all cached files (structures and LLM responses).

        Returns:
            Number of files deleted
        """
        deleted_count = 0

        # Clear structure cache
        for cache_file in self.structures_dir.glob("*.json"):
            try:
                cache_file.unlink()
                deleted_count += 1
            except OSError:
                pass

        # Clear LLM response cache
        for cache_file in self.llm_responses_dir.glob("*.txt"):
            try:
                cache_file.unlink()
                deleted_count += 1
            except OSError:
                pass

        return deleted_count

    def get_llm_response(self, key: str) -> Optional[str]:
        """
        Retrieve cached raw LLM response by key.

        Args:
            key: Cache key (content hash + model + operation type)

        Returns:
            Raw LLM response text or None if not found
        """
        cache_file = self.llm_responses_dir / f"{key}.txt"

        if cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                return None

        return None

    def set_llm_response(self, key: str, response: str) -> None:
        """
        Store raw LLM response in cache.

        Args:
            key: Cache key (content hash + model + operation type)
            response: Raw LLM response text
        """
        cache_file = self.llm_responses_dir / f"{key}.txt"

        try:
            cache_file.write_text(response, encoding="utf-8")
        except (IOError, TypeError):
            # Log error but don't fail the operation
            # Caching is optional, should not break the pipeline
            pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (file_count, total_size_bytes)
        """
        structure_files = list(self.structures_dir.glob("*.json"))
        llm_response_files = list(self.llm_responses_dir.glob("*.txt"))

        structure_size = 0
        for cache_file in structure_files:
            try:
                structure_size += cache_file.stat().st_size
            except (IOError, OSError):
                continue

        llm_response_size = 0
        for cache_file in llm_response_files:
            try:
                llm_response_size += cache_file.stat().st_size
            except (IOError, OSError):
                continue

        return {
            "structure_files": len(structure_files),
            "llm_response_files": len(llm_response_files),
            "structure_size_bytes": structure_size,
            "llm_response_size_bytes": llm_response_size,
            "total_size_bytes": structure_size + llm_response_size,
            "cache_dir": str(self.cache_dir)
        }
