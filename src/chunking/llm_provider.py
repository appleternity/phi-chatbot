"""
LLM provider interfaces and implementations for chunking system.

This module provides abstraction over LLM APIs with concrete implementations
for OpenRouter and testing.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests

from .models import LLMProviderError


# ============================================================================
# Abstract Interface
# ============================================================================


class LLMProvider(ABC):
    """Abstract interface for LLM providers"""

    @abstractmethod
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Request chat completion from LLM.

        Args:
            model: Model identifier (e.g., "openai/gpt-4o")
            messages: List of message dicts with "role" and "content"
            **kwargs: Additional provider-specific parameters

        Returns:
            Response dict with standard OpenAI-compatible format

        Raises:
            LLMProviderError: If API call fails
        """
        pass


# ============================================================================
# OpenRouter Implementation
# ============================================================================


class OpenRouterProvider(LLMProvider):
    """OpenRouter API implementation"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        enable_prompt_caching: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: API base URL (default: https://openrouter.ai/api/v1)
            enable_prompt_caching: Enable prompt caching via Cache-Control headers
            cache_ttl: Cache TTL in seconds (default: 3600 = 1 hour)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.enable_prompt_caching = enable_prompt_caching
        self.cache_ttl = cache_ttl

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Request chat completion from OpenRouter API"""

        # TODO: check how caching works on OpenRouter side

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Add prompt caching headers if enabled
        if self.enable_prompt_caching:
            headers["Cache-Control"] = f"max-age={self.cache_ttl}"

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60  # 60 second timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            error_detail = ""

            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("error", {}).get("message", str(e))
                except Exception:
                    error_detail = e.response.text or str(e)

            raise LLMProviderError(
                f"OpenRouter API error (HTTP {status_code}): {error_detail}"
            ) from e

        except requests.exceptions.Timeout as e:
            raise LLMProviderError(
                "OpenRouter API timeout after 60 seconds"
            ) from e

        except requests.exceptions.RequestException as e:
            raise LLMProviderError(
                f"OpenRouter API request failed: {str(e)}"
            ) from e

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error calling OpenRouter API: {str(e)}"
            ) from e


# ============================================================================
# Mock Implementation (for Testing)
# ============================================================================


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing"""

    def __init__(self, responses: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize mock provider.

        Args:
            responses: Dict mapping model names to mock responses
                      Format: {"model_name": {"choices": [{"message": {"content": "..."}}]}}
        """
        self.responses = responses or {}
        self.call_history: List[Dict[str, Any]] = []

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Return mock response"""

        # Record call for testing
        self.call_history.append({
            "model": model,
            "messages": messages,
            "kwargs": kwargs
        })

        # Return mock response if available
        if model in self.responses:
            return self.responses[model]

        # Default mock response
        return {
            "id": "mock-response-id",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Mock response content"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }

    def add_response(self, model: str, response: Dict[str, Any]):
        """Add a mock response for a specific model"""
        self.responses[model] = response

    def clear_history(self):
        """Clear call history"""
        self.call_history = []
