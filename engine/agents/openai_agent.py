"""OpenAI (GPT) agent wrapper."""

from __future__ import annotations
import time
from typing import Optional

import openai

from .base import BaseAgent


class OpenAIAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        model_id: str = "gpt-4o",
        api_key: Optional[str] = None,
    ):
        super().__init__(name, model_id)
        self.client = openai.OpenAI(api_key=api_key)

    def get_response(self, prompt: str) -> tuple[str, int]:
        start = time.monotonic()
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return response.choices[0].message.content, latency_ms
