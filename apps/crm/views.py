from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import RoleAllowed
from apps.accounts.throttles import BulkExportRateThrottle
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
from apps.crm.serializers import (
    AccountSerializer,
    ActivitySerializer,
    CampaignSerializer,
    ContactSerializer,
    ContactSerializerNoMRN,
    LeadConvertSerializer,
    LeadSerializer,
    OpportunitySerializer,
    RefillReminderSerializer,
    StageTransitionSerializer,
    TagSerializer,
    TaskSerializer,
    TimelineEntrySerializer,
)
from apps.crm.services import convert_lead, get_timeline

# ---------------------------------------------------------------------------
# Permission shortcuts (reusable instances)
# ---------------------------------------------------------------------------
_SALES_WRITE = RoleAllowed({"SALES": "write"})
_PHARMACIST_READ_SALES_WRITE = RoleAllowed(
    {"SALES": "write", "PHARMACIST": "read"}
)

# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------
class TagViewSet(viewsets.ModelViewSet):
    """Simple CRUD for segment tags."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
class AccountViewSet(viewsets.ModelViewSet):
    """Organisations: hospitals, clinics, wholesalers, pharmacy chains."""

    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        qs = (
            Account.objects.annotate(
                contact_count=Count("contacts"),
                open_opportunities=Count(
                    "opportunities",
                    filter=~Q(
                        opportunities__stage__in=[
                            PipelineStage.WON,
                            PipelineStage.LOST,
                        ]
                    ),
                ),
            )
            .prefetch_related("tags")
            .all()
        )

        account_type = self.request.query_params.get("account_type")
        if account_type:
            qs = qs.filter(account_type=account_type.upper())

        return qs


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------
class ContactViewSet(viewsets.ModelViewSet):
    """People: patients, prescribers, buyers."""

    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated, _PHARMACIST_READ_SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["first_name", "last_name", "email", "mrn"]
    ordering_fields = ["first_name", "last_name", "created_at"]
    ordering = ["last_name", "first_name"]

    def get_serializer_class(self):
        # If user doesn't have MRN access, use a serializer that excludes MRN
        if not self.request.user.mrn_access and self.request.user.role != "ADMIN":
            return ContactSerializerNoMRN
        return ContactSerializer

    def get_queryset(self):
        qs = (
            Contact.objects.select_related("account", "owner")
            .prefetch_related("tags")
            .all()
        )

        contact_type = self.request.query_params.get("contact_type")
        if contact_type:
            qs = qs.filter(contact_type=contact_type.upper())

        account_id = self.request.query_params.get("account")
        if account_id:
            qs = qs.filter(account_id=account_id)

        tag = self.request.query_params.get("tag")
        if tag:
            qs = qs.filter(tags__id=tag)

        return qs

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """360-degree timeline aggregating activities, dispenses,
        opportunities, and notifications for this contact."""
        entries = get_timeline(pk)
        serializer = TimelineEntrySerializer(entries, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------
class LeadViewSet(viewsets.ModelViewSet):
    """Prospective deals before qualification."""

    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "source"]
    ordering_fields = ["name", "est_value", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Lead.objects.select_related("owner").all()

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())

        return qs

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """Convert a qualified lead into an Account, Contact, and Opportunity."""
        lead = self.get_object()
        serializer = LeadConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            opportunity = convert_lead(
                lead_id=lead.id,
                account_name=serializer.validated_data["account_name"],
                contact_first=serializer.validated_data["contact_first"],
                contact_last=serializer.validated_data["contact_last"],
                owner=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

        out = OpportunitySerializer(
            opportunity, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------
class OpportunityViewSet(viewsets.ModelViewSet):
    """Deals moving through the sales pipeline."""

    serializer_class = OpportunitySerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = [
        "name",
        "amount",
        "expected_close_date",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Opportunity.objects.select_related("account", "owner").all()

        stage_param = self.request.query_params.get("stage")
        if stage_param:
            qs = qs.filter(stage=stage_param.upper())

        return qs

    @action(detail=True, methods=["patch"])
    def stage(self, request, pk=None):
        """Transition an opportunity between pipeline stages.

        Requires ``lost_reason`` when moving to **Lost**.
        Automatically sets ``probability`` to 0 (Lost) or 100 (Won).
        """
        opportunity = self.get_object()
        serializer = StageTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_stage = serializer.validated_data["stage"]
        opportunity.stage = new_stage

        if serializer.validated_data.get("lost_reason"):
            opportunity.lost_reason = serializer.validated_data["lost_reason"]

        if new_stage == PipelineStage.WON:
            opportunity.probability = 100
        elif new_stage == PipelineStage.LOST:
            opportunity.probability = 0

        opportunity.save(
            update_fields=["stage", "lost_reason", "probability"]
        )

        out = self.get_serializer(opportunity)
        return Response(out.data)

    @action(detail=False, methods=["get"])
    def pipeline(self, request):
        """Kanban-style view: opportunities grouped by pipeline stage."""
        opportunities = self.get_queryset()
        grouped: dict[str, list[Opportunity]] = defaultdict(list)

        for opp in opportunities:
            grouped[opp.stage].append(opp)

        result = {}
        for stage_value, _stage_label in PipelineStage.choices:
            result[stage_value] = self.get_serializer(
                grouped.get(stage_value, []), many=True
            ).data

        return Response(result)


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------
class ActivityViewSet(viewsets.ModelViewSet):
    """Interaction log: calls, emails, meetings, notes."""

    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = (
            Activity.objects.select_related(
                "created_by", "contact", "account", "opportunity"
            )
            .all()
        )

        for param, field in [
            ("contact", "contact_id"),
            ("account", "account_id"),
            ("opportunity", "opportunity_id"),
            ("activity_type", "activity_type"),
        ]:
            value = self.request.query_params.get(param)
            if value:
                qs = qs.filter(**{field: value})

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
class TaskViewSet(viewsets.ModelViewSet):
    """To-do items linked to contacts or opportunities."""

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["title"]
    ordering_fields = ["due_date", "title"]
    ordering = ["due_date"]

    def get_queryset(self):
        qs = (
            Task.objects.select_related(
                "assignee", "contact", "opportunity"
            )
            .all()
        )

        for param, field in [
            ("status", "status"),
            ("assignee", "assignee_id"),
            ("due_date", "due_date"),
        ]:
            value = self.request.query_params.get(param)
            if value:
                qs = qs.filter(**{field: value})

        return qs


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------
class CampaignViewSet(viewsets.ModelViewSet):
    """Marketing campaigns: refill drives, awareness, promotions."""

    queryset = Campaign.objects.prefetch_related("target_tags").all()
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = [
        "name",
        "scheduled_for",
        "sent_count",
        "created_at",
    ]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        campaign = serializer.save()
        # Only target contacts with consent_marketing=True
        tags = campaign.target_tags.all()
        if tags.exists():
            eligible = Contact.objects.filter(
                tags__in=tags, consent_marketing=True
            ).distinct()
        else:
            eligible = Contact.objects.filter(consent_marketing=True)
        campaign.sent_count = eligible.count()
        campaign.save(update_fields=["sent_count"])

    def get_queryset(self):
        qs = super().get_queryset()

        campaign_type = self.request.query_params.get("campaign_type")
        if campaign_type:
            qs = qs.filter(campaign_type=campaign_type.upper())

        return qs


# ---------------------------------------------------------------------------
# Refill Reminder
# ---------------------------------------------------------------------------
class BulkExportView(generics.GenericAPIView):
    """Bulk export contacts to CSV with rate limiting.

    Requires a CONTACT_BULK_EXPORT approval for large exports.
    """

    permission_classes = [IsAuthenticated, _SALES_WRITE]
    throttle_classes = [BulkExportRateThrottle]

    def post(self, request):
        from apps.approvals.models import ApprovalRequest

        filters = {}
        tag = request.data.get("tag")
        if tag:
            filters["tag"] = tag
        contact_type = request.data.get("contact_type")
        if contact_type:
            filters["contact_type"] = contact_type

        approval = ApprovalRequest.objects.create(
            action_type="CONTACT_BULK_EXPORT",
            payload={"filters": filters, "requested_by": str(request.user.id)},
            requested_by=request.user,
        )

        return Response(
            {
                "message": "Bulk export submitted for approval.",
                "approval_id": str(approval.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class RefillReminderViewSet(viewsets.ModelViewSet):
    """Scheduled medication refill reminders for patients."""

    serializer_class = RefillReminderSerializer
    permission_classes = [IsAuthenticated, _SALES_WRITE]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["next_due_date"]
    ordering = ["next_due_date"]

    def get_queryset(self):
        qs = (
            RefillReminder.objects.select_related("contact", "product")
            .all()
        )

        for param, field in [
            ("contact", "contact_id"),
            ("active", "active"),
        ]:
            value = self.request.query_params.get(param)
            if value:
                qs = qs.filter(**{field: value})

        return qs
