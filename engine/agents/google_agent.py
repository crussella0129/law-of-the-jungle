"""Google (Gemini) agent wrapper."""

from __future__ import annotations
import time
from typing import Optional

import google.generativeai as genai

from .base import BaseAgent


class GoogleAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        model_id: str = "gemini-1.5-pro",
        api_key: Optional[str] = None,
    ):
        super().__init__(name, model_id)
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_id)

    def get_response(self, prompt: str) -> tuple[str, int]:
        start = time.monotonic()
        response = self.model.generate_content(prompt)
        latency_ms = int((time.monotonic() - start) * 1000)
        return response.text, latency_ms
