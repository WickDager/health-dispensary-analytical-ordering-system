from __future__ import annotations
import uuid
from django.conf import settings
from django.db import models

class ApprovalRequest(models.Model):
    ACTION_CHOICES = [
        ("USER_ACTIVATE", "Activate user"),
        ("ROLE_CHANGE", "Change role"),
        ("STOCK_ADJUST", "Adjust stock"),
        ("ORDER_SUBMIT", "Submit PO"),
        ("AI_COMMIT", "Commit AI invoice"),
        ("PRODUCT_DELETE", "Delete product"),
        ("LOT_UNLOCK", "Unlock lot"),
        ("CONTACT_BULK_EXPORT", "Bulk export contacts"),
    ]
    STATUS = [("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_type = models.CharField(max_length=32, choices=ACTION_CHOICES)
    payload = models.JSONField()
    status = models.CharField(max_length=12, choices=STATUS, default="PENDING")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approvals_made")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approvals_reviewed")
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status"]), models.Index(fields=["action_type"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.get_status_display()}"

    def execute(self) -> None:
        from apps.approvals.handlers import HANDLERS
        HANDLERS[self.action_type](self.payload)
