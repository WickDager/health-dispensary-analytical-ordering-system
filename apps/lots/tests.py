"""
Comprehensive tests for the lots app: Lot model, serializers (expiry tiers),
FEFO dispensing service, lot views, and dispense endpoint.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import transaction

from apps.lots.models import Lot
from apps.lots.serializers import LotSerializer, DispenseRequestSerializer
from apps.lots.services import dispense_fefo, get_fefo_suggestion, InsufficientStock


# ===========================================================================
# Lot Model Tests
# ===========================================================================
class TestLotModel:
    """Tests for the Lot model."""

    def test_create_lot(self, db, product):
        """Lot can be created with valid data."""
        lot = Lot.objects.create(
            product=product,
            batch_number="BATCH-2024-001",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=1000,
        )
        assert lot.id is not None
        assert lot.product == product
        assert lot.batch_number == "BATCH-2024-001"
        assert lot.quantity == 1000
        assert lot.is_locked is False

    def test_lot_str(self, db, lot):
        """String representation includes product name and batch."""
        s = str(lot)
        assert lot.product.name in s
        assert lot.batch_number in s

    def test_lot_default_quantity_zero(self, db, product):
        """Lot quantity defaults to 0."""
        lot = Lot.objects.create(
            product=product,
            batch_number="EMPTY",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        assert lot.quantity == 0

    def test_lot_default_not_locked(self, db, product):
        """New lots are not locked by default."""
        lot = Lot.objects.create(
            product=product,
            batch_number="UNLOCKED",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        assert lot.is_locked is False

    def test_lot_quantity_constraint(self, db, product):
        """DB constraint prevents negative quantity."""
        with pytest.raises(Exception):
            Lot.objects.create(
                product=product,
                batch_number="NEG-QTY",
                manufacture_date=date.today(),
                expiry_date=date.today() + timedelta(days=365),
                quantity=-5,
            )

    def test_lot_ordering_by_expiry(self, db, product):
        """Lots are ordered by expiry_date ASC."""
        lot1 = Lot.objects.create(
            product=product, batch_number="LATE",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        lot2 = Lot.objects.create(
            product=product, batch_number="EARLY",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
        )
        lots = list(Lot.objects.all())
        # Earlier expiry should come first
        assert lots[0].expiry_date <= lots[1].expiry_date

    def test_lot_lock(self, db, lot):
        """Lot can be locked."""
        lot.is_locked = True
        lot.save(update_fields=["is_locked"])
        lot.refresh_from_db()
        assert lot.is_locked is True

    def test_lot_unlock(self, db, lot):
        """Lot can be unlocked."""
        lot.is_locked = True
        lot.save()
        lot.is_locked = False
        lot.save(update_fields=["is_locked"])
        lot.refresh_from_db()
        assert lot.is_locked is False


# ===========================================================================
# Lot Serializer Tests
# ===========================================================================
class TestLotSerializer:
    """Tests for LotSerializer."""

    def test_serialize_lot(self, db, lot):
        """Serializer outputs correct fields."""
        serializer = LotSerializer(lot)
        data = serializer.data
        assert data["batch_number"] == lot.batch_number
        assert data["product"] == lot.product.id
        assert data["product_name"] == lot.product.name
        assert data["quantity"] == lot.quantity
        assert data["is_locked"] == lot.is_locked
        assert "days_to_expiry" in data
        assert "expiry_tier" in data

    def test_expiry_tier_ok(self, db, product):
        """Lot expiring >180 days → OK."""
        lot = Lot.objects.create(
            product=product, batch_number="OK",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        serializer = LotSerializer(lot)
        assert serializer.data["expiry_tier"] == "OK"

    def test_expiry_tier_info(self, db, product):
        """Lot expiring between 91-180 days → INFO."""
        lot = Lot.objects.create(
            product=product, batch_number="INFO",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=120),
        )
        serializer = LotSerializer(lot)
        assert serializer.data["expiry_tier"] == "INFO"

    def test_expiry_tier_warn(self, db, product):
        """Lot expiring between 31-90 days → WARN."""
        lot = Lot.objects.create(
            product=product, batch_number="WARN",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        serializer = LotSerializer(lot)
        assert serializer.data["expiry_tier"] == "WARN"

    def test_expiry_tier_critical(self, db, product):
        """Lot expiring within 30 days → CRITICAL."""
        lot = Lot.objects.create(
            product=product, batch_number="CRIT",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=15),
        )
        serializer = LotSerializer(lot)
        assert serializer.data["expiry_tier"] == "CRITICAL"

    def test_expiry_tier_expired(self, db, product):
        """Lot already expired → EXPIRED."""
        lot = Lot.objects.create(
            product=product, batch_number="EXP",
            manufacture_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=10),
        )
        serializer = LotSerializer(lot)
        assert serializer.data["expiry_tier"] == "EXPIRED"
        assert serializer.data["days_to_expiry"] < 0

    def test_deserialize_lot(self, db, product):
        """Serializer creates a lot from valid data."""
        data = {
            "product": str(product.id),
            "batch_number": "NEW-BATCH",
            "manufacture_date": str(date.today()),
            "expiry_date": str(date.today() + timedelta(days=365)),
            "quantity": 500,
        }
        serializer = LotSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        lot = serializer.save()
        assert lot.batch_number == "NEW-BATCH"
        assert lot.quantity == 500


class TestDispenseRequestSerializer:
    """Tests for the dispense request serializer."""

    def test_valid_dispense_request(self, db):
        """Valid dispense request is accepted."""
        import uuid
        data = {
            "product_id": str(uuid.uuid4()),
            "quantity": 5,
            "mrn": "MRN-12345",
        }
        serializer = DispenseRequestSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_negative_quantity(self, db):
        """Negative quantity is rejected."""
        import uuid
        data = {"product_id": str(uuid.uuid4()), "quantity": -1, "mrn": "MRN-1"}
        serializer = DispenseRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_zero_quantity(self, db):
        """Zero quantity is rejected."""
        import uuid
        data = {"product_id": str(uuid.uuid4()), "quantity": 0, "mrn": "MRN-1"}
        serializer = DispenseRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_missing_product_id(self, db):
        """Missing product_id is rejected."""
        data = {"quantity": 5, "mrn": "MRN-1"}
        serializer = DispenseRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_missing_quantity(self, db):
        """Missing quantity is rejected."""
        import uuid
        data = {"product_id": str(uuid.uuid4()), "mrn": "MRN-1"}
        serializer = DispenseRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_missing_mrn(self, db):
        """Missing MRN is rejected."""
        import uuid
        data = {"product_id": str(uuid.uuid4()), "quantity": 5}
        serializer = DispenseRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_long_mrn(self, db):
        """MRN up to 64 chars is accepted."""
        import uuid
        data = {"product_id": str(uuid.uuid4()), "quantity": 1, "mrn": "X" * 64}
        serializer = DispenseRequestSerializer(data=data)
        assert serializer.is_valid()

    def test_too_long_mrn(self, db):
        """MRN over 64 chars is rejected."""
        import uuid
        data = {"product_id": str(uuid.uuid4()), "quantity": 1, "mrn": "X" * 65}
        serializer = DispenseRequestSerializer(data=data)
        assert not serializer.is_valid()


# ===========================================================================
# FEFO Dispense Service Tests
# ===========================================================================
class TestFEFOService:
    """Tests for the FEFO dispensing logic."""

    def test_dispense_basic(self, db, product, pharmacist_user):
        """Basic dispense from a single lot."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="B1",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        result = dispense_fefo(
            product_id=str(product.id),
            quantity=30,
            mrn="MRN-001",
            user=pharmacist_user,
        )
        assert result["total_dispensed"] == 30
        assert len(result["allocations"]) == 1
        assert result["allocations"][0]["qty"] == 30

    def test_dispense_fefo_order(self, db, product, pharmacist_user):
        """FEFO picks earliest-expiring lot first."""
        from apps.lots.models import Lot
        early = Lot.objects.create(
            product=product, batch_number="EARLY",
            manufacture_date=date.today() - timedelta(days=300),
            expiry_date=date.today() + timedelta(days=30),
            quantity=50,
        )
        late = Lot.objects.create(
            product=product, batch_number="LATE",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        result = dispense_fefo(
            product_id=str(product.id),
            quantity=40,
            mrn="MRN-002",
            user=pharmacist_user,
        )
        # Should use the early lot first
        allocations = result["allocations"]
        assert len(allocations) == 1  # only need early lot
        assert allocations[0]["batch_number"] == "EARLY"
        assert allocations[0]["qty"] == 40

        # Verify quantities
        early.refresh_from_db()
        assert early.quantity == 10  # 50 - 40

    def test_dispense_across_multiple_lots(self, db, product, pharmacist_user):
        """FEFO dispenses across multiple lots when needed."""
        from apps.lots.models import Lot
        lot1 = Lot.objects.create(
            product=product, batch_number="L1",
            manufacture_date=date.today() - timedelta(days=200),
            expiry_date=date.today() + timedelta(days=100),
            quantity=30,
        )
        lot2 = Lot.objects.create(
            product=product, batch_number="L2",
            manufacture_date=date.today() - timedelta(days=100),
            expiry_date=date.today() + timedelta(days=200),
            quantity=50,
        )
        result = dispense_fefo(
            product_id=str(product.id),
            quantity=60,
            mrn="MRN-003",
            user=pharmacist_user,
        )
        assert result["total_dispensed"] == 60
        allocations = result["allocations"]
        assert len(allocations) == 2  # needs both lots
        assert allocations[0]["batch_number"] == "L1"
        assert allocations[0]["qty"] == 30  # all of L1
        assert allocations[1]["batch_number"] == "L2"
        assert allocations[1]["qty"] == 30  # partial L2

    def test_dispense_insufficient_stock(self, db, product, pharmacist_user):
        """Insufficient stock raises InsufficientStock."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="SMALL",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=10,
        )
        with pytest.raises(InsufficientStock) as exc:
            dispense_fefo(
                product_id=str(product.id),
                quantity=100,
                mrn="MRN-004",
                user=pharmacist_user,
            )
        assert "Short by 90" in str(exc.value)

    def test_dispense_zero_quantity(self, db, product, pharmacist_user):
        """Zero quantity raises ValueError."""
        with pytest.raises(ValueError, match="quantity must be positive"):
            dispense_fefo(
                product_id=str(product.id),
                quantity=0,
                mrn="MRN-005",
                user=pharmacist_user,
            )

    def test_dispense_negative_quantity(self, db, product, pharmacist_user):
        """Negative quantity raises ValueError."""
        with pytest.raises(ValueError, match="quantity must be positive"):
            dispense_fefo(
                product_id=str(product.id),
                quantity=-5,
                mrn="MRN-006",
                user=pharmacist_user,
            )

    def test_dispense_excludes_expired(self, db, product, pharmacist_user):
        """Expired lots are excluded from FEFO dispense."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="EXPIRED",
            manufacture_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=10),
            quantity=100,
        )
        Lot.objects.create(
            product=product, batch_number="VALID",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=50,
        )
        result = dispense_fefo(
            product_id=str(product.id),
            quantity=30,
            mrn="MRN-007",
            user=pharmacist_user,
        )
        # Should use only the VALID lot
        assert result["allocations"][0]["batch_number"] == "VALID"

    def test_dispense_excludes_locked(self, db, product, pharmacist_user):
        """Locked lots are excluded from FEFO dispense."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="LOCKED",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100, is_locked=True,
        )
        Lot.objects.create(
            product=product, batch_number="FREE",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=50,
        )
        result = dispense_fefo(
            product_id=str(product.id),
            quantity=30,
            mrn="MRN-008",
            user=pharmacist_user,
        )
        assert result["allocations"][0]["batch_number"] == "FREE"

    def test_dispense_updates_soh(self, db, product, pharmacist_user):
        """Dispensing updates product SOH."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="B1",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        product.soh = 100
        product.save()
        dispense_fefo(
            product_id=str(product.id),
            quantity=30,
            mrn="MRN-009",
            user=pharmacist_user,
        )
        product.refresh_from_db()
        assert product.soh == 70

    def test_dispense_creates_audit_log(self, db, product, pharmacist_user):
        """Dispensing creates an audit trail."""
        from apps.lots.models import Lot
        from apps.audit.models import AuditLog
        Lot.objects.create(
            product=product, batch_number="B1",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        dispense_fefo(
            product_id=str(product.id),
            quantity=20,
            mrn="MRN-AUDIT",
            user=pharmacist_user,
        )
        log = AuditLog.objects.filter(action="DISPENSE").first()
        assert log is not None
        assert log.category == "CLINICAL"
        assert log.details["mrn"] == "MRN-AUDIT"
        assert log.details["quantity"] == 20

    def test_dispense_is_atomic(self, db, product, pharmacist_user):
        """Failed dispense rolls back all changes."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="B1",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=50,
        )
        with pytest.raises(InsufficientStock):
            dispense_fefo(
                product_id=str(product.id),
                quantity=100,  # too much
                mrn="MRN-ROLLBACK",
                user=pharmacist_user,
            )
        # Lot should still have 50
        lot = Lot.objects.get(batch_number="B1")
        assert lot.quantity == 50


class TestFEFOSuggestion:
    """Tests for the FEFO suggestion (read-only preview)."""

    def test_suggestion_basic(self, db, product):
        """FEFO suggestion returns lots in expiry order."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="LATE",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        Lot.objects.create(
            product=product, batch_number="EARLY",
            manufacture_date=date.today() - timedelta(days=300),
            expiry_date=date.today() + timedelta(days=30),
            quantity=50,
        )
        suggestion = get_fefo_suggestion(str(product.id))
        assert len(suggestion) == 2
        assert suggestion[0]["batch_number"] == "EARLY"  # first to expire
        assert suggestion[1]["batch_number"] == "LATE"

    def test_suggestion_excludes_locked(self, db, product):
        """Suggestion excludes locked lots."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="FREE",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        Lot.objects.create(
            product=product, batch_number="LOCKED",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            quantity=50, is_locked=True,
        )
        suggestion = get_fefo_suggestion(str(product.id))
        assert len(suggestion) == 1
        assert suggestion[0]["batch_number"] == "FREE"

    def test_suggestion_excludes_zero_quantity(self, db, product):
        """Suggestion excludes zero-quantity lots."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="HAS_STOCK",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        Lot.objects.create(
            product=product, batch_number="EMPTY",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            quantity=0,
        )
        suggestion = get_fefo_suggestion(str(product.id))
        assert len(suggestion) == 1


# ===========================================================================
# Lot API Tests
# ===========================================================================
class TestLotAPI:
    """Tests for Lot API endpoints."""

    URL = "/api/lots/"

    def test_list_lots(self, admin_client, lot):
        """Authenticated users can list lots."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_unauthenticated(self, api_client):
        """Unauthenticated users cannot list lots."""
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_retrieve_lot(self, admin_client, lot):
        """Can retrieve a single lot."""
        response = admin_client.get(f"{self.URL}{lot.id}/")
        assert response.status_code == 200
        assert response.data["batch_number"] == lot.batch_number

    def test_filter_by_product(self, admin_client, lot, product, supplier):
        """Can filter lots by product."""
        response = admin_client.get(f"{self.URL}?product={product.id}")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_filter_by_is_locked(self, admin_client, lot):
        """Can filter lots by lock status."""
        response = admin_client.get(f"{self.URL}?is_locked=false")
        assert response.status_code == 200
        for result in response.data["results"]:
            assert result["is_locked"] is False

    def test_search_by_batch(self, admin_client, lot):
        """Can search lots by batch number."""
        response = admin_client.get(f"{self.URL}?search={lot.batch_number}")
        assert response.status_code == 200


class TestDispenseAPI:
    """Tests for the dispense endpoint."""

    URL = "/api/lots/dispense/"

    def test_dispense_success(self, admin_client, product):
        """Dispense endpoint works with valid data."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="DISP-BATCH",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=200,
        )
        response = admin_client.post(self.URL, {
            "product_id": str(product.id),
            "quantity": 50,
            "mrn": "MRN-DISP-001",
        })
        assert response.status_code == 200
        assert response.data["total_dispensed"] == 50

    def test_dispense_insufficient(self, admin_client, product):
        """Dispense returns 409 when insufficient stock."""
        response = admin_client.post(self.URL, {
            "product_id": str(product.id),
            "quantity": 99999,
            "mrn": "MRN-FAIL",
        })
        assert response.status_code == 409
        assert "error" in response.data

    def test_dispense_bad_request(self, admin_client, product):
        """Dispense returns 400 for bad request."""
        response = admin_client.post(self.URL, {
            "product_id": str(product.id),
            "quantity": -1,
            "mrn": "MRN-BAD",
        })
        assert response.status_code == 400

    def test_dispense_unauthenticated(self, api_client, product):
        """Dispense requires authentication."""
        import uuid
        response = api_client.post(self.URL, {
            "product_id": str(product.id),
            "quantity": 1,
            "mrn": "MRN-TEST",
        })
        assert response.status_code == 401

    def test_fefo_suggestion_endpoint(self, admin_client, product):
        """FEFO suggestion endpoint returns available lots."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="FEFO-1",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        response = admin_client.get(
            f"/api/lots/fefo_suggestion/?product_id={product.id}"
        )
        assert response.status_code == 200
        assert "lots" in response.data
        assert len(response.data["lots"]) >= 1
