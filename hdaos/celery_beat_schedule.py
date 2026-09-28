from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "nightly-scan-expiries": {
        "task": "apps.notifications.tasks.nightly_scan_expiries",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "celery"},
    },
    "nightly-scan-low-stock": {
        "task": "apps.notifications.tasks.nightly_scan_low_stock",
        "schedule": crontab(hour=2, minute=30),
        "options": {"queue": "celery"},
    },
    "nightly-scan-refills": {
        "task": "apps.notifications.tasks.nightly_scan_refills",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "celery"},
    },
    "daily-scan-tasks": {
        "task": "apps.notifications.tasks.daily_scan_tasks",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "celery"},
    },
    # -- Intelligence pipeline (runs after notification scans) --
    "nightly-intelligence-pipeline": {
        "task": "apps.intelligence.tasks.nightly_intelligence_pipeline",
        "schedule": crontab(hour=3, minute=30),
        "options": {"queue": "celery"},
    },
    "nightly-model-evaluation": {
        "task": "apps.intelligence.tasks.evaluate_models_task",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "celery"},
    },
}
