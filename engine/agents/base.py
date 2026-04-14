"""Abstract base class for all LLM agent wrappers."""

from __future__ import annotations
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Unified interface for any LLM backend."""

    def __init__(self, name: str, model_id: str):
        self.name = name
        self.model_id = model_id

    @abstractmethod
    def get_response(self, prompt: str) -> tuple[str, int]:
        """Send the prompt and return (raw_response_text, latency_ms)."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, model={self.model_id!r})"
