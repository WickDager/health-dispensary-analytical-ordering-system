from __future__ import annotations

from datetime import date
from typing import Dict, List

from django.db import transaction
from django.db.models import F

from apps.lots.models import Lot
from apps.catalog.models import Product
from apps.audit.models import AuditLog


class InsufficientStock(Exception):
    pass


@transaction.atomic
def dispense_fefo(
    *,
    product_id: str,
    quantity: int,
    mrn: str,
    user,
) -> dict:
    """
    Dispense `quantity` from the earliest-expiring, unlocked, non-expired lots
    for the given product.  Raises InsufficientStock if the full quantity
    cannot be satisfied.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    # Lock matching lots in expiry order (FEFO = First Expiry, First Out)
    lots = (
        Lot.objects.select_for_update()
        .filter(
            product_id=product_id,
            is_locked=False,
            expiry_date__gt=date.today(),
            quantity__gt=0,
        )
        .order_by("expiry_date")
    )

    remaining: int = quantity
    allocations: List[Dict] = []

    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.quantity, remaining)
        Lot.objects.filter(pk=lot.pk).update(quantity=F("quantity") - take)
        allocations.append(
            {
                "lot_id": str(lot.pk),
                "batch_number": lot.batch_number,
                "qty": take,
                "expiry_date": lot.expiry_date.isoformat(),
            }
        )
        remaining -= take

    if remaining > 0:
        raise InsufficientStock(f"Short by {remaining} units")

    # Recompute the product-level SOH cache
    Product.objects.get(pk=product_id).recompute_soh()

    # Audit trail
    AuditLog.objects.create(
        action="DISPENSE",
        category="CLINICAL",
        details={
            "product_id": product_id,
            "quantity": quantity,
            "mrn": mrn,
            "allocations": allocations,
        },
        user=user,
    )

    return {"allocations": allocations, "total_dispensed": quantity}


def get_fefo_suggestion(product_id: str) -> list[dict]:
    """
    Return the list of available lots for a product, ordered FEFO.
    This is a read-only preview (no locks, no deduction).
    """
    lots = (
        Lot.objects.filter(
            product_id=product_id,
            is_locked=False,
            quantity__gt=0,
        )
        .order_by("expiry_date")
        .values("id", "batch_number", "expiry_date", "quantity")
    )

    return [
        {
            "lot_id": str(l["id"]),
            "batch_number": l["batch_number"],
            "expiry_date": l["expiry_date"].isoformat(),
            "available": l["quantity"],
        }
        for l in lots
    ]
