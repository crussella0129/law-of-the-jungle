"""Anthropic (Claude) agent wrapper."""

from __future__ import annotations
import time
from typing import Optional

import anthropic

from .base import BaseAgent


class AnthropicAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        model_id: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
    ):
        super().__init__(name, model_id)
        self.client = anthropic.Anthropic(api_key=api_key)

    def get_response(self, prompt: str) -> tuple[str, int]:
        start = time.monotonic()
        message = self.client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return message.content[0].text, latency_ms
