"""
Comprehensive tests for the notifications app: Notification model,
serializers, notification services (emit, expiry scans, low stock scans,
refill scans, task scans), views, and preferences.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.notifications.models import Notification
from apps.notifications.serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer,
)
from apps.notifications.services import (
    emit,
    scan_expiries,
    scan_low_stock,
    scan_refills_due,
    scan_tasks_due,
)
from apps.crm.models import RefillReminder


# ===========================================================================
# Notification Model Tests
# ===========================================================================
class TestNotificationModel:
    """Tests for the Notification model."""

    def test_create_notification(self, db, admin_user):
        """Notification can be created."""
        notif = Notification.objects.create(
            recipient=admin_user,
            notif_type="EXPIRY_WARNING",
            level="WARN",
            channel="IN_APP",
            title="Expiry Warning",
            body="A lot is about to expire.",
        )
        assert notif.id is not None
        assert notif.recipient == admin_user
        assert notif.read is False  # default
        assert notif.level == "WARN"
        assert notif.channel == "IN_APP"

    def test_notification_defaults(self, db, admin_user):
        """Notification has correct defaults."""
        notif = Notification.objects.create(
            recipient=admin_user,
            notif_type="REORDER",
            title="Reorder",
            body="Low stock detected.",
        )
        assert notif.level == "INFO"
        assert notif.channel == "IN_APP"
        assert notif.read is False

    def test_notification_str(self, db, admin_user):
        """String representation includes level and title."""
        notif = Notification.objects.create(
            recipient=admin_user,
            notif_type="STOCKOUT", level="CRITICAL",
            title="STOCKOUT: Paracetamol", body="Out of stock.",
        )
        s = str(notif)
        assert "Critical" in s
        assert "STOCKOUT" in s

    def test_notification_all_levels(self, db, admin_user):
        """Notifications support all severity levels."""
        for level_code, _label in Notification.LEVELS:
            notif = Notification.objects.create(
                recipient=admin_user,
                notif_type="EXPIRY_WARNING",
                level=level_code,
                title="Test",
                body="Test body.",
            )
            assert notif.level == level_code

    def test_notification_all_types(self, db, admin_user):
        """Notifications support all notif types."""
        for type_code, _label in Notification.TYPES:
            notif = Notification.objects.create(
                recipient=admin_user,
                notif_type=type_code,
                title=f"Test {type_code}",
                body="Test.",
            )
            assert notif.notif_type == type_code

    def test_notification_link_optional(self, db, admin_user):
        """Notification link can be null."""
        notif = Notification.objects.create(
            recipient=admin_user,
            notif_type="TASK_DUE",
            title="Task",
            body="Due today.",
        )
        assert notif.link is None

    def test_notification_read_toggle(self, db, admin_user):
        """Notification can be marked as read."""
        notif = Notification.objects.create(
            recipient=admin_user,
            notif_type="REFILL_DUE",
            title="Refill",
            body="Time to refill.",
        )
        notif.read = True
        notif.save(update_fields=["read"])
        notif.refresh_from_db()
        assert notif.read is True

    def test_notification_ordering(self, db, admin_user):
        """Notifications are ordered by -created_at."""
        n1 = Notification.objects.create(
            recipient=admin_user, notif_type="REORDER", title="Older", body=".",
        )
        n2 = Notification.objects.create(
            recipient=admin_user, notif_type="REORDER", title="Newer", body=".",
        )
        notifications = list(Notification.objects.all())
        assert notifications[0].created_at >= notifications[1].created_at


# ===========================================================================
# Notification Serializer Tests
# ===========================================================================
class TestNotificationSerializer:
    """Tests for NotificationSerializer."""

    def test_serialize(self, db, notification):
        """Serializer includes display fields."""
        serializer = NotificationSerializer(notification)
        data = serializer.data
        assert data["title"] == notification.title
        assert data["body"] == notification.body
        assert "level_display" in data
        assert "notif_type_display" in data
        assert "channel_display" in data
        assert data["read"] is False


class TestNotificationPreferenceSerializer:
    """Tests for NotificationPreferenceSerializer."""

    def test_valid_prefs(self, db):
        """Valid preference data is accepted."""
        data = {
            "notif_type": "EXPIRY_WARNING",
            "muted": True,
            "force_email": False,
        }
        serializer = NotificationPreferenceSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_invalid_notif_type(self, db):
        """Invalid notif_type is accepted (no choices validation)."""
        data = {"notif_type": "INVALID", "muted": False, "force_email": False}
        serializer = NotificationPreferenceSerializer(data=data)
        # This passes because it's a plain Serializer with CharField
        assert serializer.is_valid()

    def test_default_values(self, db):
        """Default values for muted and force_email are False."""
        data = {"notif_type": "REORDER"}
        serializer = NotificationPreferenceSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["muted"] is False
        assert serializer.validated_data["force_email"] is False


# ===========================================================================
# Emit Service Tests
# ===========================================================================
class TestEmitService:
    """Tests for the notification emit service."""

    def test_emit_creates_notifications(self, db, admin_user):
        """Emit creates notifications for specified roles."""
        count = emit(
            kind="EXPIRY_WARNING",
            level="WARN",
            subject="Paracetamol",
            detail="Batch expiring soon.",
        )
        assert count >= 1  # admin_user is ADMIN
        notifs = Notification.objects.filter(notif_type="EXPIRY_WARNING")
        assert notifs.count() >= 1

    def test_emit_default_roles(self, db, admin_user, logistics_user):
        """Default roles are LOGISTICS and ADMIN."""
        count = emit(
            kind="REORDER", level="INFO", subject="Test", detail="Detail",
        )
        # Should notify admin and logistics users
        assert count >= 1

    def test_emit_custom_roles(self, db, pharmacist_user):
        """Custom roles can be specified."""
        count = emit(
            kind="REFILL_DUE", level="INFO", subject="Test",
            detail="Detail", roles=["PHARMACIST"],
        )
        assert count >= 1
        notif = Notification.objects.filter(
            recipient=pharmacist_user, notif_type="REFILL_DUE",
        ).first()
        assert notif is not None

    def test_emit_only_active_users(self, db, inactive_user):
        """Inactive users do not receive notifications."""
        # Give inactive user a relevant role
        inactive_user.role = "ADMIN"
        inactive_user.save()
        count = emit(
            kind="REORDER", level="INFO", subject="Test", detail="Detail",
        )
        # Inactive user should not be counted
        notifications_for_inactive = Notification.objects.filter(
            recipient=inactive_user,
        )
        assert notifications_for_inactive.count() == 0

    def test_emit_critical_uses_email_channel(self, db, admin_user):
        """CRITICAL level notifications use EMAIL channel."""
        count = emit(
            kind="STOCKOUT", level="CRITICAL", subject="Test",
            detail="Detail", roles=["ADMIN"],
        )
        notif = Notification.objects.filter(
            recipient=admin_user, notif_type="STOCKOUT",
        ).first()
        assert notif is not None
        assert notif.channel == "EMAIL"

    def test_emit_info_uses_inapp_channel(self, db, admin_user):
        """INFO level notifications use IN_APP channel."""
        count = emit(
            kind="TASK_DUE", level="INFO", subject="Test",
            detail="Detail", roles=["ADMIN"],
        )
        notif = Notification.objects.filter(
            recipient=admin_user, notif_type="TASK_DUE",
        ).first()
        assert notif is not None
        assert notif.channel == "IN_APP"

    def test_emit_survives_broker_failure(self, db, admin_user):
        """In-app notifications persist even when the email broker is down."""
        from unittest.mock import MagicMock, patch

        failing = MagicMock()
        failing.delay.side_effect = Exception("broker unreachable")
        with patch("apps.notifications.services._send_email_notification", failing):
            count = emit(
                kind="STOCKOUT", level="CRITICAL", subject="Test",
                detail="Detail", roles=["ADMIN"],
            )
        assert count >= 1
        assert Notification.objects.filter(
            recipient=admin_user, notif_type="STOCKOUT",
        ).exists()
        failing.delay.assert_called()


# ===========================================================================
# Expiry Scan Service Tests
# ===========================================================================
class TestScanExpiries:
    """Tests for the expiry scanning service."""

    def test_scan_locks_expired_lots(self, db, product):
        """Expired lots are auto-locked."""
        from apps.lots.models import Lot
        lot = Lot.objects.create(
            product=product, batch_number="EXP-TODAY",
            manufacture_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=1),  # yesterday
            quantity=50,
        )
        count = scan_expiries()
        lot.refresh_from_db()
        assert lot.is_locked is True
        assert count >= 1

    def test_scan_lock_updates_product_soh(self, db, product):
        """Auto-locking an expired lot also recomputes the product SOH cache."""
        from apps.lots.models import Lot

        product.soh = 0
        product.save(update_fields=["soh"])
        Lot.objects.create(
            product=product, batch_number="EXP-SOH",
            manufacture_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=1),
            quantity=50,
        )
        Lot.objects.create(
            product=product, batch_number="GOOD-SOH",
            manufacture_date=date.today() - timedelta(days=10),
            expiry_date=date.today() + timedelta(days=365),
            quantity=30,
        )
        scan_expiries()
        product.refresh_from_db()
        # Only the unexpired, unlocked lot counts toward SOH.
        assert product.soh == 30

    def test_scan_alerts_approaching_expiry(self, db, product, admin_user):
        """Lots approaching expiry generate alerts."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="EXP-90",
            manufacture_date=date.today() - timedelta(days=275),
            expiry_date=date.today() + timedelta(days=90),
            quantity=100,
        )
        count = scan_expiries()
        # Should have generated at least one EXPIRY_WARNING notification
        notifs = Notification.objects.filter(notif_type="EXPIRY_WARNING")
        assert notifs.count() >= 1

    def test_scan_no_expired_nothing_happens(self, db, product):
        """No action when all lots are valid."""
        from apps.lots.models import Lot
        Lot.objects.create(
            product=product, batch_number="FUTURE",
            manufacture_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            quantity=100,
        )
        count = scan_expiries()
        # Only scanning for specific windows, most won't match today + 30/60/90 exactly
        assert count >= 0  # should not error


# ===========================================================================
# Low Stock Scan Service Tests
# ===========================================================================
class TestScanLowStock:
    """Tests for low stock scanning service."""

    def test_scan_low_stock_reorder(self, db, product, admin_user):
        """Products below reorder point generate REORDER alerts."""
        # Create a procurement role user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        procurement = User.objects.create_user(
            username="proc2", password="pass", role="PROCUREMENT", is_active=True,
        )
        product.soh = 150  # below reorder_point=200
        product.save()
        count = scan_low_stock()
        assert count >= 1
        notifs = Notification.objects.filter(notif_type="REORDER")
        assert notifs.count() >= 1

    def test_scan_stockout(self, db, product, admin_user):
        """Zero stock generates STOCKOUT alerts."""
        product.soh = 0
        product.save()
        count = scan_low_stock()
        assert count >= 1
        notifs = Notification.objects.filter(notif_type="STOCKOUT")
        assert notifs.count() >= 1

    def test_scan_healthy_no_alerts(self, db, product):
        """Products with sufficient stock generate no alerts."""
        product.soh = 500  # well above reorder_point=200
        product.save()
        before = Notification.objects.count()
        scan_low_stock()
        after = Notification.objects.count()
        assert after == before  # No new notifications


# ===========================================================================
# Refill Due Scan Tests
# ===========================================================================
class TestScanRefillsDue:
    """Tests for refill-due scanning service."""

    def test_scan_refills_due(self, db, contact, product, admin_user):
        """Due refill reminders generate alerts."""
        RefillReminder.objects.create(
            contact=contact,
            product=product,
            interval_days=30,
            next_due_date=date.today() - timedelta(days=1),  # yesterday
            active=True,
        )
        count = scan_refills_due()
        assert count >= 1
        notifs = Notification.objects.filter(notif_type="REFILL_DUE")
        assert notifs.count() >= 1

    def test_scan_future_refills_no_alerts(self, db, contact, product):
        """Future refill reminders generate no alerts."""
        RefillReminder.objects.create(
            contact=contact, product=product,
            interval_days=30,
            next_due_date=date.today() + timedelta(days=10),
            active=True,
        )
        before = Notification.objects.count()
        scan_refills_due()
        after = Notification.objects.count()
        assert after == before

    def test_scan_inactive_refills_no_alerts(self, db, contact, product):
        """Inactive refill reminders generate no alerts."""
        RefillReminder.objects.create(
            contact=contact, product=product,
            interval_days=30,
            next_due_date=date.today() - timedelta(days=1),
            active=False,
        )
        before = Notification.objects.count()
        scan_refills_due()
        after = Notification.objects.count()
        assert after == before


# ===========================================================================
# Task Due Scan Tests
# ===========================================================================
class TestScanTasksDue:
    """Tests for task-due scanning service."""

    def test_scan_tasks_due_today(self, db, sales_user):
        """Tasks due today generate alerts."""
        from apps.crm.models import Task
        task = Task.objects.create(
            title="Urgent task",
            due_date=date.today(),
            assignee=sales_user,
            status="OPEN",
        )
        count = scan_tasks_due()
        assert count >= 1
        task.refresh_from_db()
        assert task.reminder_sent is True

    def test_scan_future_tasks_no_alert(self, db, sales_user):
        """Future tasks generate no alerts."""
        from apps.crm.models import Task
        Task.objects.create(
            title="Future task",
            due_date=date.today() + timedelta(days=7),
            assignee=sales_user,
            status="OPEN",
        )
        before = Notification.objects.count()
        scan_tasks_due()
        after = Notification.objects.count()
        assert after == before

    def test_scan_done_tasks_no_alert(self, db, sales_user):
        """Done tasks generate no alerts."""
        from apps.crm.models import Task
        Task.objects.create(
            title="Done task",
            due_date=date.today(),
            assignee=sales_user,
            status="DONE",
        )
        before = Notification.objects.count()
        scan_tasks_due()
        after = Notification.objects.count()
        assert after == before

    def test_scan_already_reminded(self, db, sales_user):
        """Tasks already reminded are skipped."""
        from apps.crm.models import Task
        Task.objects.create(
            title="Already reminded",
            due_date=date.today(),
            assignee=sales_user,
            status="OPEN",
            reminder_sent=True,
        )
        count = scan_tasks_due()
        assert count == 0


# ===========================================================================
# Notification Views API Tests
# ===========================================================================
class TestNotificationAPI:
    """Tests for Notification API endpoints."""

    URL = "/api/notifications/"

    def test_list_notifications(self, admin_client, notification):
        """User can list their notifications."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_unauthenticated(self, api_client):
        """Unauthenticated users cannot access notifications."""
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_other_users_notifications_not_visible(self, pharmacist_client, notification):
        """User only sees their own notifications."""
        response = pharmacist_client.get(self.URL)
        # notification is for admin_user, not pharmacist
        for item in response.data.get("results", []):
            assert item["recipient"] != str(notification.recipient.id)

    def test_mark_read(self, admin_client, notification):
        """Can mark a notification as read."""
        response = admin_client.patch(f"{self.URL}{notification.id}/read/")
        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.read is True

    def test_read_all(self, admin_client, admin_user):
        """Can mark all notifications as read."""
        Notification.objects.create(
            recipient=admin_user, notif_type="REORDER",
            title="T1", body=".", read=False,
        )
        Notification.objects.create(
            recipient=admin_user, notif_type="STOCKOUT",
            title="T2", body=".", read=False,
        )
        response = admin_client.patch(f"{self.URL}read_all/")
        assert response.status_code == 200
        assert response.data["marked_read"] >= 2

    def test_unread_count(self, admin_client, admin_user):
        """Unread count returns correct number."""
        Notification.objects.create(
            recipient=admin_user, notif_type="REORDER",
            title="Unread", body=".", read=False,
        )
        response = admin_client.get(f"{self.URL}unread_count/")
        assert response.status_code == 200
        assert response.data["unread_count"] >= 1

    def test_filter_by_read(self, admin_client, admin_user):
        """Can filter notifications by read status."""
        Notification.objects.create(
            recipient=admin_user, notif_type="REORDER",
            title="Read", body=".", read=True,
        )
        response = admin_client.get(f"{self.URL}?read=1")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["read"] is True

    def test_filter_by_type(self, admin_client, notification):
        """Can filter notifications by type."""
        response = admin_client.get(f"{self.URL}?type=EXPIRY_WARNING")
        assert response.status_code == 200
        for item in response.data["results"]:
            assert item["notif_type"] == "EXPIRY_WARNING"

    def test_notification_preferences(self, admin_client):
        """Can get and update notification preferences."""
        # GET
        response = admin_client.get(f"{self.URL}preferences/")
        assert response.status_code == 200
        assert isinstance(response.data, list)

        # PUT
        prefs_data = [
            {"notif_type": "EXPIRY_WARNING", "muted": True, "force_email": False},
        ]
        response = admin_client.put(
            f"{self.URL}preferences/", prefs_data, format="json",
        )
        assert response.status_code == 200
