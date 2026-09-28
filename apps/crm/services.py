from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.crm.models import (
    Account,
    Activity,
    Contact,
    Lead,
    Opportunity,
    PipelineStage,
)
from apps.notifications.models import Notification


# ---------------------------------------------------------------------------
# Lead-to-account+contact+opportunity conversion
# ---------------------------------------------------------------------------
@transaction.atomic
def convert_lead(
    *,
    lead_id: str,
    account_name: str,
    contact_first: str,
    contact_last: str,
    owner: User,
) -> Opportunity:
    """Atomically convert a qualified lead into an Account, Contact, and Opportunity.

    * Locks the lead row with ``select_for_update`` to prevent concurrent conversions.
    * Raises ``ValueError`` if the lead has already been converted.
    * Creates an Account (type CLINIC), a Contact (type BUYER), and an
      Opportunity (stage QUALIFICATION).
    * Logs the conversion event to the audit trail.
    """
    lead = Lead.objects.select_for_update().get(id=lead_id)

    if lead.status == "CONVERTED":
        raise ValueError(f"Lead '{lead.name}' is already converted.")

    account = Account.objects.create(
        name=account_name,
        account_type="CLINIC",
        owner=owner,
    )

    contact = Contact.objects.create(
        contact_type="BUYER",
        first_name=contact_first,
        last_name=contact_last,
        account=account,
        owner=owner,
    )

    opportunity = Opportunity.objects.create(
        name=f"{account_name} — Initial Deal",
        account=account,
        stage=PipelineStage.QUALIFICATION,
        amount=lead.est_value,
        probability=10,
        owner=owner,
    )

    # Mark the lead as converted *after* all related objects exist.
    lead.status = "CONVERTED"
    lead.save(update_fields=["status"])

    AuditLog.objects.create(
        action=f"Lead '{lead.name}' converted to Account '{account_name}'",
        category="crm",
        details={
            "lead_id": str(lead.id),
            "account_id": str(account.id),
            "contact_id": str(contact.id),
            "opportunity_id": str(opportunity.id),
        },
        user=owner,
    )

    return opportunity


# ---------------------------------------------------------------------------
# 360-degree contact timeline
# ---------------------------------------------------------------------------
def get_timeline(contact_id: str) -> list[dict[str, Any]]:
    """Return a unified, time-sorted feed for a contact's 360-degree view.

    Aggregates:
    * Activities logged directly against this contact.
    * Dispense events from the audit trail (matched by MRN).
    * Opportunities linked via the contact's parent account.
    * Notifications sent to any system user whose email matches the contact's email.

    Returns the 100 most recent entries, each structured as::

        {"type": str, "date": str, "title": str, "detail": str, "link": str}
    """
    try:
        contact = Contact.objects.only(
            "id", "mrn", "email", "account_id"
        ).get(id=contact_id)
    except Contact.DoesNotExist:
        return []

    entries: list[dict[str, Any]] = []

    # ---- 1. Activities ----
    activities = Activity.objects.filter(contact_id=contact_id).select_related(
        "created_by"
    )
    for a in activities:
        entries.append({
            "type": "activity",
            "date": a.created_at,
            "title": f"{a.get_activity_type_display()}: {a.subject}",
            "detail": a.body or "",
            "link": f"/crm/activities/{a.id}",
        })

    # ---- 2. Dispenses (AuditLog) ----
    # dispense_fefo writes category="CLINICAL" — keep the filter in sync.
    mrn = contact.mrn
    if mrn:
        dispenses = AuditLog.objects.filter(
            category="CLINICAL", action="DISPENSE", details__mrn=mrn
        )
        for d in dispenses:
            details = d.details or {}
            product = details.get("product")
            if not product and details.get("product_id"):
                from apps.catalog.models import Product

                product = (
                    Product.objects.filter(id=details["product_id"])
                    .values_list("name", flat=True)
                    .first()
                ) or "Unknown product"
            qty = details.get("quantity", "N/A")
            entries.append({
                "type": "dispense",
                "date": d.timestamp,
                "title": f"Dispensed: {product}",
                "detail": f"Quantity: {qty}",
                "link": f"/audit/{d.id}",
            })

    # ---- 3. Opportunities (via account) ----
    if contact.account_id:
        opportunities = Opportunity.objects.filter(
            account_id=contact.account_id
        )
        for o in opportunities:
            entries.append({
                "type": "opportunity",
                "date": o.created_at,
                "title": f"Opportunity: {o.name}",
                "detail": (
                    f"Stage: {o.get_stage_display()}, "
                    f"Amount: ${o.amount:,.2f}"
                ),
                "link": f"/crm/opportunities/{o.id}",
            })

    # ---- 4. Notifications matching the contact's email ----
    if contact.email:
        user_ids = (
            User.objects.filter(email=contact.email)
            .values_list("id", flat=True)
        )
        notifications = Notification.objects.filter(
            recipient_id__in=list(user_ids)
        )
        for n in notifications:
            entries.append({
                "type": "notification",
                "date": n.created_at,
                "title": n.title,
                "detail": n.body or "",
                "link": n.link or f"/notifications/{n.id}",
            })

    # Sort by date descending, return top 100.
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries[:100]
