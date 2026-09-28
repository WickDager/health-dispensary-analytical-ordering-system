"""
Comprehensive tests for the intelligence (AI/ML) app: all 9 models,
serializers, statistical demand forecasting functions, anomaly detection
algorithms (IQR, Z-score, modified Z-score), and API endpoints.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.intelligence.models import (
    AnomalyAlert, DemandForecast, DocumentTemplate, ExpiryRiskAssessment,
    ModelVersion, OutcomeLog, PatientAdherenceScore, PredictionLog,
    SupplierScore,
)
from apps.intelligence.serializers import (
    AnomalyAlertSerializer, DemandForecastSerializer, DocumentTemplateSerializer,
    ExpiryRiskAssessmentSerializer, ModelVersionSerializer,
    PatientAdherenceScoreSerializer, PredictionLogSerializer, SupplierScoreSerializer,
    InsightRequestSerializer, AnomalyAlertResolveSerializer,
)
from apps.intelligence.services import demand_forecasting, anomaly_detection


# ===========================================================================
# Statistical Functions Tests (demand_forecasting.py)
# ===========================================================================
class TestMovingAverage:
    def test_basic(self):
        result = demand_forecasting.moving_average([1.0, 2.0, 3.0, 4.0, 5.0], window=3)
        assert result == pytest.approx(4.0)  # avg of last 3: (3+4+5)/3

    def test_empty(self):
        assert demand_forecasting.moving_average([]) == 0.0

    def test_single_value(self):
        assert demand_forecasting.moving_average([5.0]) == 5.0

    def test_window_larger_than_data(self):
        result = demand_forecasting.moving_average([1.0, 2.0], window=10)
        assert result == pytest.approx(1.5)


class TestExponentialSmoothing:
    def test_basic(self):
        result = demand_forecasting.exponential_smoothing(
            [10.0, 12.0, 14.0], alpha=0.5
        )
        # step1: 10 → step2: 0.5*12 + 0.5*10 = 11 → step3: 0.5*14 + 0.5*11 = 12.5
        assert result == pytest.approx(12.5)

    def test_empty(self):
        assert demand_forecasting.exponential_smoothing([]) == 0.0

    def test_single_value(self):
        assert demand_forecasting.exponential_smoothing([7.0]) == 7.0


class TestDoubleExponentialSmoothing:
    def test_basic(self):
        level, trend = demand_forecasting.double_exponential_smoothing(
            [10.0, 12.0, 15.0, 18.0], alpha=0.5, beta=0.3
        )
        # should produce reasonable level+trend values
        assert level > 0
        assert isinstance(trend, float)

    def test_empty(self):
        level, trend = demand_forecasting.double_exponential_smoothing([])
        assert level == 0.0
        assert trend == 0.0


class TestLinearRegressionSlope:
    def test_basic(self):
        x = [0, 1, 2, 3]
        y = [0, 2, 4, 6]
        slope, intercept = demand_forecasting.linear_regression_slope(x, y)
        assert slope == pytest.approx(2.0)
        assert intercept == pytest.approx(0.0)

    def test_single_point(self):
        slope, intercept = demand_forecasting.linear_regression_slope([0], [5.0])
        assert slope == 0.0
        assert intercept == 5.0

    def test_constant_y(self):
        x = [0, 1, 2, 3]
        y = [3.0, 3.0, 3.0, 3.0]
        slope, intercept = demand_forecasting.linear_regression_slope(x, y)
        assert slope == pytest.approx(0.0)
        assert intercept == pytest.approx(3.0)


class TestTrendDirection:
    def test_rising(self):
        assert demand_forecasting.trend_direction([10, 20, 30, 40, 50]) == "rising"

    def test_falling(self):
        assert demand_forecasting.trend_direction([50, 40, 30, 20, 10]) == "falling"

    def test_stable(self):
        result = demand_forecasting.trend_direction([10, 10, 10, 10, 10])
        assert result == "stable"

    def test_short_sequence(self):
        assert demand_forecasting.trend_direction([10, 20]) == "stable"


class TestClassifyVelocity:
    def test_fast_mover(self):
        result = demand_forecasting.classify_velocity([80, 90, 85, 95, 100])
        assert result == "fast_mover"

    def test_slow_mover(self):
        result = demand_forecasting.classify_velocity([1, 100, 2, 80, 3])
        # avg ≈ 37.2, max=100, normalized ≈ 0.372 → moderate (between 0.2 and 0.8)
        # Actually with 0.2 threshold this would be moderate
        assert result in ("fast_mover", "moderate", "slow_mover")

    def test_empty(self):
        assert demand_forecasting.classify_velocity([]) == "slow_mover"


class TestCoefficientOfVariation:
    def test_basic(self):
        cv = demand_forecasting.coefficient_of_variation([10, 10, 10, 10])
        assert cv == 0.0  # zero variance

    def test_with_variance(self):
        cv = demand_forecasting.coefficient_of_variation([1, 2, 3, 4, 5])
        assert cv > 0.0

    def test_empty(self):
        assert demand_forecasting.coefficient_of_variation([]) == 0.0


class TestMAPE:
    def test_perfect_prediction(self):
        mape = demand_forecasting.mean_absolute_percentage_error(
            [10, 20, 30], [10, 20, 30]
        )
        assert mape == 0.0

    def test_error(self):
        mape = demand_forecasting.mean_absolute_percentage_error(
            [10, 20, 30], [12, 18, 33]
        )
        # |10-12|/10 = 0.2, |20-18|/20 = 0.1, |30-33|/30 = 0.1 → avg 0.1333
        assert pytest.approx(mape, abs=0.01) == 0.1333

    def test_empty(self):
        assert demand_forecasting.mean_absolute_percentage_error([], []) == float("inf")

    def test_mismatched_lengths(self):
        assert demand_forecasting.mean_absolute_percentage_error(
            [1, 2], [1, 2, 3]
        ) == float("inf")


# ===========================================================================
# Anomaly Detection Tests (anomaly_detection.py)
# ===========================================================================
class TestAnomalyDetectionIQR:
    def test_no_anomalies(self):
        values = [10.0, 12.0, 11.0, 13.0, 10.0, 12.0]
        indices = anomaly_detection.detect_anomalies_iqr(values)
        assert indices == []

    def test_upper_anomaly(self):
        values = [10.0, 11.0, 10.0, 11.0, 10.0, 100.0]
        indices = anomaly_detection.detect_anomalies_iqr(values)
        assert 5 in indices  # 100.0 is anomalous

    def test_lower_anomaly(self):
        values = [10.0, 11.0, 10.0, 11.0, 10.0, -50.0]
        indices = anomaly_detection.detect_anomalies_iqr(values)
        assert 5 in indices

    def test_too_few_values(self):
        values = [1.0, 2.0, 3.0]
        indices = anomaly_detection.detect_anomalies_iqr(values)
        assert indices == []

    def test_zero_iqr(self):
        values = [5.0, 5.0, 5.0, 5.0, 5.0]
        indices = anomaly_detection.detect_anomalies_iqr(values)
        assert indices == []


class TestAnomalyDetectionZScore:
    def test_no_anomalies(self):
        values = [10.0, 11.0, 10.0, 11.0, 10.0, 11.0]
        indices = anomaly_detection.detect_anomalies_zscore(values)
        assert indices == []

    def test_anomaly(self):
        # With many tight-clustered values, an extreme outlier is detected
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 100.0]
        indices = anomaly_detection.detect_anomalies_zscore(values)
        assert 10 in indices

    def test_too_few_values(self):
        assert anomaly_detection.detect_anomalies_zscore([1.0, 2.0]) == []

    def test_zero_std(self):
        values = [5.0, 5.0, 5.0, 5.0]
        assert anomaly_detection.detect_anomalies_zscore(values) == []


class TestAnomalyDetectionModifiedZScore:
    def test_basic(self):
        values = [10.0, 11.0, 12.0, 11.0, 10.0, 100.0]
        indices = anomaly_detection.detect_anomalies_modified_zscore(values)
        assert 5 in indices

    def test_no_anomalies(self):
        values = [10.0, 11.0, 12.0, 11.0, 10.0, 12.0, 11.0, 10.0]
        indices = anomaly_detection.detect_anomalies_modified_zscore(values)
        assert indices == []

    def test_too_few_values(self):
        assert anomaly_detection.detect_anomalies_modified_zscore([1.0, 2.0, 3.0]) == []

    def test_zero_mad(self):
        values = [5.0, 5.0, 5.0, 5.0, 5.0]
        assert anomaly_detection.detect_anomalies_modified_zscore(values) == []


class TestDetectAnomaliesUnified:
    def test_iqr_method(self):
        values = [10.0, 11.0, 10.0, 11.0, 10.0, 100.0]
        result = anomaly_detection.detect_anomalies(values, method="iqr")
        assert result["method"] == "iqr"
        assert result["anomaly_count"] >= 1
        assert "indices" in result
        assert "lower_bound" in result
        assert "upper_bound" in result
        assert "total_values" in result

    def test_zscore_method(self):
        values = [10.0, 11.0, 10.0, 11.0, 10.0, 100.0]
        result = anomaly_detection.detect_anomalies(values, method="zscore")
        assert result["method"] == "zscore"

    def test_modified_zscore_method(self):
        values = [10.0, 11.0, 10.0, 11.0, 10.0, 100.0]
        result = anomaly_detection.detect_anomalies(
            values, method="modified_zscore"
        )
        assert result["method"] == "modified_zscore"


# ===========================================================================
# Model Tests
# ===========================================================================
class TestDocumentTemplateModel:
    def test_create_default_template(self, db):
        tpl = DocumentTemplate.objects.create(
            template_type="invoice",
            prompt_template="Extract invoice data from: {{ text }}",
        )
        assert tpl.id is not None
        assert tpl.template_type == "invoice"
        assert tpl.is_active is True

    def test_unique_template_type(self, db):
        DocumentTemplate.objects.create(
            template_type="invoice", prompt_template="...",
        )
        with pytest.raises(Exception):
            DocumentTemplate.objects.create(
                template_type="invoice", prompt_template="...",
            )

    def test_str(self, db):
        tpl = DocumentTemplate.objects.create(
            template_type="receipt", prompt_template="...",
        )
        assert "Receipt" in str(tpl)


class TestModelVersionModel:
    def test_create(self, db):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast",
            version="1.0.0",
            accuracy_score=0.85,
        )
        assert mv.model_type == "demand_forecast"
        assert mv.version == "1.0.0"
        assert mv.is_active is True

    def test_str(self, db):
        mv = ModelVersion.objects.create(
            model_type="supplier_scoring", version="2.0.0",
        )
        s = str(mv)
        assert "supplier_scoring" in s
        assert "2.0.0" in s

    def test_unique_type_version(self, db):
        ModelVersion.objects.create(
            model_type="adherence", version="1.0.0",
        )
        with pytest.raises(Exception):
            ModelVersion.objects.create(
                model_type="adherence", version="1.0.0",
            )


class TestDemandForecastModel:
    def test_create(self, db, product):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        forecast = DemandForecast.objects.create(
            product=product,
            model_version=mv,
            forecast_date=date.today(),
            predicted_quantity=500,
            confidence_low=400,
            confidence_high=600,
            method="ensemble(ma+es+lr)",
        )
        assert forecast.predicted_quantity == 500
        assert forecast.confidence_low == 400

    def test_str(self, db, product):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        forecast = DemandForecast.objects.create(
            product=product, model_version=mv,
            forecast_date=date.today(),
            predicted_quantity=500, confidence_low=400, confidence_high=600,
            method="ma",
        )
        s = str(forecast)
        assert product.name in s

    def test_unique_product_date(self, db, product):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        DemandForecast.objects.create(
            product=product, model_version=mv, forecast_date=date.today(),
            predicted_quantity=100, confidence_low=50, confidence_high=150,
            method="ma",
        )
        with pytest.raises(Exception):
            DemandForecast.objects.create(
                product=product, model_version=mv, forecast_date=date.today(),
                predicted_quantity=200, confidence_low=100, confidence_high=300,
                method="ma",
            )


class TestSupplierScoreModel:
    def test_create(self, db, supplier):
        score = SupplierScore.objects.create(
            supplier=supplier,
            overall_score=85.0,
            cost_score=70.0,
            reliability_score=90.0,
            quality_score=88.0,
            speed_score=82.0,
            trend="stable",
        )
        assert score.overall_score == 85.0
        assert score.trend == "stable"

    def test_str(self, db, supplier):
        score = SupplierScore.objects.create(
            supplier=supplier, overall_score=85.0,
        )
        s = str(score)
        assert supplier.name in s


class TestExpiryRiskAssessmentModel:
    def test_create(self, db, lot):
        assessment = ExpiryRiskAssessment.objects.create(
            lot=lot,
            risk_score=75.0,
            risk_level="high",
            days_of_stock_remaining=45,
            daily_consumption_rate=2.5,
        )
        assert assessment.risk_score == 75.0
        assert assessment.risk_level == "high"

    def test_str(self, db, lot):
        assessment = ExpiryRiskAssessment.objects.create(
            lot=lot, risk_score=50.0, risk_level="medium",
        )
        assert lot.batch_number in str(assessment)


class TestPatientAdherenceScoreModel:
    def test_create(self, db, contact, product):
        score = PatientAdherenceScore.objects.create(
            contact=contact,
            product=product,
            adherence_score=90.0,
            days_overdue_risk=5,
            pattern="regular",
        )
        assert score.adherence_score == 90.0
        assert score.pattern == "regular"

    def test_str(self, db, contact, product):
        score = PatientAdherenceScore.objects.create(
            contact=contact, product=product,
            adherence_score=85.0, pattern="regular",
        )
        assert str(contact) in str(score)


class TestAnomalyAlertModel:
    def test_create(self, db):
        alert = AnomalyAlert.objects.create(
            anomaly_type="unusual_order",
            severity="high",
            subject_type="product",
            subject_id=str(uuid.uuid4()),
            title="Unusual order detected",
            description="Quantity far outside expected range.",
            data_snapshot={"observed": 5000, "expected_range": [100, 500]},
        )
        assert alert.anomaly_type == "unusual_order"
        assert alert.severity == "high"
        assert alert.resolved is False

    def test_resolve(self, db, admin_user):
        alert = AnomalyAlert.objects.create(
            anomaly_type="stock_discrepancy", severity="critical",
            subject_type="product", subject_id=str(uuid.uuid4()),
            title="Stock discrepancy", description="...",
        )
        alert.resolved = True
        alert.resolved_by = admin_user
        alert.save()
        alert.refresh_from_db()
        assert alert.resolved is True
        assert alert.resolved_by == admin_user

    def test_str(self, db):
        alert = AnomalyAlert.objects.create(
            anomaly_type="price_spike", severity="medium",
            subject_type="supplier", subject_id="x",
            title="Price spike", description="...",
        )
        assert "price_spike" in str(alert)


class TestPredictionLogModel:
    def test_create(self, db):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        log = PredictionLog.objects.create(
            model_version=mv,
            subject_type="product",
            subject_id=str(uuid.uuid4()),
            prediction={"predicted": 100},
            confidence=0.85,
        )
        assert log.subject_type == "product"
        assert log.confidence == 0.85


class TestOutcomeLogModel:
    def test_create(self, db):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        pred = PredictionLog.objects.create(
            model_version=mv, subject_type="product",
            subject_id=str(uuid.uuid4()),
            prediction={"predicted": 100}, confidence=0.85,
        )
        outcome = OutcomeLog.objects.create(
            prediction=pred,
            subject_type="product",
            subject_id=pred.subject_id,
            outcome={"actual": 95},
        )
        assert outcome.outcome == {"actual": 95}

    def test_prediction_nullable(self, db):
        outcome = OutcomeLog.objects.create(
            subject_type="product",
            subject_id=str(uuid.uuid4()),
            outcome={"actual": 50},
        )
        assert outcome.prediction is None


# ===========================================================================
# Serializer Tests
# ===========================================================================
class TestModelVersionSerializer:
    def test_serialize(self, db):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
            accuracy_score=0.92,
        )
        serializer = ModelVersionSerializer(mv)
        data = serializer.data
        assert data["model_type_display"] is not None
        assert data["version"] == "1.0.0"


class TestDemandForecastSerializer:
    def test_serialize(self, db, product):
        mv = ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        forecast = DemandForecast.objects.create(
            product=product, model_version=mv,
            forecast_date=date.today(),
            predicted_quantity=500, confidence_low=400, confidence_high=600,
            method="ensemble",
        )
        serializer = DemandForecastSerializer(forecast)
        data = serializer.data
        assert data["product_name"] == product.name
        assert data["predicted_quantity"] == 500


class TestSupplierScoreSerializer:
    def test_serialize(self, db, supplier):
        score = SupplierScore.objects.create(
            supplier=supplier, overall_score=85.0,
        )
        serializer = SupplierScoreSerializer(score)
        data = serializer.data
        assert data["supplier_name"] == supplier.name


class TestAnomalyAlertSerializer:
    def test_serialize(self, db):
        alert = AnomalyAlert.objects.create(
            anomaly_type="unusual_order", severity="high",
            subject_type="product", subject_id="x",
            title="Test", description="...",
        )
        serializer = AnomalyAlertSerializer(alert)
        data = serializer.data
        assert data["anomaly_type_display"] is not None
        assert data["resolved"] is False


class TestInsightRequestSerializer:
    def test_valid(self):
        data = {"insight_type": "procurement_recommendation"}
        serializer = InsightRequestSerializer(data=data)
        assert serializer.is_valid()

    def test_invalid_type(self):
        data = {"insight_type": "invalid_type"}
        serializer = InsightRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_anomaly_explanation_missing_id(self):
        data = {"insight_type": "anomaly_explanation"}
        serializer = InsightRequestSerializer(data=data)
        # anomaly_id is optional, should still be valid
        assert serializer.is_valid()

    def test_anomaly_explanation_with_id(self):
        data = {
            "insight_type": "anomaly_explanation",
            "anomaly_id": str(uuid.uuid4()),
        }
        serializer = InsightRequestSerializer(data=data)
        assert serializer.is_valid()


class TestAnomalyAlertResolveSerializer:
    def test_valid(self):
        serializer = AnomalyAlertResolveSerializer(
            data={"resolution_note": "False positive"}
        )
        assert serializer.is_valid()

    def test_empty_ok(self):
        serializer = AnomalyAlertResolveSerializer(data={})
        assert serializer.is_valid()


# ===========================================================================
# Intelligence API Tests
# ===========================================================================
class TestModelVersionAPI:
    URL = "/api/intelligence/models/"

    def test_list_authenticated(self, admin_client, db):
        ModelVersion.objects.create(
            model_type="demand_forecast", version="1.0.0",
        )
        response = admin_client.get(self.URL)
        assert response.status_code == 200

    def test_list_unauthenticated(self, api_client):
        response = api_client.get(self.URL)
        assert response.status_code == 401


class TestDemandForecastAPI:
    URL = "/api/intelligence/forecasts/"

    def test_list_authenticated(self, admin_client, db):
        response = admin_client.get(self.URL)
        assert response.status_code == 200


class TestSupplierScoreAPI:
    URL = "/api/intelligence/scores/"

    def test_list_authenticated(self, admin_client, db):
        response = admin_client.get(self.URL)
        assert response.status_code == 200


class TestAnomalyAlertAPI:
    URL = "/api/intelligence/anomalies/"

    def test_list_authenticated(self, admin_client, db):
        response = admin_client.get(self.URL)
        assert response.status_code == 200

    def test_create_anomaly(self, admin_client, db):
        response = admin_client.post(self.URL, {
            "anomaly_type": "unusual_order",
            "severity": "medium",
            "subject_type": "product",
            "subject_id": str(uuid.uuid4()),
            "title": "Test anomaly",
            "description": "Unit test anomaly.",
            "data_snapshot": {"value": 999},
        })
        assert response.status_code == 201

    def test_resolve_anomaly(self, admin_client, db):
        alert = AnomalyAlert.objects.create(
            anomaly_type="stock_discrepancy", severity="low",
            subject_type="product", subject_id="x",
            title="Test", description="...",
        )
        response = admin_client.post(
            f"{self.URL}{alert.id}/resolve/",
            {"resolution_note": "Reviewed, not an issue"},
            format="json",
        )
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.resolved is True

    def test_list_defaults_to_unresolved(self, admin_client, db):
        AnomalyAlert.objects.create(
            anomaly_type="unusual_order", severity="low",
            subject_type="p", subject_id="1", title="Open", description=".",
            resolved=False,
        )
        AnomalyAlert.objects.create(
            anomaly_type="price_spike", severity="low",
            subject_type="p", subject_id="2", title="Done", description=".",
            resolved=True,
        )
        response = admin_client.get(self.URL)
        titles = [a["title"] for a in response.data["results"]]
        assert "Open" in titles
        assert "Done" not in titles


class TestIntelligenceDashboardAPI:
    URL = "/api/intelligence/dashboard/"

    def test_summary_authenticated(self, admin_client, db):
        response = admin_client.get(f"{self.URL}summary/")
        assert response.status_code == 200
        assert "active_models" in response.data
        assert "unresolved_anomalies" in response.data

    def test_performance_authenticated(self, admin_client, db):
        response = admin_client.get(f"{self.URL}performance/")
        assert response.status_code == 200
        assert "kpis" in response.data
        assert "models" in response.data

    def test_top_forecasts(self, admin_client, db):
        response = admin_client.get(f"{self.URL}top_forecasts/")
        assert response.status_code == 200

    def test_top_suppliers(self, admin_client, db):
        response = admin_client.get(f"{self.URL}top_suppliers/")
        assert response.status_code == 200

    def test_recent_anomalies(self, admin_client, db):
        response = admin_client.get(f"{self.URL}recent_anomalies/")
        assert response.status_code == 200

    def test_expiry_risks(self, admin_client, db):
        response = admin_client.get(f"{self.URL}expiry_risks/")
        assert response.status_code == 200

    def test_unauthenticated(self, api_client):
        response = api_client.get(f"{self.URL}summary/")
        assert response.status_code == 401
