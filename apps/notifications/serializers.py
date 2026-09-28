from __future__ import annotations
from rest_framework import serializers
from apps.notifications.models import Notification


# ---------------------------------------------------------------------------
# NotificationSerializer
# ---------------------------------------------------------------------------
class NotificationSerializer(serializers.ModelSerializer):
    level_display = serializers.SerializerMethodField()
    notif_type_display = serializers.SerializerMethodField()
    channel_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "notif_type",
            "notif_type_display",
            "level",
            "level_display",
            "channel",
            "channel_display",
            "title",
            "body",
            "link",
            "read",
            "created_at",
        ]
        read_only_fields = fields

    def get_level_display(self, obj):
        return obj.get_level_display()

    def get_notif_type_display(self, obj):
        return obj.get_notif_type_display()

    def get_channel_display(self, obj):
        return obj.get_channel_display()


# ---------------------------------------------------------------------------
# NotificationPreferenceSerializer
#
# Plain Serializer (not ModelSerializer).  The ViewSet stores preferences
# in an in-memory dict keyed by user id.  Replace with a
# NotificationPreference model + ModelSerializer when persistence is needed.
# ---------------------------------------------------------------------------
class NotificationPreferenceSerializer(serializers.Serializer):
    """Per-user per-notification-type preferences (notif_type, muted, force_email)."""
    notif_type = serializers.CharField(max_length=20)
    muted = serializers.BooleanField(default=False)
    force_email = serializers.BooleanField(default=False)
