from __future__ import annotations
import logging

from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.db import transaction, models
from apps.notifications.models import Notification

logger = logging.getLogger("hdaos.notifications.services")

User = get_user_model()

EXPIRY_TIERS = {90: "INFO", 60: "WARN", 30: "CRITICAL"}


def emit(*, kind: str, level: str, subject, detail: str, link: str | None = None, roles: list[str] | None = None) -> int:
    """Fan out a notification to all users in the given roles (default: LOGISTICS + ADMIN)."""
    roles = roles or ["LOGISTICS", "ADMIN"]
    recipients = User.objects.filter(role__in=roles, is_active=True)
    channel = "EMAIL" if level in ("WARN", "CRITICAL") else "IN_APP"
    objs = [Notification(recipient=u, notif_type=kind, level=level, channel=channel,
                         title=f"{kind.replace('_', ' ').title()}: {subject}",
                         body=detail, link=link) for u in recipients]
    Notification.objects.bulk_create(objs)
    if channel == "EMAIL":
        for u in recipients:
            if u.email:
                try:
                    _send_email_notification.delay(
                        to=u.email,
                        subject=f"[HDAOS] {kind.replace('_', ' ').title()}: {subject}",
                        body=detail,
                    )
                except Exception:
                    # Broker unreachable — never let a notification fan-out
                    # break the calling transaction (the in-app rows are
                    # already persisted above).
                    logger.exception("Failed to enqueue email notification")
    return len(objs)


@transaction.atomic
def scan_expiries() -> int:
    """Nightly scan: auto-lock expired lots + tiered alerts for approaching expiry."""
    from apps.lots.models import Lot
    today = date.today()
    count = 0
    for lot in Lot.objects.filter(expiry_date__lte=today, is_locked=False):
        lot.is_locked = True
        lot.save(update_fields=["is_locked"])
        lot.product.recompute_soh()
        emit(kind="EXPIRY_WARNING", level="CRITICAL", subject=lot.product.name,
             detail=f"Lot {lot.batch_number} EXPIRED and auto-locked.", link=f"/lots?product_id={lot.product_id}")
        count += 1
    for days, level in EXPIRY_TIERS.items():
        window = today + timedelta(days=days)
        for lot in Lot.objects.filter(expiry_date=window, is_locked=False):
            emit(kind="EXPIRY_WARNING", level=level, subject=lot.product.name,
                 detail=f"Lot {lot.batch_number} expires in {days} days ({lot.quantity} units).",
                 link=f"/lots?product_id={lot.product_id}")
            count += 1
    return count


@transaction.atomic
def scan_low_stock() -> int:
    """Check all products against reorder points; emit REORDER/STOCKOUT alerts."""
    from apps.catalog.models import Product
    count = 0
    for product in Product.objects.filter(soh__lte=models.F("reorder_point"), soh__gt=0):
        emit(kind="REORDER", level="WARN", subject=product.name,
             detail=f"Low stock: {product.soh} units (reorder at {product.reorder_point}).",
             link=f"/inventory/{product.id}", roles=["PROCUREMENT", "ADMIN"])
        count += 1
    for product in Product.objects.filter(soh__lte=0):
        emit(kind="STOCKOUT", level="CRITICAL", subject=product.name,
             detail=f"STOCKOUT: {product.name} has zero stock.",
             link=f"/inventory/{product.id}", roles=["PROCUREMENT", "LOGISTICS", "ADMIN"])
        count += 1
    return count


@transaction.atomic
def scan_refills_due() -> int:
    """Find refill reminders due today or past due."""
    from apps.crm.models import RefillReminder
    today = date.today()
    count = 0
    for reminder in RefillReminder.objects.filter(next_due_date__lte=today, active=True).select_related("contact", "product"):
        emit(kind="REFILL_DUE", level="INFO",
             subject=f"{reminder.contact.first_name} {reminder.contact.last_name}",
             detail=f"Refill due for {reminder.product.name}. Due: {reminder.next_due_date}.",
             link=f"/crm/contacts/{reminder.contact_id}", roles=["PHARMACIST", "ADMIN"])
        count += 1
    return count


@transaction.atomic
def scan_tasks_due() -> int:
    """Find open tasks due today, emit TASK_DUE, mark reminder_sent."""
    from apps.crm.models import Task
    today = date.today()
    count = 0
    for task in Task.objects.filter(due_date=today, status="OPEN", reminder_sent=False):
        if task.assignee:
            Notification.objects.create(recipient=task.assignee, notif_type="TASK_DUE", level="INFO",
                                        channel="IN_APP", title=f"Task due: {task.title}",
                                        body=f"Task '{task.title}' is due today.",
                                        link=f"/crm/activities?task={task.id}")
            count += 1
        task.reminder_sent = True
        task.save(update_fields=["reminder_sent"])
    return count


# ---------------------------------------------------------------------------
# Celery task for email delivery
# ---------------------------------------------------------------------------
from celery import shared_task
from django.core.mail import send_mail


@shared_task
def _send_email_notification(to: str, subject: str, body: str):
    send_mail(subject=subject, message=body, from_email=None, recipient_list=[to], fail_silently=True)
