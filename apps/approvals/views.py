from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth import get_user_model

from apps.accounts.permissions import RoleAllowed
from apps.approvals.models import ApprovalRequest
from apps.approvals.serializers import ApprovalRequestSerializer

_ADMIN_ONLY = RoleAllowed({"ADMIN": "write"})


class ApprovalViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """List pending approval requests; approve or reject individual items."""

    permission_classes = [IsAuthenticated, _ADMIN_ONLY]
    serializer_class = ApprovalRequestSerializer

    def get_queryset(self):
        qs = ApprovalRequest.objects.select_related(
            "requested_by", "reviewed_by"
        ).all()

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        else:
            qs = qs.filter(status="PENDING")

        return qs.order_by("-created_at")

    def get_object(self):
        """Override to bypass default PENDING filter in get_queryset."""
        from uuid import UUID
        from django.http import Http404
        from django.shortcuts import get_object_or_404

        qs = ApprovalRequest.objects.select_related("requested_by", "reviewed_by").all()
        try:
            UUID(str(self.kwargs["pk"]))
        except (ValueError, AttributeError):
            # Invalid id in the URL must be 404, not a 500 from a bad lookup.
            raise Http404("Invalid approval id.")
        return get_object_or_404(qs, pk=self.kwargs["pk"])

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        approval = self.get_object()
        if approval.status != "PENDING":
            return Response(
                {"detail": f"Request is already {approval.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            approval.execute()
        except Exception as exc:
            return Response(
                {"detail": f"Execution failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        approval.status = "APPROVED"
        approval.reviewed_by = request.user
        approval.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return Response(
            {"detail": "Request approved and executed.", "status": "APPROVED"}
        )

    @action(detail=False, methods=["post"])
    def request_activation(self, request):
        """POST /api/approvals/request_activation/ — stage a USER_ACTIVATE

        Approval for a pending (inactive) user.  Complements the admin
        Settings > Users PATCH path; exists so the documented
        registration-approval workflow is drivable through the API.
        """
        User = get_user_model()
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"detail": "user_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            target = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if target.is_active:
            return Response(
                {"detail": "User is already active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approval = ApprovalRequest.objects.create(
            action_type="USER_ACTIVATE",
            payload={"user_id": str(target.id)},
            requested_by=request.user,
        )
        return Response(
            {
                "message": "Activation request staged for approval.",
                "approval_id": str(approval.id),
                "user_id": str(target.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        approval = self.get_object()
        if approval.status != "PENDING":
            return Response(
                {"detail": f"Request is already {approval.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Canonical field is `reason`; also accept `notes` so clients that
        # send the wrong key don't silently lose the rejection reason.
        reason = request.data.get("reason") or request.data.get("notes", "")
        approval.status = "REJECTED"
        approval.reason = reason or approval.reason
        approval.reviewed_by = request.user
        approval.save(
            update_fields=["status", "reason", "reviewed_by", "reviewed_at"]
        )

        return Response(
            {"detail": "Request rejected.", "status": "REJECTED"}
        )
