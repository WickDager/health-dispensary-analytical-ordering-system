from __future__ import annotations

from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ("id", "timestamp", "user_name", "action", "category", "details")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    """
    GET /api/audit/ — list audit log entries, newest first.
    Optional ?search= filters action/category/details.
    """
    qs = AuditLog.objects.select_related("user").order_by("-timestamp")

    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(action__icontains=search)
            | Q(category__icontains=search)
            | Q(user__username__icontains=search)
            | Q(details__icontains=search)
        )

    # Limit to the most recent 500 entries for responsiveness
    qs = qs[:500]

    serializer = AuditLogSerializer(qs, many=True)
    return Response(serializer.data)
