from rest_framework import serializers

from apps.orders.models import Order, OrderItem, OrderStatus


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "quantity", "unit_cost")
        read_only_fields = ("id",)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "supplier",
            "supplier_name",
            "status",
            "total_cost",
            "order_date",
            "expected_delivery",
            "items",
        )
        read_only_fields = ("id", "order_date")

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)
        return instance


class ProcurementSuggestionSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField(required=False)
    min_stock_only = serializers.BooleanField(default=True)
