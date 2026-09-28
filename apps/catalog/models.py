from __future__ import annotations
import uuid
from django.db import models

class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    contact_email = models.EmailField(null=True, blank=True)
    lead_time = models.PositiveIntegerField(default=3)
    min_order_value = models.FloatField(default=0.0)
    rating = models.FloatField(default=5.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    api = models.CharField(max_length=255)          # Active Pharmaceutical Ingredient
    strength = models.CharField(max_length=64)
    soh = models.IntegerField(default=0)            # derived cache of open-lot sum
    min_stock = models.PositiveIntegerField(default=100)
    max_stock = models.PositiveIntegerField(default=1000)
    unit_cost = models.FloatField(default=0.0)
    pack_size = models.PositiveIntegerField(default=1)
    reorder_point = models.PositiveIntegerField(default=200)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["api"]), models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.name} ({self.strength})"

    def recompute_soh(self) -> int:
        total = self.lots.filter(is_locked=False).aggregate(s=models.Sum("quantity"))["s"] or 0
        self.soh = total
        self.save(update_fields=["soh"])
        return total
