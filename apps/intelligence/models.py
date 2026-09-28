"""AI/ML intelligence models for HDAOS v3.0.

Stores model metadata, predictions, ground-truth outcomes, and
the derived artifacts (forecasts, scores, risk assessments) that
power the statistical prediction engine.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Document templates (LLM-driven ingestion)
# ---------------------------------------------------------------------------


class DocumentTemplate(models.Model):
    """LLM prompt template for structured document extraction."""

    TEMPLATE_TYPES = [
        ("invoice", "Supplier Invoice"),
        ("receipt", "Customer Receipt"),
        ("prescription", "Prescription"),
        ("delivery_note", "Delivery Note"),
        ("return_form", "Return/Refund Form"),
        ("purchase_order", "Purchase Order"),
        ("generic", "Generic Document"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_type = models.CharField(
        max_length=20, choices=TEMPLATE_TYPES, unique=True
    )
    prompt_template = models.TextField()
    extraction_schema = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.get_template_type_display()} template"


# ---------------------------------------------------------------------------
# Foundation -- model tracking & feedback loop
# ---------------------------------------------------------------------------


class ModelVersion(models.Model):
    """Immutable registry of every prediction model version ever deployed."""

    MODEL_TYPES = [
        ("demand_forecast", "Demand Forecasting"),
        ("supplier_scoring", "Supplier Scoring"),
        ("expiry_risk", "Expiry Risk Prediction"),
        ("reorder_point", "Dynamic Reorder Point"),
        ("adherence", "Patient Adherence Prediction"),
        ("anomaly", "Anomaly Detection"),
        ("pricing", "Pricing Optimization"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_type = models.CharField(max_length=32, choices=MODEL_TYPES)
    version = models.CharField(max_length=16)
    is_active = models.BooleanField(default=True)
    accuracy_score = models.FloatField(null=True, blank=True)
    last_trained_at = models.DateTimeField(null=True, blank=True)
    parameters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("model_type", "version")]
        indexes = [
            models.Index(fields=["model_type", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.model_type}@{self.version}" + (
            " (active)" if self.is_active else ""
        )


class PredictionLog(models.Model):
    """Every prediction emitted by the engine, for audit & feedback."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.PROTECT,
        related_name="predictions",
    )
    subject_type = models.CharField(max_length=32)
    subject_id = models.CharField(max_length=36)
    prediction = models.JSONField()
    confidence = models.FloatField(default=0.0)
    input_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_version", "created_at"]),
            models.Index(fields=["subject_type", "subject_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.model_version} -> {self.subject_type}:{self.subject_id}"


class OutcomeLog(models.Model):
    """Ground-truth outcome that can be compared against a prediction.

    Populated by nightly feedback loops -- e.g. actual consumption vs.
    forecast, actual delivery date vs. promised.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prediction = models.ForeignKey(
        PredictionLog,
        on_delete=models.CASCADE,
        related_name="outcomes",
        null=True, blank=True,
    )
    subject_type = models.CharField(max_length=32)
    subject_id = models.CharField(max_length=36)
    outcome = models.JSONField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["subject_type", "subject_id"]),
            models.Index(fields=["recorded_at"]),
        ]

    def __str__(self) -> str:
        return f"Outcome for {self.subject_type}:{self.subject_id}"


# ---------------------------------------------------------------------------
# Artifacts -- cached results from nightly runs
# ---------------------------------------------------------------------------


class DemandForecast(models.Model):
    """Per-product demand forecast, regenerated nightly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="forecasts",
    )
    model_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        related_name="demand_forecasts",
    )
    forecast_date = models.DateField()
    predicted_quantity = models.IntegerField()
    confidence_low = models.IntegerField()
    confidence_high = models.IntegerField()
    method = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("product", "forecast_date")]
        indexes = [
            models.Index(fields=["product", "forecast_date"]),
            models.Index(fields=["forecast_date"]),
        ]

    def __str__(self) -> str:
        return (
            f"Forecast {self.product.name} @ {self.forecast_date}: "
            f"{self.predicted_quantity} [{self.confidence_low}-{self.confidence_high}]"
        )


class SupplierScore(models.Model):
    """Per-supplier composite score, regenerated nightly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        "catalog.Supplier",
        on_delete=models.CASCADE,
        related_name="scores",
    )
    overall_score = models.FloatField(default=0.0)
    cost_score = models.FloatField(default=0.0)
    reliability_score = models.FloatField(default=0.0)
    quality_score = models.FloatField(default=0.0)
    speed_score = models.FloatField(default=0.0)
    trend = models.CharField(max_length=8, default="stable")
    analysis_json = models.JSONField(default=dict)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["supplier", "calculated_at"]),
        ]

    def __str__(self) -> str:
        return f"Score {self.supplier.name}: {self.overall_score:.0f}/100"


class ExpiryRiskAssessment(models.Model):
    """Per-lot expiry risk, regenerated nightly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot = models.ForeignKey(
        "lots.Lot",
        on_delete=models.CASCADE,
        related_name="risk_assessments",
    )
    risk_score = models.FloatField(default=0.0)
    risk_level = models.CharField(max_length=12, default="low")
    estimated_exhaustion_date = models.DateField(null=True)
    days_of_stock_remaining = models.IntegerField(null=True)
    daily_consumption_rate = models.FloatField(default=0.0)
    assessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["lot", "assessed_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"ExpiryRisk {self.lot.batch_number}: "
            f"{self.risk_level} ({self.risk_score:.0f}/100)"
        )


class PatientAdherenceScore(models.Model):
    """Per-patient-per-product adherence score, regenerated nightly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(
        "crm.Contact",
        on_delete=models.CASCADE,
        related_name="adherence_scores",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
    )
    adherence_score = models.FloatField(default=0.0)
    days_overdue_risk = models.IntegerField(default=0)
    pattern = models.CharField(max_length=16, default="regular")
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["contact", "product"]),
        ]

    def __str__(self) -> str:
        return (
            f"Adherence {self.contact}: {self.pattern} "
            f"({self.adherence_score:.0f}/100)"
        )


class AnomalyAlert(models.Model):
    """Detected statistical anomalies across any dimension."""

    ANOMALY_TYPES = [
        ("unusual_order", "Unusual Order Quantity"),
        ("unusual_dispense", "Unusual Dispense Pattern"),
        ("stock_discrepancy", "Stock Level Discrepancy"),
        ("price_spike", "Supplier Price Spike"),
        ("unusual_velocity", "Unusual Consumption Velocity"),
    ]
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    anomaly_type = models.CharField(
        max_length=24, choices=ANOMALY_TYPES
    )
    severity = models.CharField(
        max_length=8, choices=SEVERITY_CHOICES, default="medium"
    )
    subject_type = models.CharField(max_length=32)
    subject_id = models.CharField(max_length=36)
    title = models.CharField(max_length=255)
    description = models.TextField()
    data_snapshot = models.JSONField(default=dict)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["anomaly_type", "resolved"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"[{self.severity}] {self.anomaly_type} for "
            f"{self.subject_type}:{self.subject_id}"
        )


# ---------------------------------------------------------------------------
# AI Module Configuration (settings/ai endpoint)
# ---------------------------------------------------------------------------
class AIModuleConfig(models.Model):
    """Per-module toggle and confidence threshold for AI intelligence features."""

    key = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=True)
    confidence_threshold = models.FloatField(default=0.7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.label} ({'enabled' if self.enabled else 'disabled'})"
