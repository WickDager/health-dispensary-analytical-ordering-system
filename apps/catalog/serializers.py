from rest_framework import serializers
from apps.catalog.models import Product, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Supplier
        fields = (
            "id",
            "name",
            "contact_email",
            "lead_time",
            "min_order_value",
            "rating",
            "product_count",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "api",
            "strength",
            "soh",
            "min_stock",
            "max_stock",
            "unit_cost",
            "pack_size",
            "reorder_point",
            "supplier",
            "supplier_name",
            "stock_status",
            "created_at",
        )
        read_only_fields = ("id", "soh", "created_at")

    def get_stock_status(self, obj) -> str:
        if obj.soh <= 0:
            return "STOCKOUT"
        if obj.soh <= obj.min_stock:
            return "CRITICAL"
        if obj.soh <= obj.reorder_point:
            return "LOW"
        return "HEALTHY"
