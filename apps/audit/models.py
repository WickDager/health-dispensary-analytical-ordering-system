from __future__ import annotations
import uuid
from django.conf import settings
from django.db import models

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=64)
    category = models.CharField(max_length=32)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs")

    class Meta:
        indexes = [models.Index(fields=["timestamp"]), models.Index(fields=["category"])]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.category}] {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"


class AIIngestAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Celery task id (or "sync-<uuid>" when processed without a broker) so the
    # status-polling endpoint can look up the audit row for a specific upload.
    task_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    provider = models.CharField(max_length=16)
    model = models.CharField(max_length=128)
    raw_output = models.JSONField()
    validated_output = models.JSONField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField()
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    est_cost_usd = models.FloatField(null=True, blank=True)
    succeeded = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["provider"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return f"{self.provider}/{self.model} — {'OK' if self.succeeded else 'FAIL'}"
