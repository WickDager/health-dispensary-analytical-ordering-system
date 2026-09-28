"""
AI Ingestion services — commit a validated extraction into the database.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from datetime import date, timedelta

from django.db import transaction

from apps.audit.models import AuditLog

logger = logging.getLogger("hdaos.ingest.services")

# Placeholder shelf life applied when the source document has no expiry data.
COMMIT_LOT_SHELF_LIFE_DAYS = 730


def _match_product(description: str):
    """Find a Product for an invoice line description.

    Tries exact (case-insensitive) name match first, then a unique
    substring match.  Returns None when nothing unambiguous matches.
    """
    from apps.catalog.models import Product

    desc = (description or "").strip()
    if not desc:
        return None

    product = Product.objects.filter(name__iexact=desc).first()
    if product is not None:
        return product

    matches = Product.objects.filter(name__icontains=desc)
    if matches.count() == 1:
        return matches.first()
    return None


@transaction.atomic
def commit_ingestion(
    *,
    validated_data: Dict[str, Any],
    user,
) -> dict:
    """
    Commit a Pydantic-validated invoice extraction to the database.

    Called by the approval handler (AI_COMMIT) once an admin has reviewed
    and approved the extracted data.

    For every line item that can be matched to an existing Product, a Lot
    is created (batch number derived from the invoice number, quantity from
    the line) and the product's SOH cache is recomputed.  The source
    document carries no expiry data, so committed lots get a placeholder
    expiry of COMMIT_LOT_SHELF_LIFE_DAYS days and are flagged in the audit
    trail.  Unmatched lines are reported back instead of silently dropped.

    Returns a summary dict used both by the approval handler (for logging)
    and by tests.
    """
    from apps.catalog.models import Product
    from apps.lots.models import Lot

    invoice_number = (validated_data.get("invoice_number") or "N/A") or "N/A"
    supplier_name = validated_data.get("supplier_name") or "Unknown"
    line_items = validated_data.get("line_items") or []

    # Stable batch number per invoice+line: INV-2026-0114 -> INV-2026-0114-L1
    batch_base = invoice_number.replace(" ", "-")
    if batch_base == "N/A":
        batch_base = "AI-INGEST"

    created_lots: list[dict] = []
    unmatched: list[dict] = []
    touched_products: list[Product] = []

    for idx, item in enumerate(line_items, start=1):
        description = str(item.get("description", "")).strip()
        try:
            quantity = int(item.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0

        if quantity <= 0:
            unmatched.append({
                "description": description, "reason": "invalid or missing quantity",
            })
            continue

        product = _match_product(description)
        if product is None:
            unmatched.append({
                "description": description,
                "reason": "no matching product",
            })
            continue

        batch_number = f"{batch_base}-L{idx}"
        lot, created = Lot.objects.get_or_create(
            product=product,
            batch_number=batch_number,
            defaults={
                "manufacture_date": date.today(),
                "expiry_date": date.today() + timedelta(days=COMMIT_LOT_SHELF_LIFE_DAYS),
                "quantity": quantity,
            },
        )
        if not created:
            # Re-delivery of the same invoice: top up rather than duplicate.
            lot.quantity += quantity
            lot.save(update_fields=["quantity"])

        created_lots.append({
            "lot_id": str(lot.id),
            "batch_number": batch_number,
            "product": product.name,
            "quantity": quantity,
            "expiry_date": lot.expiry_date.isoformat(),
            "expiry_is_placeholder": True,
        })
        if product not in touched_products:
            touched_products.append(product)

    # Recompute the SOH cache for every product we touched.
    for product in touched_products:
        product.recompute_soh()

    AuditLog.objects.create(
        action="AI_INGEST_COMMIT",
        category="CLINICAL",
        details={
            "invoice_number": invoice_number,
            "supplier_name": supplier_name,
            "line_count": len(line_items),
            "lots_created": created_lots,
            "unmatched_lines": unmatched,
            "placeholder_expiry_days": COMMIT_LOT_SHELF_LIFE_DAYS,
            "validated_data": validated_data,
        },
        user=user,
    )

    logger.info(
        "Committed AI ingestion for invoice %s from %s: %d lot(s) created, "
        "%d line(s) unmatched.",
        invoice_number, supplier_name, len(created_lots), len(unmatched),
    )

    return {
        "status": "committed",
        "invoice_number": invoice_number,
        "line_items_committed": len(created_lots),
        "lots_created": created_lots,
        "unmatched_lines": unmatched,
    }
