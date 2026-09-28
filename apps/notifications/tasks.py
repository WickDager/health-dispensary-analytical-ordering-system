from celery import shared_task
from apps.notifications.services import scan_expiries, scan_low_stock, scan_refills_due, scan_tasks_due


@shared_task
def nightly_scan_expiries():
    count = scan_expiries()
    return f"Expiry scan: {count} alerts"


@shared_task
def nightly_scan_low_stock():
    count = scan_low_stock()
    return f"Low stock scan: {count} alerts"


@shared_task
def nightly_scan_refills():
    count = scan_refills_due()
    return f"Refill scan: {count} reminders"


@shared_task
def daily_scan_tasks():
    count = scan_tasks_due()
    return f"Task scan: {count} reminders"
