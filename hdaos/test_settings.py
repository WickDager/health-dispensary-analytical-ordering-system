"""
Test settings for HDAOS v3.0.
Overrides DATABASE_URL to use SQLite for testing.
"""
import os

# Import all base settings first
import socket
# Override system FQDN before Django mail utils caches it (Windows hostname
# like WIN-xxx.. has trailing dots that break IDNA encoding for Message-ID).
socket.getfqdn = lambda: "hdaos-test.localhost"

from .settings import *  # noqa: F403

# Force SQLite for tests regardless of what .env says
_TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_db.sqlite3")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _TEST_DB_PATH,
    }
}

# Use eager Celery tasks in test mode (no Redis needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Don't try to send real emails in tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@hdaos-test.example"
SERVER_EMAIL = "root@hdaos-test.example"

# Don't try to connect to Redis for Celery broker
CELERY_BROKER_URL = "memory://"
