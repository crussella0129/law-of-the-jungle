"""Ollama (local model) agent wrapper — no GPU cost, useful for control agents."""

from __future__ import annotations
import time

import requests

from .base import BaseAgent


class OllamaAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        model_id: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ):
        super().__init__(name, model_id)
        self.base_url = base_url.rstrip("/")

    def get_response(self, prompt: str) -> tuple[str, int]:
        start = time.monotonic()
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model_id, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        latency_ms = int((time.monotonic() - start) * 1000)
        return response.json()["response"], latency_ms
