"""
Celery application configuration for HDAOS v3.0.

Auto-discovers tasks from all installed apps.
"""
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hdaos.settings")

app = Celery("hdaos")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Import beat schedule so it is available when the worker starts with -B / --beat.
try:
    from hdaos.celery_beat_schedule import CELERY_BEAT_SCHEDULE
    app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
except ImportError:
    pass

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """A no-op debug task that prints the request details."""
    print(f"Request: {self.request!r}")
