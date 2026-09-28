"""
Comprehensive tests for the orders app: Order, OrderItem models,
serializers (nested items), procurement suggestions, order submission
workflow, and API endpoints.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.orders.models import Order, OrderItem, OrderStatus
from apps.orders.serializers import OrderSerializer, OrderItemSerializer


# ===========================================================================
# Model Tests
# ===========================================================================
class TestOrderModel:
    """Tests for the Order model."""

    def test_create_order(self, db, supplier):
        """Order can be created with required fields."""
        order = Order.objects.create(
            supplier=supplier,
            total_cost=500.00,
        )
        assert order.id is not None
        assert order.supplier == supplier
        assert order.status == OrderStatus.PENDING
        assert order.total_cost == 500.00

    def test_order_default_status(self, db, supplier):
        """New orders default to PENDING."""
        order = Order.objects.create(supplier=supplier, total_cost=100.0)
        assert order.status == "PENDING"

    def test_order_str(self, db, supplier):
        """String representation is descriptive."""
        order = Order.objects.create(supplier=supplier, total_cost=100.0)
        s = str(order)
        assert supplier.name in s

    def test_order_supplier_cascade(self, db, supplier):
        """Cannot delete a supplier with orders (PROTECT)."""
        Order.objects.create(supplier=supplier, total_cost=100.0)
        with pytest.raises(Exception):
            supplier.delete()

    def test_order_status_choices(self, db, supplier):
        """Order supports all status choices."""
        for status_code, _label in OrderStatus.choices:
            order = Order.objects.create(
                supplier=supplier, total_cost=100.0, status=status_code,
            )
            assert order.status == status_code

    def test_order_expected_delivery_optional(self, db, supplier):
        """Expected delivery date can be null."""
        order = Order.objects.create(supplier=supplier, total_cost=100.0)
        assert order.expected_delivery is None


class TestOrderItemModel:
    """Tests for the OrderItem model."""

    def test_create_order_item(self, db, order, product):
        """Order item can be created."""
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=100,
            unit_cost=0.15,
        )
        assert item.id is not None
        assert item.order == order
        assert item.product == product
        assert item.quantity == 100
        assert item.unit_cost == 0.15

    def test_order_item_str(self, db, order, product):
        """String representation includes product and quantity."""
        item = OrderItem.objects.create(
            order=order, product=product, quantity=100, unit_cost=0.15,
        )
        s = str(item)
        assert product.name in s

    def test_order_items_related(self, db, order, product):
        """Order.items returns related items."""
        OrderItem.objects.create(
            order=order, product=product, quantity=100, unit_cost=0.15,
        )
        assert order.items.count() >= 1  # order fixture already has one item

    def test_order_product_protect(self, db, order, product):
        """Cannot delete product with order items (PROTECT)."""
        OrderItem.objects.create(
            order=order, product=product, quantity=100, unit_cost=0.15,
        )
        with pytest.raises(Exception):
            product.delete()


# ===========================================================================
# Serializer Tests
# ===========================================================================
class TestOrderSerializer:
    """Tests for OrderSerializer with nested items."""

    def test_create_order_with_items(self, db, supplier, product):
        """Can create an order with nested items."""
        data = {
            "supplier": str(supplier.id),
            "total_cost": 75.00,
            "items": [
                {
                    "product": str(product.id),
                    "quantity": 500,
                    "unit_cost": 0.15,
                },
            ],
        }
        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        order = serializer.save()
        assert order.items.count() == 1
        assert order.items.first().quantity == 500

    def test_create_order_multiple_items(self, db, supplier, product):
        """Can create an order with multiple items."""
        # Create second product
        from apps.catalog.models import Product
        product2 = Product.objects.create(
            name="Ibuprofen", api="Ibuprofen", strength="400mg",
            supplier=supplier,
        )
        data = {
            "supplier": str(supplier.id),
            "total_cost": 150.00,
            "items": [
                {"product": str(product.id), "quantity": 100, "unit_cost": 0.50},
                {"product": str(product2.id), "quantity": 200, "unit_cost": 0.50},
            ],
        }
        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        order = serializer.save()
        assert order.items.count() == 2

    def test_update_order_items(self, db, order, product):
        """Can update order items (replacement)."""
        data = {
            "supplier": str(order.supplier.id),
            "total_cost": 200.00,
            "items": [
                {
                    "product": str(product.id),
                    "quantity": 2000,
                    "unit_cost": 0.10,
                },
            ],
        }
        serializer = OrderSerializer(order, data=data, partial=False)
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.items.count() == 1
        assert updated.items.first().quantity == 2000

    def test_serialize_order_with_items(self, db, order):
        """Serialized order includes items and supplier name."""
        serializer = OrderSerializer(order)
        data = serializer.data
        assert data["supplier_name"] == order.supplier.name
        assert len(data["items"]) == 1
        assert data["items"][0]["product_name"] is not None

    def test_empty_items_list(self, db, supplier):
        """Order with empty items is valid."""
        data = {
            "supplier": str(supplier.id),
            "total_cost": 0.0,
            "items": [],
        }
        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


class TestOrderItemSerializer:
    """Tests for OrderItemSerializer."""

    def test_serialize_item(self, db, order, product):
        """Serialized item includes product_name."""
        item = OrderItem.objects.create(
            order=order, product=product, quantity=100, unit_cost=0.15,
        )
        serializer = OrderItemSerializer(item)
        data = serializer.data
        assert data["product_name"] == product.name
        assert data["quantity"] == 100
        assert data["unit_cost"] == 0.15


# ===========================================================================
# Order API Tests
# ===========================================================================
class TestOrderAPI:
    """Tests for Order API endpoints."""

    URL = "/api/orders/"

    def test_list_orders(self, admin_client, order):
        """Authenticated users can list orders."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_unauthenticated(self, api_client):
        """Unauthenticated users cannot list orders."""
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_create_order_admin(self, admin_client, supplier, product):
        """Admin can create an order."""
        response = admin_client.post(self.URL, {
            "supplier": str(supplier.id),
            "total_cost": 150.00,
            "items": [
                {"product": str(product.id), "quantity": 100, "unit_cost": 1.50},
            ],
        })
        assert response.status_code == 201

    def test_create_order_non_admin(self, pharmacist_client, supplier, product):
        """Non-admin cannot create orders."""
        response = pharmacist_client.post(self.URL, {
            "supplier": str(supplier.id),
            "total_cost": 150.00,
            "items": [
                {"product": str(product.id), "quantity": 100, "unit_cost": 1.50},
            ],
        })
        assert response.status_code == 403

    def test_filter_by_status(self, admin_client, order):
        """Can filter orders by status."""
        response = admin_client.get(f"{self.URL}?status=PENDING")
        assert response.status_code == 200
        for result in response.data["results"]:
            assert result["status"] == "PENDING"

    def test_filter_by_supplier(self, admin_client, order, supplier):
        """Can filter orders by supplier."""
        response = admin_client.get(f"{self.URL}?supplier={supplier.id}")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_search_by_supplier_name(self, admin_client, order, supplier):
        """Can search orders by supplier name."""
        response = admin_client.get(f"{self.URL}?search={supplier.name}")
        assert response.status_code == 200


class TestOrderSubmitAPI:
    """Tests for the order submit workflow."""

    def test_submit_pending_order(self, admin_client, order):
        """Submitting a PENDING order creates an approval request."""
        response = admin_client.post(
            f"/api/orders/{order.id}/submit/"
        )
        assert response.status_code == 202
        assert "approval_id" in response.data
        assert response.data["message"] == "Order submitted for approval."

    def test_submit_already_sent_order(self, admin_client, order):
        """Cannot submit an already SENT order."""
        order.status = OrderStatus.SENT
        order.save()
        response = admin_client.post(
            f"/api/orders/{order.id}/submit/"
        )
        assert response.status_code == 400

    def test_submit_unauthenticated(self, api_client, order):
        """Submit requires authentication."""
        response = api_client.post(
            f"/api/orders/{order.id}/submit/"
        )
        assert response.status_code == 401


class TestProcurementSuggestionsAPI:
    """Tests for procurement suggestions endpoint."""

    URL = "/api/orders/procurement-suggestions/"

    def test_suggestions_authenticated(self, admin_client, product_low_stock, supplier):
        """Procurement suggestions returns products below reorder point."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        # product_low_stock has soh=50, reorder_point=150
        assert len(response.data) >= 1
        # Should be grouped by supplier
        for group in response.data:
            assert "supplier_name" in group
            assert "items" in group
            assert "estimated_total" in group

    def test_suggestions_filter_supplier(self, admin_client, product_low_stock, supplier):
        """Can filter suggestions by supplier."""
        response = admin_client.get(f"{self.URL}?supplier_id={supplier.id}")
        assert response.status_code == 200

    def test_suggestions_min_stock_only(self, admin_client, product_low_stock, supplier):
        """min_stock_only=True only shows products below min_stock."""
        response = admin_client.get(f"{self.URL}?min_stock_only=true")
        assert response.status_code == 200

    def test_suggestions_unauthenticated(self, api_client):
        """Suggestions require authentication."""
        response = api_client.get(self.URL)
        assert response.status_code == 401
