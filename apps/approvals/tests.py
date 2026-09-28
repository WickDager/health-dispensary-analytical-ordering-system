"""
Comprehensive tests for the approvals, LLM schemas, ingest, and audit apps.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from apps.approvals.models import ApprovalRequest
from apps.approvals.serializers import ApprovalRequestSerializer
from apps.llm.schemas import LineItem, InvoiceExtraction
from apps.llm.models import LLMProviderConfig
from apps.llm.adapters import BaseLLMAdapter, INVOICE_SYSTEM_PROMPT
from apps.audit.models import AuditLog, AIIngestAudit


# ===========================================================================
# Approval Model Tests
# ===========================================================================
class TestApprovalRequestModel:
    """Tests for ApprovalRequest model."""

    def test_create_approval_request(self, db, admin_user):
        """Approval request can be created."""
        approval = ApprovalRequest.objects.create(
            action_type="USER_ACTIVATE",
            payload={"user_id": str(uuid.uuid4())},
            requested_by=admin_user,
        )
        assert approval.id is not None
        assert approval.action_type == "USER_ACTIVATE"
        assert approval.status == "PENDING"  # default

    def test_approval_all_action_types(self, db, admin_user):
        """All action types are supported."""
        for action_code, _label in ApprovalRequest.ACTION_CHOICES:
            approval = ApprovalRequest.objects.create(
                action_type=action_code,
                payload={"test": True},
                requested_by=admin_user,
            )
            assert approval.action_type == action_code

    def test_approval_str(self, db, approval_request):
        """String representation is descriptive."""
        s = str(approval_request)
        assert "Activate" in s  # action_type display
        assert "Pending" in s  # status display

    def test_approval_payload_json(self, db, admin_user):
        """Payload accepts any JSON-serializable data."""
        payload = {
            "user_id": "abc-123",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }
        approval = ApprovalRequest.objects.create(
            action_type="STOCK_ADJUST",
            payload=payload,
            requested_by=admin_user,
        )
        approval.refresh_from_db()
        assert approval.payload == payload

    def test_approval_reviewed_by_nullable(self, db, admin_user):
        """Reviewed by is null before review."""
        approval = ApprovalRequest.objects.create(
            action_type="ROLE_CHANGE",
            payload={"user_id": "x"},
            requested_by=admin_user,
        )
        assert approval.reviewed_by is None
        assert approval.reviewed_at is None

    def test_approval_reason_nullable(self, db, admin_user):
        """Reason is nullable."""
        approval = ApprovalRequest.objects.create(
            action_type="ORDER_SUBMIT",
            payload={"order_id": "x"},
            requested_by=admin_user,
        )
        assert approval.reason is None


# ===========================================================================
# Approval Handler Tests
# ===========================================================================
class TestApprovalHandlers:
    """Tests for approval action handlers."""

    def test_user_activate(self, db, inactive_user):
        """USER_ACTIVATE handler activates a user."""
        from apps.approvals.handlers import handle_user_activate
        handle_user_activate({"user_id": str(inactive_user.id)})
        inactive_user.refresh_from_db()
        assert inactive_user.is_active is True

    def test_role_change(self, db, pharmacist_user):
        """ROLE_CHANGE handler changes a user's role."""
        from apps.approvals.handlers import handle_role_change
        handle_role_change({
            "user_id": str(pharmacist_user.id),
            "new_role": "ADMIN",
        })
        pharmacist_user.refresh_from_db()
        assert pharmacist_user.role == "ADMIN"

    def test_stock_adjust(self, db, product):
        """STOCK_ADJUST handler adjusts product SOH."""
        from apps.approvals.handlers import handle_stock_adjust
        original_soh = product.soh
        handle_stock_adjust({
            "product_id": str(product.id),
            "adjustment": 100,
        })
        product.refresh_from_db()
        assert product.soh == original_soh + 100

    def test_stock_adjust_negative_no_below_zero(self, db, product):
        """Stock adjustment floors at 0."""
        from apps.approvals.handlers import handle_stock_adjust
        product.soh = 10
        product.save()
        handle_stock_adjust({
            "product_id": str(product.id),
            "adjustment": -100,
        })
        product.refresh_from_db()
        assert product.soh == 0

    def test_order_submit(self, db, order):
        """ORDER_SUBMIT handler marks order as SENT."""
        from apps.approvals.handlers import handle_order_submit
        handle_order_submit({"order_id": str(order.id)})
        order.refresh_from_db()
        assert order.status == "SENT"

    def test_product_delete(self, db, product):
        """PRODUCT_DELETE handler deletes a product."""
        from apps.approvals.handlers import handle_product_delete
        product_id = product.id
        handle_product_delete({"product_id": str(product_id)})
        with pytest.raises(Exception):
            from apps.catalog.models import Product
            Product.objects.get(pk=product_id)

    def test_lot_unlock(self, db, lot):
        """LOT_UNLOCK handler unlocks a locked lot."""
        from apps.approvals.handlers import handle_lot_unlock
        lot.is_locked = True
        lot.save()
        handle_lot_unlock({"lot_id": str(lot.id)})
        lot.refresh_from_db()
        assert lot.is_locked is False

    def test_ai_commit(self, db, product):
        """AI_COMMIT handler commits validated ingestion into inventory."""
        from apps.approvals.handlers import handle_ai_commit
        from apps.lots.models import Lot

        product.soh = 0
        product.save(update_fields=["soh"])
        validated_data = {
            "invoice_number": "INV-001",
            "supplier_name": "PharmaCorp",
            "line_items": [{"description": product.name, "quantity": 10, "unit_price": 5.0, "line_total": 50.0}],
        }
        handle_ai_commit({"validated_data": validated_data})
        log = AuditLog.objects.filter(action="AI_INGEST_COMMIT").first()
        assert log is not None
        # Inventory actually changed
        assert Lot.objects.filter(product=product, batch_number="INV-001-L1").exists()
        product.refresh_from_db()
        assert product.soh == 10

    def test_contact_bulk_export(self, db):
        """CONTACT_BULK_EXPORT handler logs the action."""
        from apps.approvals.handlers import handle_contact_bulk_export
        handle_contact_bulk_export({"filters": {"contact_type": "PATIENT"}})
        log = AuditLog.objects.filter(action="CONTACT_BULK_EXPORT").first()
        assert log is not None

    def test_approval_execute(self, db, inactive_user, admin_user):
        """ApprovalRequest.execute() dispatches to the correct handler."""
        approval = ApprovalRequest.objects.create(
            action_type="USER_ACTIVATE",
            payload={"user_id": str(inactive_user.id)},
            requested_by=admin_user,
        )
        approval.execute()
        inactive_user.refresh_from_db()
        assert inactive_user.is_active is True


# ===========================================================================
# Approval Views API Tests
# ===========================================================================
class TestApprovalAPI:
    """Tests for the Approval API."""

    URL = "/api/approvals/"

    def test_list_approvals_admin(self, admin_client, approval_request):
        """Admin can list pending approvals."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_approvals_non_admin(self, pharmacist_client):
        """Non-admin cannot list approvals."""
        response = pharmacist_client.get(self.URL)
        assert response.status_code == 403

    def test_approve_request(self, admin_client, inactive_user):
        """Admin can approve a request."""
        approval = ApprovalRequest.objects.create(
            action_type="USER_ACTIVATE",
            payload={"user_id": str(inactive_user.id)},
            requested_by=admin_client.handler._force_user,
        )
        response = admin_client.post(f"{self.URL}{approval.id}/approve/")
        assert response.status_code == 200
        assert response.data["status"] == "APPROVED"

    def test_reject_request(self, admin_client, approval_request):
        """Admin can reject a request with reason."""
        response = admin_client.post(
            f"{self.URL}{approval_request.id}/reject/",
            {"reason": "Not needed"},
        )
        assert response.status_code == 200
        assert response.data["status"] == "REJECTED"
        approval_request.refresh_from_db()
        assert approval_request.reason == "Not needed"

    def test_reject_request_accepts_notes_alias(self, admin_client, approval_request):
        """Reject also accepts `notes` (legacy client field) as the reason."""
        response = admin_client.post(
            f"{self.URL}{approval_request.id}/reject/",
            {"notes": "Wrong supplier"},
        )
        assert response.status_code == 200
        approval_request.refresh_from_db()
        assert approval_request.reason == "Wrong supplier"

    def test_approve_already_processed(self, admin_client, approval_request):
        """Cannot approve an already processed request."""
        approval_request.status = "APPROVED"
        approval_request.save()
        response = admin_client.post(
            f"{self.URL}{approval_request.id}/approve/"
        )
        assert response.status_code == 400

    def test_reject_already_processed(self, admin_client, approval_request):
        """Cannot reject an already processed request."""
        approval_request.status = "REJECTED"
        approval_request.save()
        response = admin_client.post(
            f"{self.URL}{approval_request.id}/reject/"
        )
        assert response.status_code == 400

    def test_filter_by_status(self, admin_client, approval_request):
        """Can filter approvals by status."""
        response = admin_client.get(f"{self.URL}?status=PENDING")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["status"] == "PENDING"


# ===========================================================================
# Pydantic Schema Tests (LLM Validation)
# ===========================================================================
class TestLineItemSchema:
    """Tests for LineItem Pydantic schema."""

    def test_valid_line_item(self):
        """Valid line item passes validation."""
        item = LineItem(
            description="Paracetamol 500mg tablets",
            quantity=100,
            unit_price=0.15,
            line_total=15.00,
        )
        assert item.description == "Paracetamol 500mg tablets"
        assert item.quantity == 100

    def test_quantity_must_be_positive(self):
        """Quantity must be > 0."""
        with pytest.raises(Exception):
            LineItem(description="Test", quantity=0, unit_price=1.0, line_total=1.0)
        with pytest.raises(Exception):
            LineItem(description="Test", quantity=-5, unit_price=1.0, line_total=1.0)

    def test_unit_price_must_be_positive(self):
        """Unit price must be > 0."""
        with pytest.raises(Exception):
            LineItem(description="Test", quantity=1, unit_price=0, line_total=1.0)
        with pytest.raises(Exception):
            LineItem(description="Test", quantity=1, unit_price=-1.0, line_total=1.0)

    def test_line_total_must_be_positive(self):
        """Line total must be > 0."""
        with pytest.raises(Exception):
            LineItem(description="Test", quantity=1, unit_price=1.0, line_total=0)

    def test_description_empty(self):
        """Description cannot be empty."""
        with pytest.raises(Exception):
            LineItem(description="", quantity=1, unit_price=1.0, line_total=1.0)

    def test_description_max_length(self):
        """Description max 500 chars."""
        LineItem(description="A" * 500, quantity=1, unit_price=1.0, line_total=1.0)
        with pytest.raises(Exception):
            LineItem(description="A" * 501, quantity=1, unit_price=1.0, line_total=1.0)

    def test_line_total_cross_validation_accepts_close_match(self):
        """Line items with close-enough math pass."""
        item = LineItem(
            description="Test",
            quantity=3,
            unit_price=1.3333,
            line_total=4.0,  # 3 * 1.3333 = 3.9999, close to 4.0
        )
        assert item.line_total == 4.0


class TestInvoiceExtractionSchema:
    """Tests for InvoiceExtraction Pydantic schema."""

    def test_valid_extraction(self):
        """Valid extraction passes validation."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-001",
            invoice_date=date.today(),
            supplier_name="PharmaCorp Ltd",
            currency="USD",
            subtotal=100.0,
            tax=10.0,
            total=110.0,
            line_items=[
                LineItem(
                    description="Product A",
                    quantity=10,
                    unit_price=5.0,
                    line_total=50.0,
                ),
                LineItem(
                    description="Product B",
                    quantity=10,
                    unit_price=5.0,
                    line_total=50.0,
                ),
            ],
        )
        assert extraction.invoice_number == "INV-2024-001"
        assert extraction.currency == "USD"
        assert len(extraction.line_items) == 2

    def test_minimal_extraction(self):
        """Extraction with all optional fields None passes."""
        extraction = InvoiceExtraction()
        assert extraction.invoice_number is None
        assert extraction.invoice_date is None
        assert extraction.line_items == []

    def test_currency_normalization(self):
        """Currency is normalized to uppercase."""
        extraction = InvoiceExtraction(currency="usd")
        assert extraction.currency == "USD"

    def test_currency_invalid(self):
        """Invalid currency length is rejected."""
        with pytest.raises(Exception):
            InvoiceExtraction(currency="USDD")

    def test_date_parsing_iso(self):
        """ISO date format parsed correctly."""
        extraction = InvoiceExtraction(invoice_date="2024-03-15")
        assert extraction.invoice_date == date(2024, 3, 15)

    def test_date_parsing_slash(self):
        """Slash date format parsed correctly."""
        extraction = InvoiceExtraction(invoice_date="15/03/2024")
        assert extraction.invoice_date == date(2024, 3, 15)

    def test_date_parsing_dash(self):
        """Dash date format parsed correctly."""
        extraction = InvoiceExtraction(invoice_date="15-03-2024")
        assert extraction.invoice_date == date(2024, 3, 15)

    def test_date_parsing_long(self):
        """Long date format parsed correctly."""
        extraction = InvoiceExtraction(invoice_date="15 March 2024")
        assert extraction.invoice_date == date(2024, 3, 15)

    def test_date_parsing_us_long(self):
        """US long date format parsed correctly."""
        extraction = InvoiceExtraction(invoice_date="March 15, 2024")
        assert extraction.invoice_date == date(2024, 3, 15)

    def test_date_parsing_invalid(self):
        """Invalid date returns None."""
        extraction = InvoiceExtraction(invoice_date="not a date")
        assert extraction.invoice_date is None

    def test_invoice_number_max_length(self):
        """Invoice number max 128 chars."""
        extraction = InvoiceExtraction(invoice_number="A" * 128)
        assert extraction.invoice_number == "A" * 128
        with pytest.raises(Exception):
            InvoiceExtraction(invoice_number="A" * 129)

    def test_supplier_name_max_length(self):
        """Supplier name max 255 chars."""
        extraction = InvoiceExtraction(supplier_name="A" * 255)
        assert extraction.supplier_name == "A" * 255
        with pytest.raises(Exception):
            InvoiceExtraction(supplier_name="A" * 256)

    def test_totals_cross_check_accepts(self):
        """Acceptable totals pass."""
        extraction = InvoiceExtraction(
            subtotal=100.0, tax=10.0, total=110.0,
        )
        assert extraction.subtotal == 100.0


# ===========================================================================
# LLM Adapter Tests
# ===========================================================================
class TestLLMAdapterParse:
    """Tests for LLM response parsing."""

    def test_parse_plain_json(self):
        """Plain JSON is parsed correctly."""
        from apps.llm.adapters import BaseLLMAdapter

        class TestAdapter(BaseLLMAdapter):
            def extract_invoice(self, text):
                pass

        adapter = TestAdapter(api_key="test", model="test")
        result = adapter._parse_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_markdown_fenced_json(self):
        """Markdown-fenced JSON is parsed correctly."""
        from apps.llm.adapters import BaseLLMAdapter

        class TestAdapter(BaseLLMAdapter):
            def extract_invoice(self, text):
                pass

        adapter = TestAdapter(api_key="test", model="test")
        result = adapter._parse_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_markdown_fenced_no_lang(self):
        """Markdown fence without language works."""
        from apps.llm.adapters import BaseLLMAdapter

        class TestAdapter(BaseLLMAdapter):
            def extract_invoice(self, text):
                pass

        adapter = TestAdapter(api_key="test", model="test")
        result = adapter._parse_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invoice_system_prompt_contains_schema(self):
        """System prompt includes the expected schema."""
        assert "line_items" in INVOICE_SYSTEM_PROMPT
        assert "invoice_number" in INVOICE_SYSTEM_PROMPT
        assert "supplier_name" in INVOICE_SYSTEM_PROMPT
        assert "quantity" in INVOICE_SYSTEM_PROMPT


# ===========================================================================
# LLM Provider Config Tests
# ===========================================================================
class TestLLMProviderConfig:
    """Tests for LLMProviderConfig model."""

    def test_create_config(self, db):
        """Provider config can be created."""
        config = LLMProviderConfig.objects.create(
            name="gemini",
            enabled=True,
            is_default=True,
            model="gemini-2.0-flash",
            fallback_priority=1,
        )
        assert config.name == "gemini"
        assert config.enabled is True
        assert config.is_default is True

    def test_config_str(self, db):
        """String representation is descriptive."""
        config = LLMProviderConfig.objects.create(
            name="openai", model="gpt-4o",
        )
        s = str(config)
        assert "openai" in s.lower() or "OpenAI" in s

    def test_all_providers(self, db):
        """All 5 provider types can be created."""
        for provider_code in ("gemini", "claude", "openai", "deepseek", "openrouter"):
            config = LLMProviderConfig.objects.create(
                name=provider_code, model="test-model",
            )
            assert config.name == provider_code

    def test_default_fallback_priority(self, db):
        """Default fallback priority is 100."""
        config = LLMProviderConfig.objects.create(
            name="gemini", model="test",
        )
        assert config.fallback_priority == 100

    def test_encrypted_api_key_nullable(self, db):
        """API key can be null."""
        config = LLMProviderConfig.objects.create(
            name="gemini", model="test",
        )
        assert config.encrypted_api_key is None


# ===========================================================================
# LLM Gateway Tests
# ===========================================================================
class TestLLMGateway:
    """Tests for LLM gateway functions."""

    def test_get_provider_chain_empty_if_none_enabled(self, db):
        """Empty chain if no providers enabled."""
        from apps.llm.gateway import get_provider_chain
        chain = get_provider_chain()
        assert len(chain) == 0

    def test_get_provider_chain_only_enabled(self, db):
        """Only enabled providers are returned."""
        LLMProviderConfig.objects.create(
            name="gemini", enabled=True, model="gemini", fallback_priority=1,
        )
        LLMProviderConfig.objects.create(
            name="claude", enabled=False, model="claude", fallback_priority=2,
        )
        from apps.llm.gateway import get_provider_chain
        chain = get_provider_chain()
        assert len(chain) == 1
        assert chain[0].name == "gemini"

    def test_get_provider_chain_ordered(self, db):
        """Providers ordered by fallback_priority."""
        LLMProviderConfig.objects.create(
            name="claude", enabled=True, model="c", fallback_priority=2,
        )
        LLMProviderConfig.objects.create(
            name="gemini", enabled=True, model="g", fallback_priority=1,
        )
        from apps.llm.gateway import get_provider_chain
        chain = get_provider_chain()
        assert chain[0].name == "gemini"
        assert chain[1].name == "claude"

    def test_extract_invoice_no_providers(self, db):
        """Raises when no providers are enabled."""
        from apps.llm.gateway import extract_invoice, AllProvidersFailed
        with pytest.raises(AllProvidersFailed) as exc:
            extract_invoice("some text")
        # Error message varies - just check it's an AllProvidersFailed
        assert "provider" in str(exc.value).lower()


# ===========================================================================
# Ingest Serializer Tests
# ===========================================================================
class TestIngestSerializers:
    """Tests for ingest serializers."""

    def test_invoice_upload_valid(self, db):
        """Valid invoice upload data is accepted."""
        from apps.ingest.serializers import InvoiceUploadSerializer
        data = {"text": "Invoice #12345\nSupplier: PharmaCorp\nLine items: ..."}
        serializer = InvoiceUploadSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_invoice_upload_empty_text(self, db):
        """Empty text is rejected."""
        from apps.ingest.serializers import InvoiceUploadSerializer
        serializer = InvoiceUploadSerializer(data={"text": ""})
        assert not serializer.is_valid()

    def test_invoice_upload_text_too_long(self, db):
        """Text exceeding max length is rejected."""
        from apps.ingest.serializers import InvoiceUploadSerializer
        serializer = InvoiceUploadSerializer(data={"text": "X" * 100001})
        assert not serializer.is_valid()

    def test_commit_ingestion_valid(self, db):
        """Valid commit data is accepted."""
        from apps.ingest.serializers import CommitIngestionSerializer
        data = {"audit_id": str(uuid.uuid4())}
        serializer = CommitIngestionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_commit_ingestion_invalid_uuid(self, db):
        """Invalid UUID is rejected."""
        from apps.ingest.serializers import CommitIngestionSerializer
        serializer = CommitIngestionSerializer(data={"audit_id": "not-a-uuid"})
        assert not serializer.is_valid()


# ===========================================================================
# Ingest Services Tests
# ===========================================================================
class TestIngestService:
    """Tests for ingest services."""

    def test_commit_ingestion(self, db, product):
        """Commit ingestion creates a matched lot, updates SOH, and logs."""
        from apps.ingest.services import commit_ingestion
        from apps.lots.models import Lot

        product.soh = 0
        product.save(update_fields=["soh"])
        validated_data = {
            "invoice_number": "INV-001",
            "supplier_name": "PharmaCorp",
            "line_items": [
                {"description": product.name, "quantity": 10, "unit_price": 5.0, "line_total": 50.0},
                {"description": "No Such Product Anywhere", "quantity": 5, "unit_price": 1.0, "line_total": 5.0},
            ],
        }
        result = commit_ingestion(
            validated_data=validated_data,
            user=None,
        )
        assert result["status"] == "committed"
        assert result["invoice_number"] == "INV-001"
        # Only the matched line becomes a lot
        assert result["line_items_committed"] == 1
        assert len(result["unmatched_lines"]) == 1
        assert result["unmatched_lines"][0]["description"] == "No Such Product Anywhere"

        # A lot was created with the invoiced quantity and SOH recomputed
        lot = Lot.objects.filter(batch_number="INV-001-L1").first()
        assert lot is not None
        assert lot.quantity == 10
        product.refresh_from_db()
        assert product.soh == 10

        log = AuditLog.objects.filter(action="AI_INGEST_COMMIT").first()
        assert log is not None

    def test_commit_ingestion_redelivery_tops_up(self, db, product):
        """Committing the same invoice twice tops up the lot, no duplicate."""
        from apps.ingest.services import commit_ingestion
        from apps.lots.models import Lot

        validated_data = {
            "invoice_number": "INV-002",
            "supplier_name": "PharmaCorp",
            "line_items": [
                {"description": product.name, "quantity": 7, "unit_price": 5.0, "line_total": 35.0},
            ],
        }
        commit_ingestion(validated_data=validated_data, user=None)
        commit_ingestion(validated_data=validated_data, user=None)
        lots = Lot.objects.filter(batch_number="INV-002-L1")
        assert lots.count() == 1
        assert lots.first().quantity == 14
        product.refresh_from_db()
        assert product.soh == 14


class TestIngestStatusAPI:
    """Regression tests for per-task ingest status polling.

    The status endpoint must honour the task_id captured when the upload
    was queued, not just return the user's latest audit row.
    """

    URL = "/api/ingest/"

    def _make_audit(self, user, task_id=None):
        return AIIngestAudit.objects.create(
            provider="test", model="test-model",
            raw_output={}, latency_ms=1, succeeded=True,
            created_by=user, task_id=task_id,
        )

    def test_status_returns_task_specific_audit(self, admin_client):
        """GET /ingest/{task_id}/status/ returns the audit for that task."""
        user = admin_client.handler._force_user
        self._make_audit(user)  # older audit, different task
        target = self._make_audit(user, task_id="11111111-1111-1111-1111-111111111111")
        response = admin_client.get(f"{self.URL}{target.task_id}/status/")
        assert response.status_code == 200
        assert response.data["data"]["id"] == str(target.id)

    def test_status_without_task_id_returns_latest(self, admin_client):
        """GET /ingest/status/ returns the newest audit for the user."""
        user = admin_client.handler._force_user
        self._make_audit(user)
        latest = self._make_audit(user)
        response = admin_client.get(f"{self.URL}status/")
        assert response.status_code == 200
        assert response.data["data"]["id"] == str(latest.id)

    def test_status_unknown_task_falls_back_to_latest(self, admin_client):
        """Unknown task_id falls back to the latest audit (back-compat)."""
        user = admin_client.handler._force_user
        latest = self._make_audit(user)
        response = admin_client.get(
            f"{self.URL}22222222-2222-2222-2222-222222222222/status/"
        )
        assert response.status_code == 200
        assert response.data["data"]["id"] == str(latest.id)


class TestProcessInvoiceTaskId:
    """The task id recorded on AIIngestAudit must always be pollable."""

    def test_lot_filterset_works(self, admin_client, lot):
        """Regression: LotViewSet must actually apply filterset/search params.

        filter_backends were never wired in, so /lots/?is_locked=true and
        ?search= silently ignored every filter.
        """
        response = admin_client.get("/api/lots/?is_locked=false")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["is_locked"] is False

        response = admin_client.get(
            f"/api/lots/?search={lot.batch_number}"
        )
        assert response.status_code == 200
        ids = [item["id"] for item in response.data["results"]]
        assert str(lot.id) in ids
        assert len(ids) == 1

    def test_order_filterset_works(self, admin_client, order):
        """Regression: OrderViewSet must actually apply filterset params."""
        response = admin_client.get("/api/orders/?status=PENDING")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["status"] == "PENDING"
        assert str(order.id) in [i["id"] for i in response.data["results"]]


class TestProductDeleteGuard:
    """Regression: deleting a product with lots must be refused, not cascade."""

    def test_delete_product_with_lots_returns_409(self, admin_client, product, lot):
        """Lot.product is PROTECT; API surfaces it as a clean 409."""
        from apps.catalog.models import Product

        response = admin_client.delete(f"/api/products/{product.id}/")
        assert response.status_code == 409
        assert Product.objects.filter(pk=product.id).exists()

    def test_delete_product_without_lots_succeeds(self, admin_client, db, supplier):
        from apps.catalog.models import Product

        p = Product.objects.create(
            name="DELE-TMP", api="T", strength="1mg", supplier=supplier,
        )
        response = admin_client.delete(f"/api/products/{p.id}/")
        assert response.status_code == 204
        assert not Product.objects.filter(pk=p.id).exists()


class TestRequestActivationAction:
    """POST /api/approvals/request_activation/ closes the registration
    approval loop through the API."""

    def test_request_activation_full_loop(self, admin_client, inactive_user):
        response = admin_client.post(
            "/api/approvals/request_activation/",
            {"user_id": str(inactive_user.id)},
        )
        assert response.status_code == 202
        approval = ApprovalRequest.objects.get(pk=response.data["approval_id"])
        assert approval.action_type == "USER_ACTIVATE"
        assert approval.status == "PENDING"

        resp2 = admin_client.post(f"/api/approvals/{approval.id}/approve/")
        assert resp2.status_code == 200
        inactive_user.refresh_from_db()
        assert inactive_user.is_active is True

    def test_request_activation_rejects_active_user(self, admin_client, admin_user):
        response = admin_client.post(
            "/api/approvals/request_activation/",
            {"user_id": str(admin_user.id)},
        )
        assert response.status_code == 400

    def test_request_activation_requires_user_id(self, admin_client):
        response = admin_client.post("/api/approvals/request_activation/", {})
        assert response.status_code == 400

    def test_process_invoice_records_task_id_without_broker(self, db):
        """Direct (synchronous) execution still records a UUID task id."""
        from apps.ingest import tasks as ingest_tasks

        validated = {"invoice_number": "INV-SYNC", "supplier_name": "S", "line_items": []}
        with patch.object(ingest_tasks, "extract_invoice", return_value=validated):
            result = ingest_tasks.process_invoice(text="some invoice text")

        assert result["succeeded"] is True
        assert result["task_id"]
        uuid.UUID(result["task_id"])  # must be a valid UUID (URL route only accepts UUIDs)
        audit = AIIngestAudit.objects.get(task_id=result["task_id"])
        assert audit.succeeded is True

    def test_upload_sync_fallback_returns_task_id(self, admin_client):
        """Broker down: upload response still carries a pollable task_id."""
        from apps.ingest import tasks as ingest_tasks

        validated = {"invoice_number": "INV-SYNC2", "supplier_name": "S", "line_items": []}
        with patch.object(ingest_tasks.process_invoice, "delay",
                          side_effect=Exception("no broker")), \
                patch.object(ingest_tasks, "extract_invoice", return_value=validated):
            response = admin_client.post("/api/ingest/", {"text": "invoice text"}, format="json")

        assert response.status_code == 200
        assert response.data["task_id"]
        assert response.data["status"] == "completed"
        assert AIIngestAudit.objects.filter(task_id=response.data["task_id"]).exists()


# ===========================================================================
# Audit Model Tests
# ===========================================================================
class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_create_audit_log(self, db, admin_user):
        """Audit log can be created."""
        log = AuditLog.objects.create(
            action="DISPENSE",
            category="CLINICAL",
            details={"product": "Paracetamol", "quantity": 30},
            user=admin_user,
        )
        assert log.id is not None
        assert log.action == "DISPENSE"
        assert log.category == "CLINICAL"
        assert log.details == {"product": "Paracetamol", "quantity": 30}

    def test_audit_log_str(self, db, admin_user):
        """String representation includes category and action."""
        log = AuditLog.objects.create(
            action="TEST", category="CLINICAL",
            details={}, user=admin_user,
        )
        s = str(log)
        assert "CLINICAL" in s
        assert "TEST" in s

    def test_audit_log_user_nullable(self, db):
        """User can be null."""
        log = AuditLog.objects.create(
            action="SYSTEM_EVENT", category="SYSTEM", details={},
        )
        assert log.user is None

    def test_audit_log_ordering(self, db):
        """Audit logs ordered by -timestamp."""
        log1 = AuditLog.objects.create(action="A", category="T", details={})
        log2 = AuditLog.objects.create(action="B", category="T", details={})
        logs = list(AuditLog.objects.all())
        assert logs[0].timestamp >= logs[1].timestamp


class TestAIIngestAuditModel:
    """Tests for AIIngestAudit model."""

    def test_create_ai_audit(self, db, admin_user):
        """AI ingest audit can be created."""
        audit = AIIngestAudit.objects.create(
            provider="gemini",
            model="gemini-2.0-flash",
            raw_output={"raw": "data"},
            validated_output={"clean": "data"},
            latency_ms=1500,
            input_tokens=500,
            output_tokens=200,
            est_cost_usd=0.005,
            succeeded=True,
            created_by=admin_user,
        )
        assert audit.id is not None
        assert audit.provider == "gemini"
        assert audit.succeeded is True
        assert audit.latency_ms == 1500

    def test_ai_audit_str(self, db):
        """String representation is descriptive."""
        audit = AIIngestAudit.objects.create(
            provider="openai", model="gpt-4o",
            raw_output={}, latency_ms=100,
        )
        s = str(audit)
        assert "openai" in s.lower() or "OpenAI" in s

    def test_ai_audit_failed(self, db):
        """Failed audit is recorded."""
        audit = AIIngestAudit.objects.create(
            provider="claude", model="claude-sonnet",
            raw_output={}, latency_ms=5000, succeeded=False,
        )
        assert audit.succeeded is False
        assert "OK" not in str(audit)
