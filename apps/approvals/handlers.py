"""
Approval action handlers — each handler receives the `payload` dict from an
approved ApprovalRequest and performs the corresponding side-effect.

Registered in HANDLERS dict keyed by ApprovalRequest.action_type.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from django.db import transaction

logger = logging.getLogger("hdaos.approvals.handlers")


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------

@transaction.atomic
def handle_user_activate(payload: dict) -> None:
    """Activate a user account."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(pk=payload["user_id"])
    user.is_active = True
    user.save(update_fields=["is_active"])
    logger.info("User %s activated via approval.", user.username)


@transaction.atomic
def handle_role_change(payload: dict) -> None:
    """Change a user's role."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(pk=payload["user_id"])
    user.role = payload["new_role"]
    user.save(update_fields=["role"])
    logger.info("User %s role changed to %s via approval.", user.username, payload["new_role"])


@transaction.atomic
def handle_stock_adjust(payload: dict) -> None:
    """Adjust stock on hand for a product (manual override)."""
    from apps.catalog.models import Product

    product = Product.objects.get(pk=payload["product_id"])
    adjustment = payload.get("adjustment", 0)
    product.soh += adjustment
    if product.soh < 0:
        product.soh = 0
    product.save(update_fields=["soh"])
    logger.info("Product %s SOH adjusted by %d via approval.", product.name, adjustment)


@transaction.atomic
def handle_order_submit(payload: dict) -> None:
    """Mark an order as SENT and record the action."""
    from apps.orders.models import Order, OrderStatus
    from apps.audit.models import AuditLog

    order = Order.objects.get(pk=payload["order_id"])
    order.status = OrderStatus.SENT
    order.save(update_fields=["status"])
    AuditLog.objects.create(
        action="ORDER_SENT",
        category="PROCUREMENT",
        details={"order_id": str(order.id), "supplier": order.supplier.name},
    )
    logger.info("Order %s submitted (SENT) via approval.", str(order.id)[:8])


@transaction.atomic
def handle_ai_commit(payload: dict) -> None:
    """Commit a validated AI invoice extraction into the database."""
    from apps.ingest.services import commit_ingestion

    validated_data = payload.get("validated_data", {})
    commit_ingestion(validated_data=validated_data, user=None)
    logger.info("AI invoice committed via approval.")


@transaction.atomic
def handle_product_delete(payload: dict) -> None:
    """Delete a product (soft-delete not implemented; hard delete)."""
    from apps.catalog.models import Product

    product = Product.objects.get(pk=payload["product_id"])
    name = product.name
    product.delete()
    logger.info("Product '%s' deleted via approval.", name)


@transaction.atomic
def handle_lot_unlock(payload: dict) -> None:
    """Unlock a previously locked lot."""
    from apps.lots.models import Lot

    lot = Lot.objects.get(pk=payload["lot_id"])
    lot.is_locked = False
    lot.save(update_fields=["is_locked"])
    logger.info("Lot %s (%s) unlocked via approval.", lot.batch_number, str(lot.id)[:8])


@transaction.atomic
def handle_contact_bulk_export(payload: dict) -> None:
    """Approve a bulk contact export request.  Logs the action; actual export
    is handled by the CRM module."""
    from apps.audit.models import AuditLog

    AuditLog.objects.create(
        action="CONTACT_BULK_EXPORT",
        category="CRM",
        details=payload,
    )
    logger.info("Contact bulk export approved. Filters: %s", payload.get("filters", {}))


# ---------------------------------------------------------------------------
# Registry — maps action_type -> handler callable
# ---------------------------------------------------------------------------
HANDLERS: Dict[str, Callable[[dict], None]] = {
    "USER_ACTIVATE": handle_user_activate,
    "ROLE_CHANGE": handle_role_change,
    "STOCK_ADJUST": handle_stock_adjust,
    "ORDER_SUBMIT": handle_order_submit,
    "AI_COMMIT": handle_ai_commit,
    "PRODUCT_DELETE": handle_product_delete,
    "LOT_UNLOCK": handle_lot_unlock,
    "CONTACT_BULK_EXPORT": handle_contact_bulk_export,
}
