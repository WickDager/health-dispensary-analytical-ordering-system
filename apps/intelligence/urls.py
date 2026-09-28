"""URL configuration for the intelligence (AI/ML) API."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.intelligence.views import (
    AnomalyAlertViewSet,
    DemandForecastViewSet,
    DocumentTemplateViewSet,
    ExpiryRiskAssessmentViewSet,
    IntelligenceDashboardViewSet,
    ModelVersionViewSet,
    PatientAdherenceScoreViewSet,
    SupplierScoreViewSet,
)

app_name = "intelligence"

router = DefaultRouter()

# Read-only endpoints
router.register(r"models", ModelVersionViewSet, basename="intelligence-model")
router.register(r"forecasts", DemandForecastViewSet, basename="intelligence-forecast")
router.register(r"scores", SupplierScoreViewSet, basename="intelligence-score")
router.register(
    r"expiry-risks", ExpiryRiskAssessmentViewSet, basename="intelligence-expiry-risk"
)
router.register(r"anomalies", AnomalyAlertViewSet, basename="intelligence-anomaly")
router.register(
    r"adherence", PatientAdherenceScoreViewSet, basename="intelligence-adherence"
)

# Admin write endpoints
router.register(
    r"templates", DocumentTemplateViewSet, basename="intelligence-template"
)

# Dashboard aggregations + pipeline trigger
router.register(
    r"dashboard",
    IntelligenceDashboardViewSet,
    basename="intelligence-dashboard",
)

urlpatterns = router.urls
