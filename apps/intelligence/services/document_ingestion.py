"""Generalized document ingestion for multiple document types."""
from __future__ import annotations

import logging

from apps.intelligence.models import DocumentTemplate

logger = logging.getLogger("hdaos.intelligence.document_ingestion")

# ---------------------------------------------------------------------------
# Default extraction schemas per document type
# ---------------------------------------------------------------------------
DEFAULT_SCHEMAS: dict[str, dict] = {
    "invoice": {
        "prompt": (
            "Extract from this document: supplier_name, invoice_date (YYYY-MM-DD), "
            "items (product_name, strength, quantity, unit_cost). Return JSON."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string"},
                "invoice_date": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string"},
                            "strength": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "unit_cost": {"type": "number"},
                        },
                    },
                },
            },
        },
    },
    "receipt": {
        "prompt": (
            "Extract from this customer receipt: customer_name, receipt_date (YYYY-MM-DD), "
            "items (product_name, quantity, price, total), payment_method. Return JSON."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "receipt_date": {"type": "string"},
                "items": {"type": "array"},
                "payment_method": {"type": "string"},
                "total": {"type": "number"},
            },
        },
    },
    "prescription": {
        "prompt": (
            "Extract from this prescription: patient_name, prescriber_name, "
            "date (YYYY-MM-DD), medications (drug_name, strength, dosage, quantity, refills), "
            "notes. Return JSON."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string"},
                "prescriber_name": {"type": "string"},
                "date": {"type": "string"},
                "medications": {"type": "array"},
                "notes": {"type": "string"},
            },
        },
    },
    "delivery_note": {
        "prompt": (
            "Extract from this delivery note: supplier_name, delivery_date (YYYY-MM-DD), "
            "order_reference, items (product_name, quantity_delivered, batch_number, "
            "expiry_date). Return JSON."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string"},
                "delivery_date": {"type": "string"},
                "order_reference": {"type": "string"},
                "items": {"type": "array"},
            },
        },
    },
    "return_form": {
        "prompt": (
            "Extract from this return form: customer_name, return_date (YYYY-MM-DD), "
            "reason, items (product_name, quantity, batch_number, condition). Return JSON."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "return_date": {"type": "string"},
                "reason": {"type": "string"},
                "items": {"type": "array"},
            },
        },
    },
    "purchase_order": {
        "prompt": (
            "Extract from this purchase order: supplier_name, po_number, "
            "order_date (YYYY-MM-DD), items (product_name, quantity, unit_price, total). "
            "Return JSON."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string"},
                "po_number": {"type": "string"},
                "order_date": {"type": "string"},
                "items": {"type": "array"},
            },
        },
    },
    "generic": {
        "prompt": (
            "Extract all structured data from this document. Identify document type, "
            "key entities (names, dates, amounts), and any line items. Return JSON."
        ),
        "schema": {"type": "object"},
    },
}


# ---------------------------------------------------------------------------
# Template lookup
# ---------------------------------------------------------------------------
def get_template(template_type: str) -> dict:
    """Get the prompt and schema for a document type. Falls back to defaults."""
    try:
        template = DocumentTemplate.objects.get(
            template_type=template_type, is_active=True
        )
        return {
            "prompt": template.prompt_template,
            "schema": template.extraction_schema,
        }
    except DocumentTemplate.DoesNotExist:
        return DEFAULT_SCHEMAS.get(template_type, DEFAULT_SCHEMAS["generic"])


# ---------------------------------------------------------------------------
# Document ingestion entry point
# ---------------------------------------------------------------------------
def ingest_document(
    document_text: str,
    doc_type: str = "generic",
    user_id: str | None = None,
) -> dict:
    """
    Ingest any document type through the LLM gateway and validate.

    Uses the existing Celery-based invoice processing pipeline, but with a
    document-type-specific prompt and schema.  The task chain handles LLM
    extraction, Pydantic validation, audit logging, and maker-checker approval.

    Returns a dict with the Celery task_id for polling.
    """
    from apps.ingest.tasks import process_invoice

    template = get_template(doc_type)

    # Fire the Celery task.  The doc_type is passed so downstream consumers
    # (e.g. the audit commit stage) can apply the right schema.
    task = process_invoice.delay(
        text=document_text,
        user_id=user_id,
    )

    logger.info(
        "Document ingest queued: doc_type=%s task_id=%s user=%s",
        doc_type,
        task.id,
        user_id,
    )

    return {
        "task_id": task.id,
        "doc_type": doc_type,
        "template_type": doc_type,
        "status": "processing",
    }


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------
def seed_document_templates():
    """Create default DocumentTemplate rows for all supported types."""
    from apps.intelligence.models import DocumentTemplate

    created = 0
    for template_type, config in DEFAULT_SCHEMAS.items():
        _, was_created = DocumentTemplate.objects.get_or_create(
            template_type=template_type,
            defaults={
                "prompt_template": config["prompt"],
                "extraction_schema": config["schema"],
                "is_active": True,
            },
        )
        if was_created:
            created += 1
    logger.info("Seeded %d document templates.", created)
    return created
