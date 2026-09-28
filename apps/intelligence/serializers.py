"""REST serializers for the intelligence (AI/ML) module."""

from __future__ import annotations

from rest_framework import serializers

from apps.intelligence.models import (
    AIModuleConfig,
    AnomalyAlert,
    DemandForecast,
    DocumentTemplate,
    ExpiryRiskAssessment,
    ModelVersion,
    OutcomeLog,
    PatientAdherenceScore,
    PredictionLog,
    SupplierScore,
)


# ---------------------------------------------------------------------------
# ModelVersion
# ---------------------------------------------------------------------------

class ModelVersionSerializer(serializers.ModelSerializer):
    model_type_display = serializers.CharField(
        source="get_model_type_display", read_only=True
    )
    prediction_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = ModelVersion
        fields = (
            "id",
            "model_type",
            "model_type_display",
            "version",
            "is_active",
            "accuracy_score",
            "last_trained_at",
            "parameters",
            "created_at",
            "prediction_count",
        )
        read_only_fields = ("id", "created_at", "prediction_count")


# ---------------------------------------------------------------------------
# PredictionLog
# ---------------------------------------------------------------------------

class PredictionLogSerializer(serializers.ModelSerializer):
    model_version_label = serializers.SerializerMethodField()

    class Meta:
        model = PredictionLog
        fields = (
            "id",
            "model_version",
            "model_version_label",
            "subject_type",
            "subject_id",
            "prediction",
            "confidence",
            "input_snapshot",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def get_model_version_label(self, obj: PredictionLog) -> str:
        return str(obj.model_version)


# ---------------------------------------------------------------------------
# OutcomeLog
# ---------------------------------------------------------------------------

class OutcomeLogSerializer(serializers.ModelSerializer):
    prediction_subject_type = serializers.CharField(
        source="prediction.subject_type", read_only=True, default=None
    )
    prediction_subject_id = serializers.CharField(
        source="prediction.subject_id", read_only=True, default=None
    )

    class Meta:
        model = OutcomeLog
        fields = (
            "id",
            "prediction",
            "prediction_subject_type",
            "prediction_subject_id",
            "subject_type",
            "subject_id",
            "outcome",
            "recorded_at",
        )
        read_only_fields = ("id", "recorded_at")


# ---------------------------------------------------------------------------
# DemandForecast
# ---------------------------------------------------------------------------

class DemandForecastSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name", read_only=True
    )
    product_sku = serializers.CharField(
        source="product.sku", read_only=True, default=""
    )
    model_version_label = serializers.SerializerMethodField()

    class Meta:
        model = DemandForecast
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "model_version",
            "model_version_label",
            "forecast_date",
            "predicted_quantity",
            "confidence_low",
            "confidence_high",
            "method",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def get_model_version_label(self, obj: DemandForecast) -> str:
        if obj.model_version:
            return str(obj.model_version)
        return ""


# ---------------------------------------------------------------------------
# SupplierScore
# ---------------------------------------------------------------------------

class SupplierScoreSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source="supplier.name", read_only=True
    )

    class Meta:
        model = SupplierScore
        fields = (
            "id",
            "supplier",
            "supplier_name",
            "overall_score",
            "cost_score",
            "reliability_score",
            "quality_score",
            "speed_score",
            "trend",
            "analysis_json",
            "calculated_at",
        )
        read_only_fields = ("id", "calculated_at")


# ---------------------------------------------------------------------------
# ExpiryRiskAssessment
# ---------------------------------------------------------------------------

class ExpiryRiskAssessmentSerializer(serializers.ModelSerializer):
    lot_batch_number = serializers.CharField(
        source="lot.batch_number", read_only=True
    )
    lot_product_name = serializers.SerializerMethodField()

    class Meta:
        model = ExpiryRiskAssessment
        fields = (
            "id",
            "lot",
            "lot_batch_number",
            "lot_product_name",
            "risk_level",
            "risk_score",
            "estimated_exhaustion_date",
            "days_of_stock_remaining",
            "daily_consumption_rate",
            "assessed_at",
        )
        read_only_fields = ("id", "assessed_at")

    def get_lot_product_name(self, obj: ExpiryRiskAssessment) -> str:
        try:
            return obj.lot.product.name
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# AnomalyAlert
# ---------------------------------------------------------------------------

class AnomalyAlertSerializer(serializers.ModelSerializer):
    anomaly_type_display = serializers.CharField(
        source="get_anomaly_type_display", read_only=True
    )
    resolved_by_name = serializers.CharField(
        source="resolved_by.username", read_only=True, default=None
    )

    class Meta:
        model = AnomalyAlert
        fields = (
            "id",
            "anomaly_type",
            "anomaly_type_display",
            "severity",
            "subject_type",
            "subject_id",
            "title",
            "description",
            "data_snapshot",
            "resolved",
            "created_at",
            "resolved_by",
            "resolved_by_name",
        )
        read_only_fields = ("id", "created_at")


class AnomalyAlertResolveSerializer(serializers.Serializer):
    """Lightweight serializer for the resolve action."""

    resolution_note = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


# ---------------------------------------------------------------------------
# PatientAdherenceScore
# ---------------------------------------------------------------------------

class PatientAdherenceScoreSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(
        source="product.name", read_only=True
    )

    class Meta:
        model = PatientAdherenceScore
        fields = (
            "id",
            "contact",
            "contact_name",
            "product",
            "product_name",
            "adherence_score",
            "days_overdue_risk",
            "pattern",
            "calculated_at",
        )
        read_only_fields = ("id", "calculated_at")

    def get_contact_name(self, obj: PatientAdherenceScore) -> str:
        try:
            return f"{obj.contact.first_name} {obj.contact.last_name}".strip() or str(
                obj.contact
            )
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# DocumentTemplate
# ---------------------------------------------------------------------------

class DocumentTemplateSerializer(serializers.ModelSerializer):
    template_type_display = serializers.CharField(
        source="get_template_type_display", read_only=True
    )

    class Meta:
        model = DocumentTemplate
        fields = (
            "id",
            "template_type",
            "template_type_display",
            "prompt_template",
            "extraction_schema",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


# ---------------------------------------------------------------------------
# ModelPerformance (read-only, aggregated)
# ---------------------------------------------------------------------------

class ModelPerformanceSerializer(serializers.Serializer):
    """Aggregated performance metrics per model type."""

    model_type = serializers.CharField()
    model_type_display = serializers.CharField()
    version = serializers.CharField()
    is_active = serializers.BooleanField()
    accuracy = serializers.FloatField(allow_null=True)
    total_predictions = serializers.IntegerField()
    needs_retraining = serializers.BooleanField()
    last_trained = serializers.DateTimeField(allow_null=True)


# ---------------------------------------------------------------------------
# Pipeline + Insight request serializers
# ---------------------------------------------------------------------------

class PipelineRunSerializer(serializers.Serializer):
    """Response from the full pipeline run."""

    started_at = serializers.CharField()
    finished_at = serializers.CharField(required=False)
    demand = serializers.DictField()
    suppliers = serializers.DictField()
    expiry = serializers.DictField()
    adherence = serializers.DictField()
    anomalies = serializers.DictField()
    outcomes = serializers.IntegerField()
    evaluation = serializers.ListField(child=serializers.DictField())


class InsightRequestSerializer(serializers.Serializer):
    """Request body for LLM-powered insights."""

    insight_type = serializers.ChoiceField(
        choices=[
            ("procurement_recommendation", "Procurement Recommendation"),
            ("dashboard_summary", "Dashboard Summary"),
            ("anomaly_explanation", "Anomaly Explanation"),
        ]
    )
    anomaly_id = serializers.UUIDField(required=False, default=None)
    supplier_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )


# ---------------------------------------------------------------------------
# AI Module Configuration (settings/ai endpoint)
# ---------------------------------------------------------------------------
class AIModuleConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModuleConfig
        fields = ("key", "label", "description", "enabled", "confidence_threshold")


class AIConfigSerializer(serializers.Serializer):
    modules = AIModuleConfigSerializer(many=True)
    retraining_schedule = serializers.ChoiceField(
        choices=[("daily", "Daily"), ("weekly", "Weekly"), ("manual", "Manual Only")],
        default="weekly",
    )
