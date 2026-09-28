from __future__ import annotations
import uuid
from django.db import models

class Lot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT: deleting a product with stock lots would silently destroy
    # inventory history; block the delete instead (surface as a 409).
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="lots")
    batch_number = models.CharField(max_length=64)
    manufacture_date = models.DateField()
    expiry_date = models.DateField()
    quantity = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["product", "expiry_date"]),
            models.Index(fields=["batch_number"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="lot_qty_nonneg"),
        ]
        ordering = ["expiry_date"]

    def __str__(self):
        return f"{self.product.name} — {self.batch_number} (exp: {self.expiry_date})"
