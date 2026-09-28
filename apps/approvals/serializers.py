from rest_framework import serializers
from apps.approvals.models import ApprovalRequest


class ApprovalRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.username", read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = (
            "id", "action_type", "payload", "status",
            "requested_by", "requested_by_name",
            "reviewed_by", "reviewed_by_name",
            "reason", "created_at", "reviewed_at",
        )
        read_only_fields = ("id", "status", "reviewed_by", "reviewed_at", "created_at")


class ApprovalActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
