"""
Celery tasks for AI-powered invoice ingestion.
"""

from __future__ import annotations

import base64
import logging
import time
import uuid

from celery import shared_task
from django.utils import timezone

from apps.ingest.services import commit_ingestion
from apps.audit.models import AIIngestAudit
from apps.llm.gateway import extract_invoice, AllProvidersFailed
from apps.llm.models import LLMProviderConfig
from apps.llm.schemas import InvoiceExtraction

logger = logging.getLogger("hdaos.ingest.tasks")


def _extract_text_from_image(image_data: bytes) -> str:
    """
    Send an image to an LLM provider that supports vision (currently OpenAI and
    Anthropic Claude) for OCR / text extraction.  DeepSeek does not support
    image inputs, so it is skipped.
    """
    import sys as _sys
    VISION_PROVIDERS = {"openai", "claude", "gemini", "openrouter"}

    try:
        config = LLMProviderConfig.objects.filter(enabled=True, name__in=VISION_PROVIDERS).order_by("fallback_priority").first()
        print("[VISION] Checking for vision provider...", file=_sys.stderr)
        if not config:
            print("[VISION] No vision-capable provider enabled", file=_sys.stderr)
            return ""

        print(f"[VISION] Found provider: {config.name} / {config.model}", file=_sys.stderr)

        from apps.llm.gateway import decrypt_key

        api_key = decrypt_key(config)
        print(f"[VISION] API key length: {len(api_key) if api_key else 0}", file=_sys.stderr)
        if not api_key:
            print(f"[VISION] No API key for {config.name}", file=_sys.stderr)
            return ""

        b64 = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"

        if config.name in ("openai", "openrouter"):
            from openai import OpenAI

            base_url = (config.base_url or "https://api.openai.com").rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            print(f"[VISION] Creating client with base_url={base_url}, model={config.model}", file=_sys.stderr)
            client = OpenAI(api_key=api_key, base_url=base_url)
            print(f"[VISION] Sending vision request to {config.name}/{config.model}...", file=_sys.stderr)
            response = client.chat.completions.create(
                model=config.model or "gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract ALL visible text from this invoice image. Return raw text exactly as seen.",
                            },
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                max_tokens=4096,
                temperature=0.0,
            )
            content = response.choices[0].message.content or ""
            print(f"[VISION] Got response: {len(content)} chars", file=_sys.stderr)
            print(f"[VISION] First 100 chars: {content[:100]}", file=_sys.stderr)
            return content

        elif config.name == "claude":
            try:
                from anthropic import Anthropic
            except ImportError:
                logger.warning("anthropic package not installed")
                return ""
            client = Anthropic(api_key=api_key)
            import base64 as b64mod
            response = client.messages.create(
                model=config.model or "claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract ALL visible text from this invoice image. Return raw text."},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                        ],
                    }
                ],
            )
            content = response.content[0].text if response.content else ""
            logger.info("Vision extraction returned %d chars", len(content))
            return content

        else:
            logger.warning("Vision extraction not implemented for %s", config.name)
            return ""

    except Exception:
        logger.exception("Vision extraction failed")
        return ""


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def process_invoice(self, *, text: str, doc_type: str = "supplier_invoice", is_image: bool = False, user_id: str | None = None) -> dict:
    """
    Celery task: send invoice text through the LLM gateway, validate the
    output with Pydantic, write an AIIngestAudit record, and return the
    validated extraction.

    On failure the task retries once after 60 seconds, then gives up.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    start = time.monotonic()
    provider = "unknown"
    model = "unknown"
    raw_output = {}
    validated_output = None
    succeeded = False
    latency_ms = 0
    error_detail = None

    # Celery task id; falls back to a generated UUID when the task runs
    # synchronously (broker unavailable), so status polling always works
    # (the per-task URL route only accepts UUIDs).
    task_id = getattr(self.request, "id", None) or str(uuid.uuid4())

    try:
        # ----- Image input: run vision-based text extraction first -----------------
        if is_image:
            logger.info("Image input detected — running vision extraction")
            extracted_text = _extract_text_from_image(text.encode("latin-1"))
            if extracted_text:
                text = extracted_text
            else:
                logger.warning("Vision extraction returned empty, falling back to raw input")

        # ----- Extract via gateway (returns dict) --------------------------------
        result = extract_invoice(text)
        raw_output = result
        provider = result.get("_provider", "unknown")
        model = result.get("_model", "unknown")

        # ----- Pydantic validation ------------------------------------------------
        validated = InvoiceExtraction(**result)
        validated_output = validated.model_dump(mode="json")
        succeeded = True

    except AllProvidersFailed as exc:
        raw_output = {"errors": exc.errors}
        error_detail = str(exc)

    except Exception as exc:
        raw_output = {"error": str(exc)}
        error_detail = str(exc)
        logger.exception("process_invoice failed")

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)

        # ----- Persist audit record -----------------------------------------------
        user = None
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                pass

        AIIngestAudit.objects.create(
            task_id=task_id,
            provider=provider,
            model=model,
            raw_output=raw_output,
            validated_output=validated_output,
            latency_ms=latency_ms,
            succeeded=succeeded,
            created_by=user,
        )

    if not succeeded:
        # Retry if configured
        if self.request.retries < self.max_retries:
            raise self.retry(exc=Exception(error_detail))

    return {
        "succeeded": succeeded,
        "task_id": task_id,
        "latency_ms": latency_ms,
        "provider": provider,
        "model": model,
        "validated": validated_output,
    }
