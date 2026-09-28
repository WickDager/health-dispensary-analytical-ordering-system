"""
Pytest fixtures for HDAOS v3.0.

IMPORTANT: Sets DATABASE_URL env var to SQLite BEFORE Django loads,
so that settings.py uses SQLite instead of trying PostgreSQL.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# MUST be at module level — runs before pytest-django loads Django settings.
# django-environ reads os.environ BEFORE .env file, so this takes precedence.
# ---------------------------------------------------------------------------
_TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_db.sqlite3")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

import pytest


@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    """Ensure SQLite is used for the test database."""
    from django.conf import settings

    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _TEST_DB_PATH,
        }
    }


from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_user(db) -> User:
    """An active admin user."""
    user = User.objects.create_user(
        username="admin",
        email="admin@hdaos.test",
        password="testpass123",
        role="ADMIN",
        is_active=True,
    )
    return user


@pytest.fixture
def pharmacist_user(db) -> User:
    """An active pharmacist user."""
    user = User.objects.create_user(
        username="pharmacist",
        email="pharm@hdaos.test",
        password="testpass123",
        role="PHARMACIST",
        is_active=True,
    )
    return user


@pytest.fixture
def logistics_user(db) -> User:
    """An active logistics manager."""
    user = User.objects.create_user(
        username="logistics",
        email="logistics@hdaos.test",
        password="testpass123",
        role="LOGISTICS",
        is_active=True,
    )
    return user


@pytest.fixture
def procurement_user(db) -> User:
    """An active procurement officer."""
    user = User.objects.create_user(
        username="procurement",
        email="procurement@hdaos.test",
        password="testpass123",
        role="PROCUREMENT",
        is_active=True,
    )
    return user


@pytest.fixture
def sales_user(db) -> User:
    """An active sales/account manager."""
    user = User.objects.create_user(
        username="sales",
        email="sales@hdaos.test",
        password="testpass123",
        role="SALES",
        is_active=True,
    )
    return user


@pytest.fixture
def viewer_user(db) -> User:
    """An active read-only viewer."""
    user = User.objects.create_user(
        username="viewer",
        email="viewer@hdaos.test",
        password="testpass123",
        role="VIEWER",
        is_active=True,
    )
    return user


@pytest.fixture
def inactive_user(db) -> User:
    """An inactive (unapproved) user."""
    user = User.objects.create_user(
        username="inactive",
        email="inactive@hdaos.test",
        password="testpass123",
        role="PHARMACIST",
        is_active=False,
    )
    return user


# ---------------------------------------------------------------------------
# API client fixtures
# ---------------------------------------------------------------------------
class _JsonClient(APIClient):
    """API client that defaults to JSON format to avoid 415 errors."""

    def _maybe_json(self, data, format, kwargs):
        return (format or "json") if data is not None else format

    def post(self, path, data=None, format=None, **kwargs):
        fmt = self._maybe_json(data, format, kwargs)
        return super().post(path, data, format=fmt, **kwargs)

    def patch(self, path, data=None, format=None, **kwargs):
        fmt = self._maybe_json(data, format, kwargs)
        return super().patch(path, data, format=fmt, **kwargs)

    def put(self, path, data=None, format=None, **kwargs):
        fmt = self._maybe_json(data, format, kwargs)
        return super().put(path, data, format=fmt, **kwargs)


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated API client (defaults to JSON)."""
    return _JsonClient()


@pytest.fixture
def admin_client(admin_user) -> APIClient:
    """Authenticated admin API client."""
    client = _JsonClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def pharmacist_client(pharmacist_user) -> APIClient:
    """Authenticated pharmacist API client."""
    client = _JsonClient()
    client.force_authenticate(user=pharmacist_user)
    return client


@pytest.fixture
def logistics_client(logistics_user) -> APIClient:
    """Authenticated logistics API client."""
    client = _JsonClient()
    client.force_authenticate(user=logistics_user)
    return client


@pytest.fixture
def procurement_client(procurement_user) -> APIClient:
    """Authenticated procurement API client."""
    client = _JsonClient()
    client.force_authenticate(user=procurement_user)
    return client


@pytest.fixture
def sales_client(sales_user) -> APIClient:
    """Authenticated sales API client."""
    client = _JsonClient()
    client.force_authenticate(user=sales_user)
    return client


@pytest.fixture
def viewer_client(viewer_user) -> APIClient:
    """Authenticated viewer (read-only) API client."""
    client = _JsonClient()
    client.force_authenticate(user=viewer_user)
    return client


# ---------------------------------------------------------------------------
# Catalog fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def supplier(db) -> object:
    """A sample supplier."""
    from apps.catalog.models import Supplier

    return Supplier.objects.create(
        name="PharmaCorp Ltd",
        contact_email="orders@pharmacorp.com",
        lead_time=5,
        min_order_value=500.0,
        rating=4.5,
    )


@pytest.fixture
def supplier2(db) -> object:
    """Another sample supplier."""
    from apps.catalog.models import Supplier

    return Supplier.objects.create(
        name="MedSupply Inc",
        contact_email="info@medsupply.com",
        lead_time=3,
        min_order_value=200.0,
        rating=4.0,
    )


@pytest.fixture
def product(db, supplier) -> object:
    """A sample product with stock on hand."""
    from apps.catalog.models import Product

    return Product.objects.create(
        name="Paracetamol",
        api="Paracetamol",
        strength="500mg",
        soh=500,
        min_stock=100,
        max_stock=1000,
        unit_cost=0.15,
        pack_size=100,
        reorder_point=200,
        supplier=supplier,
    )


@pytest.fixture
def product_low_stock(db, supplier) -> object:
    """A product with critically low stock."""
    from apps.catalog.models import Product

    return Product.objects.create(
        name="Amoxicillin",
        api="Amoxicillin",
        strength="250mg",
        soh=50,
        min_stock=100,
        max_stock=500,
        unit_cost=0.25,
        pack_size=20,
        reorder_point=150,
        supplier=supplier,
    )


@pytest.fixture
def product_stockout(db, supplier) -> object:
    """A product with zero stock."""
    from apps.catalog.models import Product

    return Product.objects.create(
        name="Insulin",
        api="Insulin Glargine",
        strength="100IU/ml",
        soh=0,
        min_stock=50,
        max_stock=300,
        unit_cost=5.00,
        pack_size=5,
        reorder_point=80,
        supplier=supplier,
    )


# ---------------------------------------------------------------------------
# Lot fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def lot(db, product) -> object:
    """A sample lot for product."""
    from apps.lots.models import Lot

    return Lot.objects.create(
        product=product,
        batch_number="BATCH-001",
        manufacture_date=date.today() - timedelta(days=30),
        expiry_date=date.today() + timedelta(days=365),
        quantity=300,
    )


@pytest.fixture
def lot_expiring_soon(db, product) -> object:
    """A lot expiring in 20 days."""
    from apps.lots.models import Lot

    return Lot.objects.create(
        product=product,
        batch_number="BATCH-EXPIRING",
        manufacture_date=date.today() - timedelta(days=345),
        expiry_date=date.today() + timedelta(days=20),
        quantity=100,
    )


@pytest.fixture
def lot_expired(db, product) -> object:
    """A lot already expired."""
    from apps.lots.models import Lot

    return Lot.objects.create(
        product=product,
        batch_number="BATCH-EXPIRED",
        manufacture_date=date.today() - timedelta(days=400),
        expiry_date=date.today() - timedelta(days=10),
        quantity=50,
        is_locked=True,
    )


# ---------------------------------------------------------------------------
# Order fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def order(db, supplier, product) -> object:
    """A sample pending order."""
    from apps.orders.models import Order, OrderItem

    order = Order.objects.create(
        supplier=supplier,
        status="PENDING",
        total_cost=150.00,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=1000,
        unit_cost=0.15,
    )
    return order


# ---------------------------------------------------------------------------
# CRM fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def account(db, sales_user) -> object:
    """A sample hospital account."""
    from apps.crm.models import Account

    return Account.objects.create(
        name="City General Hospital",
        account_type="HOSPITAL",
        billing_address="123 Main St, Cityville",
        owner=sales_user,
    )


@pytest.fixture
def contact(db, account) -> object:
    """A sample patient contact."""
    from apps.crm.models import Contact

    return Contact.objects.create(
        contact_type="PATIENT",
        first_name="John",
        last_name="Doe",
        email="john.doe@email.com",
        phone="+1234567890",
        mrn="MRN-12345",
        account=account,
        consent_marketing=True,
    )


@pytest.fixture
def lead(db, sales_user) -> object:
    """A sample qualified lead."""
    from apps.crm.models import Lead

    return Lead.objects.create(
        name="Riverside Clinic Supply",
        source="referral",
        status="QUALIFIED",
        est_value=5000.0,
        owner=sales_user,
    )


@pytest.fixture
def opportunity(db, account, sales_user) -> object:
    """A sample opportunity."""
    from apps.crm.models import Opportunity

    return Opportunity.objects.create(
        name="Hospital Annual Supply Contract",
        account=account,
        stage="QUALIFICATION",
        amount=25000.0,
        probability=30,
        expected_close_date=date.today() + timedelta(days=60),
        owner=sales_user,
    )


# ---------------------------------------------------------------------------
# Approval fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def approval_request(db, admin_user) -> object:
    """A sample pending approval request."""
    from apps.approvals.models import ApprovalRequest

    return ApprovalRequest.objects.create(
        action_type="USER_ACTIVATE",
        payload={"user_id": str(uuid.uuid4())},
        status="PENDING",
        requested_by=admin_user,
    )


# ---------------------------------------------------------------------------
# Notification fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def notification(db, admin_user) -> object:
    """A sample notification."""
    from apps.notifications.models import Notification

    return Notification.objects.create(
        recipient=admin_user,
        notif_type="EXPIRY_WARNING",
        level="WARN",
        channel="IN_APP",
        title="Expiry Warning: Paracetamol",
        body="Batch BATCH-001 expires in 30 days.",
    )
