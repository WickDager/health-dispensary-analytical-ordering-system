"""
Comprehensive tests for the catalog app: Supplier and Product models,
serializers, views, permissions, and dashboard endpoint.
"""
from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.catalog.models import Product, Supplier
from apps.catalog.serializers import ProductSerializer, SupplierSerializer


# ===========================================================================
# Model Tests
# ===========================================================================
class TestSupplierModel:
    """Tests for the Supplier model."""

    def test_create_supplier_minimal(self, db):
        """Supplier can be created with just a name."""
        supplier = Supplier.objects.create(name="Test Supplier")
        assert supplier.id is not None
        assert supplier.name == "Test Supplier"
        assert supplier.lead_time == 3  # default
        assert supplier.min_order_value == 0.0  # default
        assert supplier.rating == 5.0  # default
        assert supplier.created_at is not None

    def test_create_supplier_full(self, db):
        """Supplier can be created with all fields."""
        supplier = Supplier.objects.create(
            name="PharmaCorp",
            contact_email="orders@pharmacorp.com",
            lead_time=5,
            min_order_value=500.0,
            rating=4.5,
        )
        assert supplier.name == "PharmaCorp"
        assert supplier.contact_email == "orders@pharmacorp.com"
        assert supplier.lead_time == 5
        assert supplier.min_order_value == 500.0
        assert supplier.rating == 4.5

    def test_supplier_str(self, db):
        """String representation is the name."""
        supplier = Supplier.objects.create(name="PharmaCorp")
        assert str(supplier) == "PharmaCorp"

    def test_supplier_email_optional(self, db):
        """Contact email can be null/blank."""
        supplier = Supplier.objects.create(name="Test", contact_email=None)
        assert supplier.contact_email is None

    def test_supplier_lead_time_positive(self, db):
        """Lead time should accept positive integers."""
        supplier = Supplier.objects.create(name="Test", lead_time=10)
        assert supplier.lead_time == 10

    def test_supplier_rating_range(self, db):
        """Rating accepts float values."""
        supplier = Supplier.objects.create(name="Test", rating=3.7)
        assert supplier.rating == 3.7

    def test_supplier_products_related(self, db, supplier):
        """Supplier.products returns related products."""
        Product.objects.create(
            name="Test Product", api="TestAPI", strength="10mg", supplier=supplier,
        )
        assert supplier.products.count() == 1


class TestProductModel:
    """Tests for the Product model."""

    def test_create_product_minimal(self, db, supplier):
        """Product can be created with minimum required fields."""
        product = Product.objects.create(
            name="Paracetamol",
            api="Paracetamol",
            strength="500mg",
            supplier=supplier,
        )
        assert product.id is not None
        assert product.name == "Paracetamol"
        assert product.soh == 0  # default
        assert product.min_stock == 100
        assert product.max_stock == 1000
        assert product.reorder_point == 200

    def test_create_product_all_fields(self, db, supplier):
        """Product can be created with all custom fields."""
        product = Product.objects.create(
            name="Amoxicillin",
            api="Amoxicillin",
            strength="250mg",
            soh=300,
            min_stock=50,
            max_stock=500,
            unit_cost=0.25,
            pack_size=20,
            reorder_point=150,
            supplier=supplier,
        )
        assert product.soh == 300
        assert product.min_stock == 50
        assert product.pack_size == 20

    def test_product_str(self, db, supplier):
        """String representation includes name and strength."""
        product = Product.objects.create(
            name="Paracetamol", api="Paracetamol", strength="500mg", supplier=supplier,
        )
        assert "Paracetamol" in str(product)
        assert "500mg" in str(product)

    def test_product_no_supplier(self, db):
        """Product can be created without a supplier."""
        product = Product.objects.create(
            name="No-Supplier Drug", api="Test", strength="10mg",
        )
        assert product.supplier is None

    def test_recompute_soh_no_lots(self, db, supplier):
        """Recomputing SOH with no lots returns 0."""
        product = Product.objects.create(
            name="Test", api="Test", strength="10mg", supplier=supplier, soh=999,
        )
        result = product.recompute_soh()
        assert result == 0
        product.refresh_from_db()
        assert product.soh == 0

    def test_recompute_soh_with_lots(self, db, supplier):
        """Recomputing SOH sums unlocked lot quantities."""
        from apps.lots.models import Lot
        from datetime import date, timedelta

        product = Product.objects.create(
            name="Test", api="Test", strength="10mg", supplier=supplier,
        )
        Lot.objects.create(
            product=product, batch_number="B1",
            manufacture_date=date.today(), expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        Lot.objects.create(
            product=product, batch_number="B2",
            manufacture_date=date.today(), expiry_date=date.today() + timedelta(days=365),
            quantity=50,
        )
        result = product.recompute_soh()
        assert result == 150
        product.refresh_from_db()
        assert product.soh == 150

    def test_recompute_soh_excludes_locked(self, db, supplier):
        """Recomputing SOH excludes locked lots."""
        from apps.lots.models import Lot
        from datetime import date, timedelta

        product = Product.objects.create(
            name="Test", api="Test", strength="10mg", supplier=supplier,
        )
        Lot.objects.create(
            product=product, batch_number="B1",
            manufacture_date=date.today(), expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        Lot.objects.create(
            product=product, batch_number="B2",
            manufacture_date=date.today(), expiry_date=date.today() + timedelta(days=365),
            quantity=50, is_locked=True,
        )
        result = product.recompute_soh()
        assert result == 100

    def test_product_unique_uuid(self, db, supplier):
        """Each product gets a unique UUID."""
        p1 = Product.objects.create(name="A", api="X", strength="1mg", supplier=supplier)
        p2 = Product.objects.create(name="B", api="Y", strength="2mg", supplier=supplier)
        assert p1.id != p2.id


# ===========================================================================
# Serializer Tests
# ===========================================================================
class TestSupplierSerializer:
    """Tests for SupplierSerializer."""

    def test_serialize_supplier(self, db, supplier):
        """Serializer outputs correct fields."""
        serializer = SupplierSerializer(supplier)
        data = serializer.data
        assert data["name"] == supplier.name
        assert data["contact_email"] == supplier.contact_email
        assert data["lead_time"] == supplier.lead_time
        assert data["rating"] == supplier.rating
        assert "id" in data
        assert "created_at" in data
        assert "product_count" in data

    def test_deserialize_supplier(self, db):
        """Serializer creates a supplier from valid data."""
        data = {"name": "New Supplier", "lead_time": 4, "rating": 4.0}
        serializer = SupplierSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        supplier = serializer.save()
        assert supplier.name == "New Supplier"
        assert supplier.lead_time == 4

    def test_validate_empty_name(self, db):
        """Supplier name is required."""
        serializer = SupplierSerializer(data={"name": ""})
        assert not serializer.is_valid()

    def test_validate_missing_name(self, db):
        """Supplier name is required."""
        serializer = SupplierSerializer(data={})
        assert not serializer.is_valid()

    def test_product_count_read_only(self, db, supplier):
        """product_count is read-only."""
        Product.objects.create(
            name="P1", api="A", strength="1mg", supplier=supplier,
        )
        serializer = SupplierSerializer(supplier)
        assert serializer.data["product_count"] == 1


class TestProductSerializer:
    """Tests for ProductSerializer."""

    def test_serialize_product(self, db, product):
        """Product serializer outputs correct fields."""
        serializer = ProductSerializer(product)
        data = serializer.data
        assert data["name"] == product.name
        assert data["api"] == product.api
        assert data["strength"] == product.strength
        assert data["soh"] == product.soh
        assert data["supplier"] == product.supplier.id
        assert data["supplier_name"] == product.supplier.name
        assert "stock_status" in data

    def test_stock_status_healthy(self, db, supplier):
        """SOH above reorder point → HEALTHY."""
        product = Product.objects.create(
            name="Test", api="X", strength="1mg", soh=500,
            min_stock=100, reorder_point=200, supplier=supplier,
        )
        serializer = ProductSerializer(product)
        assert serializer.data["stock_status"] == "HEALTHY"

    def test_stock_status_low(self, db, supplier):
        """SOH between min_stock and reorder_point → LOW."""
        product = Product.objects.create(
            name="Test", api="X", strength="1mg", soh=150,
            min_stock=100, reorder_point=200, supplier=supplier,
        )
        serializer = ProductSerializer(product)
        assert serializer.data["stock_status"] == "LOW"

    def test_stock_status_critical(self, db, supplier):
        """SOH between 0 and min_stock → CRITICAL."""
        product = Product.objects.create(
            name="Test", api="X", strength="1mg", soh=50,
            min_stock=100, reorder_point=200, supplier=supplier,
        )
        serializer = ProductSerializer(product)
        assert serializer.data["stock_status"] == "CRITICAL"

    def test_stock_status_stockout(self, db, supplier):
        """SOH <= 0 → STOCKOUT."""
        product = Product.objects.create(
            name="Test", api="X", strength="1mg", soh=0,
            min_stock=100, reorder_point=200, supplier=supplier,
        )
        serializer = ProductSerializer(product)
        assert serializer.data["stock_status"] == "STOCKOUT"

    def test_deserialize_product(self, db, supplier):
        """Serializer creates a product from valid data."""
        data = {
            "name": "Ibuprofen",
            "api": "Ibuprofen",
            "strength": "400mg",
            "min_stock": 50,
            "max_stock": 500,
            "unit_cost": 0.10,
            "reorder_point": 100,
            "supplier": str(supplier.id),
        }
        serializer = ProductSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        product = serializer.save()
        assert product.name == "Ibuprofen"
        assert product.soh == 0

    def test_soh_is_read_only(self, db, supplier):
        """SOH should not be set via serializer (read-only)."""
        data = {
            "name": "Test", "api": "Test", "strength": "10mg",
            "soh": 999, "supplier": str(supplier.id),
        }
        serializer = ProductSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        product = serializer.save()
        # soh is read-only and defaults to 0
        assert product.soh == 0


# ===========================================================================
# API View Tests
# ===========================================================================
class TestSupplierAPI:
    """Tests for Supplier API endpoints."""

    URL = "/api/suppliers/"

    def test_list_suppliers(self, admin_client, supplier):
        """Authenticated users can list suppliers."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_unauthenticated(self, api_client):
        """Unauthenticated users cannot list suppliers."""
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_create_supplier_admin(self, admin_client):
        """Admin can create a supplier."""
        response = admin_client.post(self.URL, {"name": "New Supplier"})
        assert response.status_code == 201
        assert response.data["name"] == "New Supplier"

    def test_create_supplier_non_admin(self, pharmacist_client):
        """Non-admin cannot create a supplier."""
        response = pharmacist_client.post(self.URL, {"name": "New Supplier"})
        assert response.status_code == 403

    def test_update_supplier_admin(self, admin_client, supplier):
        """Admin can update a supplier."""
        response = admin_client.patch(f"{self.URL}{supplier.id}/", {"rating": 4.0})
        assert response.status_code == 200
        assert response.data["rating"] == 4.0

    def test_update_supplier_non_admin(self, pharmacist_client, supplier):
        """Non-admin cannot update a supplier."""
        response = pharmacist_client.patch(f"{self.URL}{supplier.id}/", {"rating": 4.0})
        assert response.status_code == 403

    def test_delete_supplier_admin(self, admin_client, supplier):
        """Admin can delete a supplier without products."""
        response = admin_client.delete(f"{self.URL}{supplier.id}/")
        assert response.status_code == 204

    def test_delete_supplier_non_admin(self, pharmacist_client, supplier):
        """Non-admin cannot delete a supplier."""
        response = pharmacist_client.delete(f"{self.URL}{supplier.id}/")
        assert response.status_code == 403

    def test_search_suppliers(self, admin_client, supplier, supplier2):
        """Can search suppliers by name."""
        response = admin_client.get(f"{self.URL}?search=PharmaCorp")
        assert response.status_code == 200
        names = [s["name"] for s in response.data["results"]]
        assert "PharmaCorp Ltd" in names
        assert "MedSupply Inc" not in names


class TestProductAPI:
    """Tests for Product API endpoints."""

    URL = "/api/products/"

    def test_list_products(self, admin_client, product):
        """Authenticated users can list products."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_unauthenticated(self, api_client):
        """Unauthenticated users cannot list products."""
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_create_product_admin(self, admin_client, supplier):
        """Admin can create a product."""
        response = admin_client.post(self.URL, {
            "name": "New Drug",
            "api": "NewAPI",
            "strength": "100mg",
            "supplier": str(supplier.id),
        })
        assert response.status_code == 201

    def test_create_product_non_admin(self, pharmacist_client, supplier):
        """Non-admin cannot create a product."""
        response = pharmacist_client.post(self.URL, {
            "name": "New Drug", "api": "NewAPI", "strength": "100mg",
            "supplier": str(supplier.id),
        })
        assert response.status_code == 403

    def test_filter_by_stock_status_healthy(self, admin_client, product):
        """Can filter products by HEALTHY stock status."""
        response = admin_client.get(f"{self.URL}?stock_status=HEALTHY")
        assert response.status_code == 200
        result_ids = [p["id"] for p in response.data["results"]]
        assert str(product.id) in result_ids

    def test_filter_by_stock_status_critical(self, admin_client, product_low_stock):
        """Can filter products by CRITICAL stock status."""
        response = admin_client.get(f"{self.URL}?stock_status=CRITICAL")
        assert response.status_code == 200
        result_ids = [p["id"] for p in response.data["results"]]
        assert str(product_low_stock.id) in result_ids

    def test_filter_by_stock_status_stockout(self, admin_client, product_stockout):
        """Can filter products by STOCKOUT status."""
        response = admin_client.get(f"{self.URL}?stock_status=STOCKOUT")
        assert response.status_code == 200
        result_ids = [p["id"] for p in response.data["results"]]
        assert str(product_stockout.id) in result_ids

    def test_filter_by_api(self, admin_client, product):
        """Can filter products by API."""
        response = admin_client.get(f"{self.URL}?api=Paracetamol")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_filter_by_supplier(self, admin_client, product, supplier):
        """Can filter products by supplier."""
        response = admin_client.get(f"{self.URL}?supplier={supplier.id}")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_search_products(self, admin_client, product):
        """Can search products by name."""
        response = admin_client.get(f"{self.URL}?search=Paracetamol")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1


class TestDashboardAPI:
    """Tests for the dashboard summary endpoint."""

    URL = "/api/dashboard/summary/"

    def test_dashboard_authenticated(self, admin_client, product, supplier):
        """Authenticated users can access dashboard."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert "total_products" in response.data
        assert "healthy_products" in response.data
        assert "low_stock_products" in response.data
        assert "critical_stock_products" in response.data
        assert "stockout_products" in response.data
        assert "expiring_30d" in response.data
        assert "pending_approvals" in response.data
        assert "total_contacts" in response.data
        assert "pipeline_value" in response.data

    def test_dashboard_unauthenticated(self, api_client):
        """Unauthenticated users cannot access dashboard."""
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_dashboard_counts(self, admin_client, product, product_low_stock, product_stockout):
        """Dashboard correctly counts products by status."""
        response = admin_client.get(self.URL)
        assert response.data["healthy_products"] >= 1  # product has soh=500 > reorder_point=200
        assert response.data["critical_stock_products"] >= 1  # product_low_stock has soh=50 <= min_stock=100
        assert response.data["stockout_products"] >= 1  # product_stockout has soh=0
