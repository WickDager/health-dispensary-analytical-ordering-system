from django.contrib import admin

from apps.intelligence.models import (
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


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ("model_type", "version", "is_active", "accuracy_score", "last_trained_at")
    list_filter = ("model_type", "is_active")
    search_fields = ("model_type", "version")
    readonly_fields = ("id", "created_at")


@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "model_version", "subject_type", "subject_id", "confidence", "created_at")
    list_filter = ("subject_type", "model_version__model_type")
    search_fields = ("subject_id",)
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"


@admin.register(OutcomeLog)
class OutcomeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "prediction", "subject_type", "subject_id", "recorded_at")
    list_filter = ("subject_type",)
    search_fields = ("subject_id",)
    readonly_fields = ("id", "recorded_at")
    date_hierarchy = "recorded_at"


@admin.register(DemandForecast)
class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ("product", "forecast_date", "predicted_quantity", "confidence_low", "confidence_high", "method")
    list_filter = ("method", "forecast_date")
    search_fields = ("product__name",)
    readonly_fields = ("id", "created_at")
    date_hierarchy = "forecast_date"


@admin.register(SupplierScore)
class SupplierScoreAdmin(admin.ModelAdmin):
    list_display = ("supplier", "overall_score", "cost_score", "reliability_score", "quality_score", "speed_score", "trend")
    list_filter = ("trend",)
    search_fields = ("supplier__name",)
    readonly_fields = ("id", "calculated_at")


@admin.register(ExpiryRiskAssessment)
class ExpiryRiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ("lot", "risk_score", "risk_level", "days_of_stock_remaining", "assessed_at")
    list_filter = ("risk_level",)
    search_fields = ("lot__lot_number",)
    readonly_fields = ("id", "assessed_at")


@admin.register(PatientAdherenceScore)
class PatientAdherenceScoreAdmin(admin.ModelAdmin):
    list_display = ("contact", "product", "adherence_score", "days_overdue_risk", "pattern")
    list_filter = ("pattern",)
    search_fields = ("contact__first_name", "contact__last_name", "product__name")
    readonly_fields = ("id", "calculated_at")


@admin.register(AnomalyAlert)
class AnomalyAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "anomaly_type", "severity", "resolved", "created_at")
    list_filter = ("anomaly_type", "severity", "resolved")
    search_fields = ("title", "description", "subject_id")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("template_type", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("template_type", "prompt_template")
    readonly_fields = ("id", "created_at")
