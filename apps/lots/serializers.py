from __future__ import annotations

from datetime import date, timedelta

from rest_framework import serializers

from apps.lots.models import Lot


class LotSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    days_to_expiry = serializers.SerializerMethodField()
    expiry_tier = serializers.SerializerMethodField()

    class Meta:
        model = Lot
        fields = (
            "id",
            "product",
            "product_name",
            "batch_number",
            "manufacture_date",
            "expiry_date",
            "quantity",
            "is_locked",
            "days_to_expiry",
            "expiry_tier",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def get_days_to_expiry(self, obj) -> int | None:
        if not obj.expiry_date:
            return None
        return (obj.expiry_date - date.today()).days

    def get_expiry_tier(self, obj) -> str:
        days = self.get_days_to_expiry(obj)
        if days is None:
            return "OK"
        if days < 0:
            return "EXPIRED"
        if days <= 30:
            return "CRITICAL"
        if days <= 90:
            return "WARN"
        if days <= 180:
            return "INFO"
        return "OK"


class DispenseRequestSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    mrn = serializers.CharField(max_length=64)


class FEFOSuggestionSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
