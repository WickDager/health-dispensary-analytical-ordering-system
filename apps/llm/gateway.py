"""
LLM Gateway — provider chain, key decryption, and invoice extraction with fallback.

The gateway builds a chain of enabled providers ordered by fallback_priority,
decrypts each provider's API key, and attempts extraction in order until one
succeeds (or all fail).
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.db.models import QuerySet

from apps.llm.adapters import ADAPTER_REGISTRY, BaseLLMAdapter
from apps.llm.models import LLMProviderConfig

logger = logging.getLogger("hdaos.llm.gateway")


class AllProvidersFailed(Exception):
    """Raised when every enabled provider has been tried and none succeeded."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"All {len(errors)} provider(s) failed.")


# ---------------------------------------------------------------------------
# Key decryption
# ---------------------------------------------------------------------------
def decrypt_key(config: LLMProviderConfig) -> str:
    """
    Decrypt the stored `encrypted_api_key` on a provider config using the
    Fernet key from Django settings (FERNET_KEY).

    If no encrypted key is stored, falls back to the matching Django setting
    (e.g. GEMINI_API_KEY) so that the gateway works in dev/test without
    database configuration.
    """
    encrypted = config.encrypted_api_key
    if encrypted:
        try:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)
            return f.decrypt(bytes(encrypted)).decode("utf-8")
        except Exception as exc:
            logger.warning("Failed to decrypt key for %s: %s", config.name, exc)

    # Fallback to settings-level key
    setting_map = {
        "gemini": "GEMINI_API_KEY",
        "claude": "CLAUDE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    key = getattr(settings, setting_map.get(config.name, ""), "") or ""
    return key


# ---------------------------------------------------------------------------
# Provider chain
# ---------------------------------------------------------------------------
def get_provider_chain() -> list[LLMProviderConfig]:
    """
    Return enabled providers ordered by fallback_priority (lowest first).
    """
    return list(
        LLMProviderConfig.objects.filter(enabled=True).order_by("fallback_priority")
    )


# ---------------------------------------------------------------------------
# Invoice extraction with fallback
# ---------------------------------------------------------------------------
def extract_invoice(text: str) -> dict:
    """
    Try each enabled provider in priority order.  Returns the first successful
    extraction dict.  Raises AllProvidersFailed if every provider fails.
    """
    chain = get_provider_chain()
    if not chain:
        raise AllProvidersFailed([{"provider": "none", "error": "No enabled providers."}])

    errors: list[dict] = []

    for config in chain:
        adapter_cls = ADAPTER_REGISTRY.get(config.name)
        if adapter_cls is None:
            errors.append({"provider": config.name, "error": "Unknown provider type."})
            continue

        try:
            api_key = decrypt_key(config)
            if not api_key:
                errors.append({"provider": config.name, "error": "No API key configured."})
                continue

            adapter: BaseLLMAdapter = adapter_cls(
                api_key=api_key,
                model=config.model,
                base_url=config.base_url or None,
            )
            result = adapter.extract_invoice(text)
            result["_provider"] = config.name
            result["_model"] = config.model
            logger.info("Invoice extraction succeeded via %s/%s", config.name, config.model)
            return result

        except Exception as exc:
            logger.warning("Provider %s failed: %s", config.name, exc)
            errors.append({"provider": config.name, "error": str(exc)})

    raise AllProvidersFailed(errors)
