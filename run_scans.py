"""
Trigger the notification scans in-process (the same functions the Celery
beat tasks call).  Used by the usage simulation to exercise the alerting
pipeline without a Redis broker.
"""
from __future__ import annotations

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hdaos.settings")
django.setup()

from apps.notifications.services import (  # noqa: E402
    scan_expiries,
    scan_low_stock,
    scan_refills_due,
    scan_tasks_due,
)

if __name__ == "__main__":
    print(f"scan_expiries    -> {scan_expiries()} alerts")
    print(f"scan_low_stock   -> {scan_low_stock()} alerts")
    print(f"scan_refills_due -> {scan_refills_due()} reminders")
    print(f"scan_tasks_due   -> {scan_tasks_due()} task reminders")
