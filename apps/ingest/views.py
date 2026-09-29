from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.throttles import IngestRateThrottle
from apps.ingest.serializers import (
    InvoiceUploadSerializer,
    IngestStatusSerializer,
    CommitIngestionSerializer,
)
from apps.ingest.tasks import process_invoice
from apps.ingest.services import commit_ingestion
from apps.audit.models import AIIngestAudit
from apps.approvals.models import ApprovalRequest


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([IngestRateThrottle])
def upload_invoice(request):
    """
    POST /api/ingest/ — upload invoice text, enqueue the Celery task,
    and return a task_id for polling.
    """
    serializer = InvoiceUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Accept either direct `text` or a `file` upload
    text = serializer.validated_data.get("text") or ""
    uploaded_file = serializer.validated_data.get("file")
    is_image = False
    if uploaded_file:
        raw_bytes = uploaded_file.read()
        # Detect image files by magic bytes
        if raw_bytes[:8] == b"\x89PNG\r\n\x1a\n" or raw_bytes[:2] in (b"\xff\xd8", b"\xff\xd9"):
            is_image = True
            text = raw_bytes.decode("latin-1")  # raw byte passthrough (latin-1 maps 0-255 to unicode codepoints)
        else:
            text = raw_bytes.decode("utf-8", errors="replace")

    if not text:
        return Response(
            {"error": "Either 'text' or 'file' field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    doc_type = serializer.validated_data.get("doc_type", "supplier_invoice")

    # Enqueue the Celery task — fall back to running synchronously if
    # the broker (Redis) is not available.
    try:
        task = process_invoice.delay(
            text=text,
            doc_type=doc_type,
            is_image=is_image,
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        return Response(
            {
                "task_id": task.id,
                "doc_type": doc_type,
                "status": "queued",
                "message": "Document is being processed. Poll GET /api/ingest/status/?task_id=<id>.",
            },
            status=status.HTTP_202_ACCEPTED,
        )
    except Exception:
        # Broker unavailable — run synchronously so the request doesn't drop.
        # The task returns its (synthetic) task_id so clients can still poll.
        result = process_invoice(
            text=text,
            doc_type=doc_type,
            is_image=is_image,
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        return Response(
            {
                "task_id": result.get("task_id"),
                "doc_type": doc_type,
                "status": "completed" if result.get("succeeded") else "failed",
                "message": "Document processed synchronously (broker unavailable).",
            },
            status=status.HTTP_200_OK,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ingest_status(request, task_id: str | None = None):
    """
    GET /api/ingest/status/?task_id=<uuid>  or  /api/ingest/<uuid>/status/

    Poll the task result.  When a task_id is supplied, return the audit row
    for that specific upload (falling back to the user's latest audit for
    rows created before task_id tracking existed); otherwise return the
    latest AIIngestAudit for the requesting user.
    """
    audits = (
        AIIngestAudit.objects
        .filter(created_by=request.user)
        .order_by("-created_at", "-id")  # -id: deterministic tiebreak when created_at is identical
    )
    if task_id:
        latest = audits.filter(task_id=task_id).first() or audits.first()
    else:
        latest = audits.first()
    if latest is None:
        return Response({"status": "not_found", "message": "No ingest records found."})

    serializer = IngestStatusSerializer(latest)
    status_text = "completed" if latest.succeeded else "failed"
    return Response({"status": status_text, "data": serializer.data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def commit_ingest(request):
    """
    POST /api/ingest/commit/ — stage an AI_COMMIT approval request.

    The actual commit is executed by the approval handler after admin review.
    """
    serializer = CommitIngestionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    audit_id = str(serializer.validated_data["audit_id"])

    try:
        audit = AIIngestAudit.objects.get(pk=audit_id, succeeded=True)
    except AIIngestAudit.DoesNotExist:
        return Response(
            {"error": "Audit record not found or ingestion was not successful."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not audit.validated_output:
        return Response(
            {"error": "Audit record has no validated output to commit."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    approval = ApprovalRequest.objects.create(
        action_type="AI_COMMIT",
        payload={"audit_id": audit_id, "validated_data": audit.validated_output},
        requested_by=request.user,
    )

    return Response(
        {
            "message": "Ingestion commit submitted for approval.",
            "approval_id": str(approval.id),
            "audit_id": audit_id,
        },
        status=status.HTTP_202_ACCEPTED,
    )
