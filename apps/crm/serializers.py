from __future__ import annotations

from rest_framework import serializers

from apps.crm.models import (
    Account,
    Activity,
    Campaign,
    Contact,
    Lead,
    Opportunity,
    PipelineStage,
    RefillReminder,
    Tag,
    Task,
)


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "color")
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
class AccountSerializer(serializers.ModelSerializer):
    contact_count = serializers.IntegerField(read_only=True)
    open_opportunities = serializers.IntegerField(read_only=True)
    owner_name = serializers.CharField(
        source="owner.username", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = Account
        fields = (
            "id",
            "name",
            "account_type",
            "billing_address",
            "owner",
            "owner_name",
            "tags",
            "contact_count",
            "open_opportunities",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["tags"] = TagSerializer(instance.tags.all(), many=True).data
        return data


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------
class ContactSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(
        source="account.name", read_only=True, default=None, allow_null=True
    )
    owner_name = serializers.CharField(
        source="owner.username", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = Contact
        fields = (
            "id",
            "contact_type",
            "first_name",
            "last_name",
            "email",
            "phone",
            "mrn",
            "account",
            "account_name",
            "owner",
            "owner_name",
            "tags",
            "consent_marketing",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["tags"] = TagSerializer(instance.tags.all(), many=True).data
        return data


class ContactSerializerNoMRN(ContactSerializer):
    """Contact serializer that excludes MRN for users without MRN access."""

    class Meta(ContactSerializer.Meta):
        pass

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("mrn", None)
        return data


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------
class LeadSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(
        source="owner.username", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = Lead
        fields = (
            "id",
            "name",
            "source",
            "status",
            "est_value",
            "owner",
            "owner_name",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


# ---------------------------------------------------------------------------
# Lead convert (write-only input)
# ---------------------------------------------------------------------------
class LeadConvertSerializer(serializers.Serializer):
    account_name = serializers.CharField(max_length=255)
    contact_first = serializers.CharField(max_length=128)
    contact_last = serializers.CharField(max_length=128)


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------
class OpportunitySerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(
        source="account.name", read_only=True
    )
    owner_name = serializers.CharField(
        source="owner.username", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "name",
            "account",
            "account_name",
            "stage",
            "amount",
            "probability",
            "expected_close_date",
            "lost_reason",
            "owner",
            "owner_name",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


# ---------------------------------------------------------------------------
# Stage transition (write-only input)
# ---------------------------------------------------------------------------
class StageTransitionSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=PipelineStage.choices)
    lost_reason = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )

    def validate(self, data):
        if data["stage"] == PipelineStage.LOST and not data.get("lost_reason"):
            raise serializers.ValidationError(
                {"lost_reason": "Lost reason is required when moving an opportunity to Lost."}
            )
        return data


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------
class ActivitySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = Activity
        fields = (
            "id",
            "activity_type",
            "subject",
            "body",
            "contact",
            "account",
            "opportunity",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(
        source="assignee.username", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "due_date",
            "reminder_sent",
            "status",
            "assignee",
            "assignee_name",
            "contact",
            "opportunity",
        )
        read_only_fields = ("id", "reminder_sent")


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------
class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = (
            "id",
            "name",
            "campaign_type",
            "target_tags",
            "scheduled_for",
            "sent_count",
            "created_at",
        )
        read_only_fields = ("id", "sent_count", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["target_tags"] = TagSerializer(
            instance.target_tags.all(), many=True
        ).data
        return data


# ---------------------------------------------------------------------------
# Refill Reminder
# ---------------------------------------------------------------------------
class RefillReminderSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = RefillReminder
        fields = (
            "id",
            "contact",
            "contact_name",
            "product",
            "product_name",
            "interval_days",
            "next_due_date",
            "active",
        )
        read_only_fields = ("id",)

    def get_contact_name(self, obj) -> str:
        c = obj.contact
        return f"{c.first_name} {c.last_name}"


# ---------------------------------------------------------------------------
# Timeline entry (read-only, for 360deg view)
# ---------------------------------------------------------------------------
class TimelineEntrySerializer(serializers.Serializer):
    type = serializers.CharField()
    date = serializers.DateTimeField()
    title = serializers.CharField()
    detail = serializers.CharField(allow_blank=True)
    link = serializers.CharField(allow_blank=True)
