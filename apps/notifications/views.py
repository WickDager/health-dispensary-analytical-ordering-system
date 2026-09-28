from __future__ import annotations
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationViewSet(ReadOnlyModelViewSet):
    """Read-only viewset for the authenticated user's notifications."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)

        # Optional filtering
        read_param = self.request.query_params.get("read")
        if read_param is not None:
            is_read = read_param.lower() in ("1", "true", "yes")
            qs = qs.filter(read=is_read)

        notif_type = self.request.query_params.get("type")
        if notif_type:
            qs = qs.filter(notif_type=notif_type.upper())

        return qs.order_by("-created_at")

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["patch"])
    def read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.read = True
        notification.save(update_fields=["read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["patch"])
    def read_all(self, request):
        """Mark all unread notifications as read for the current user."""
        updated = Notification.objects.filter(recipient=request.user, read=False).update(read=True)
        return Response({"marked_read": updated})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Badge count of unread notifications."""
        count = Notification.objects.filter(recipient=request.user, read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["get", "put"])
    def preferences(self, request):
        """
        GET  -- return a list of per-notification-type preferences for the user.
        PUT  -- accept a list of {notif_type, muted, force_email} dicts.
        """
        if request.method == "GET":
            prefs = _get_user_prefs(request.user)
            serializer = NotificationPreferenceSerializer(prefs, many=True)
            return Response(serializer.data)

        # PUT
        serializer = NotificationPreferenceSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        _save_user_prefs(request.user, serializer.validated_data)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# In-memory preference store (replace with NotificationPreference model later)
# ---------------------------------------------------------------------------
_USER_PREFS: dict[str, list[dict]] = {}  # user_id -> list of pref dicts

_DEFAULT_PREFS = [
    {"notif_type": "EXPIRY_WARNING", "muted": False, "force_email": False},
    {"notif_type": "STOCKOUT", "muted": False, "force_email": False},
    {"notif_type": "REORDER", "muted": False, "force_email": False},
    {"notif_type": "REFILL_DUE", "muted": False, "force_email": False},
    {"notif_type": "TASK_DUE", "muted": False, "force_email": False},
    {"notif_type": "APPROVAL_PENDING", "muted": False, "force_email": False},
    {"notif_type": "DEAL_UPDATE", "muted": False, "force_email": False},
]


def _get_user_prefs(user) -> list[dict]:
    key = str(user.id)
    if key not in _USER_PREFS:
        _USER_PREFS[key] = [dict(p) for p in _DEFAULT_PREFS]
    return _USER_PREFS[key]


def _save_user_prefs(user, incoming: list[dict]):
    key = str(user.id)
    current = {p["notif_type"]: p for p in _get_user_prefs(user)}
    for item in incoming:
        nt = item["notif_type"]
        if nt in current:
            current[nt]["muted"] = item.get("muted", current[nt]["muted"])
            current[nt]["force_email"] = item.get("force_email", current[nt]["force_email"])
        else:
            current[nt] = {"notif_type": nt, "muted": item.get("muted", False), "force_email": item.get("force_email", False)}
    _USER_PREFS[key] = list(current.values())
