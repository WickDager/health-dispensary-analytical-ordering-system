from __future__ import annotations
import uuid
from django.db import models

class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey("catalog.Supplier", on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=12, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_cost = models.FloatField()
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["order_date"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Order #{str(self.id)[:8]} — {self.supplier.name}"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.IntegerField()
    unit_cost = models.FloatField()

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"
