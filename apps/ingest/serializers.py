from rest_framework import serializers

from apps.audit.models import AIIngestAudit


class InvoiceUploadSerializer(serializers.Serializer):
    """Serializer for the document upload endpoint (invoice, receipt, etc.)."""

    text = serializers.CharField(min_length=1, max_length=100_000, required=False)
    file = serializers.FileField(required=False)
    doc_type = serializers.ChoiceField(
        choices=[
            "supplier_invoice",
            "supplier_receipt",
            "client_receipt",
        ],
        default="supplier_invoice",
        required=False,
    )


class IngestStatusSerializer(serializers.ModelSerializer):
    """Expose AIIngestAudit fields for status polling."""

    extracted_data = serializers.JSONField(source="validated_output", read_only=True)
    error_message = serializers.SerializerMethodField()

    class Meta:
        model = AIIngestAudit
        fields = (
            "id",
            "provider",
            "model",
            "latency_ms",
            "succeeded",
            "extracted_data",
            "error_message",
            "created_at",
        )
        read_only_fields = fields

    def get_error_message(self, obj) -> str | None:
        if obj.succeeded:
            return None
        if isinstance(obj.raw_output, dict):
            return obj.raw_output.get("error") or obj.raw_output.get("errors")
        return None


class CommitIngestionSerializer(serializers.Serializer):
    """Serializer for the commit endpoint."""
    audit_id = serializers.UUIDField()
