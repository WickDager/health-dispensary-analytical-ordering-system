"""
LLM Provider Adapters — polymorphic interface for Gemini, Claude, OpenAI, DeepSeek, OpenRouter.

Each adapter receives a decrypted API key at construction time and exposes a single
`extract_invoice(text: str) -> dict` method that returns structured JSON.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from django.conf import settings

# ---------------------------------------------------------------------------
# Shared system prompt used across all providers for invoice extraction
# ---------------------------------------------------------------------------
INVOICE_SYSTEM_PROMPT = (
    "You are a precise data-extraction assistant specialised in pharmaceutical "
    "supplier invoices.  Extract every line item from the invoice text provided "
    "by the user.  Return ONLY valid JSON conforming to this schema:\n"
    "{\n"
    '  "invoice_number": "string",\n'
    '  "invoice_date": "YYYY-MM-DD",\n'
    '  "supplier_name": "string",\n'
    '  "currency": "string (ISO 4217)",\n'
    '  "subtotal": float,\n'
    '  "tax": float,\n'
    '  "total": float,\n'
    '  "line_items": [\n'
    '    {\n'
    '      "description": "string",\n'
    '      "quantity": int,\n'
    '      "unit_price": float,\n'
    '      "line_total": float\n'
    '    }\n'
    '  ]\n'
    "}\n"
    "If any field cannot be determined, use null.  Do not include markdown "
    "fences or additional commentary — only the JSON object."
)


class BaseLLMAdapter(ABC):
    """Abstract base for all LLM provider adapters."""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @abstractmethod
    def extract_invoice(self, text: str) -> dict:
        """Send `text` to the LLM and return a parsed dict."""
        ...

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Best-effort JSON parse of an LLM response string."""
        raw = raw.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            # Remove first line (```json / ```) and last line (```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        return json.loads(raw)


# ---------------------------------------------------------------------------
# Gemini Adapter
# ---------------------------------------------------------------------------
class GeminiAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        super().__init__(api_key, model, base_url)
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(model_name=model or "gemini-2.0-flash")
        except ImportError:
            raise ImportError(
                "google-generativeai is required for Gemini.  "
                "Install it with: pip install google-generativeai"
            )

    def extract_invoice(self, text: str) -> dict:
        response = self._client.generate_content(
            contents=[
                {"role": "user", "parts": [INVOICE_SYSTEM_PROMPT + "\n\n" + text]},
            ],
            generation_config={"temperature": 0.0},
        )
        return self._parse_response(response.text)


# ---------------------------------------------------------------------------
# Claude Adapter
# ---------------------------------------------------------------------------
class ClaudeAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        super().__init__(api_key, model, base_url)
        try:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic is required for Claude.  Install it with: pip install anthropic"
            )

    def extract_invoice(self, text: str) -> dict:
        response = self._client.messages.create(
            model=self.model or "claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.0,
            system=INVOICE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        # Anthropic returns a list of content blocks; take the first text block
        raw = response.content[0].text if response.content else ""
        return self._parse_response(raw)


# ---------------------------------------------------------------------------
# OpenAI-Compatible Adapter (shared by OpenAI, DeepSeek, OpenRouter)
# ---------------------------------------------------------------------------
class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Works with any OpenAI-compatible chat-completions endpoint."""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        super().__init__(api_key, model, base_url)
        try:
            from openai import OpenAI

            client_kwargs: Dict[str, Any] = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            self._client = OpenAI(**client_kwargs)
        except ImportError:
            raise ImportError(
                "openai is required.  Install it with: pip install openai"
            )

    def extract_invoice(self, text: str) -> dict:
        response = self._client.chat.completions.create(
            model=self.model or "gpt-4o",
            messages=[
                {"role": "system", "content": INVOICE_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        raw = response.choices[0].message.content or ""
        return self._parse_response(raw)


# ---------------------------------------------------------------------------
# Adapter Registry — maps provider name -> adapter class
# ---------------------------------------------------------------------------
ADAPTER_REGISTRY: Dict[str, type] = {
    "gemini": GeminiAdapter,
    "claude": ClaudeAdapter,
    "openai": OpenAICompatibleAdapter,
    "deepseek": OpenAICompatibleAdapter,
    "openrouter": OpenAICompatibleAdapter,
}
