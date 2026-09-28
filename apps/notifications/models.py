from __future__ import annotations
import uuid
from django.conf import settings
from django.db import models

class Notification(models.Model):
    TYPES = [
        ("EXPIRY_WARNING", "Expiry warning"),
        ("STOCKOUT", "Stockout"),
        ("REORDER", "Reorder"),
        ("REFILL_DUE", "Refill due"),
        ("TASK_DUE", "Task due"),
        ("APPROVAL_PENDING", "Approval pending"),
        ("DEAL_UPDATE", "Deal update"),
    ]
    LEVELS = [("INFO", "Info"), ("WARN", "Warning"), ("CRITICAL", "Critical")]
    CHANNELS = [("IN_APP", "In-app"), ("EMAIL", "Email")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notif_type = models.CharField(max_length=20, choices=TYPES)
    level = models.CharField(max_length=8, choices=LEVELS, default="INFO")
    channel = models.CharField(max_length=8, choices=CHANNELS, default="IN_APP")
    title = models.CharField(max_length=255)
    body = models.TextField()
    link = models.CharField(max_length=255, null=True, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "read"]),
            models.Index(fields=["notif_type"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_level_display()}] {self.title}"
