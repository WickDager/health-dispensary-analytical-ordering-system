"""Self-learning feedback loop for HDAOS AI modules."""
from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Avg, Count, F, Sum

from apps.intelligence.models import ModelVersion, PredictionLog, OutcomeLog


def record_prediction(
    *,
    model_type: str,
    subject_type: str,
    subject_id: str,
    prediction: dict,
    confidence: float,
    input_snapshot: dict | None = None,
) -> PredictionLog:
    """Record a prediction for later evaluation."""
    version = ModelVersion.objects.filter(model_type=model_type, is_active=True).first()
    if not version:
        version = ModelVersion.objects.create(
            model_type=model_type, version="1.0.0", is_active=True
        )
    return PredictionLog.objects.create(
        model_version=version,
        subject_type=subject_type,
        subject_id=subject_id,
        prediction=prediction,
        confidence=confidence,
        input_snapshot=input_snapshot or {},
    )


def record_outcome(
    *,
    subject_type: str,
    subject_id: str,
    outcome: dict,
    prediction_id: str | None = None,
) -> OutcomeLog:
    """Record what actually happened."""
    pred = PredictionLog.objects.filter(pk=prediction_id).first() if prediction_id else None
    return OutcomeLog.objects.create(
        prediction=pred,
        subject_type=subject_type,
        subject_id=subject_id,
        outcome=outcome,
    )


def collect_demand_outcomes() -> int:
    """Compare demand forecasts to actual dispenses and record outcomes."""
    from apps.intelligence.models import DemandForecast

    count = 0
    # Find forecasts where the forecast date has passed
    past_forecasts = DemandForecast.objects.filter(
        forecast_date__lt=date.today()
    ).select_related("product", "model_version")

    for fc in past_forecasts:
        # Get actual dispenses for that product on that date
        from apps.audit.models import AuditLog

        actual = (
            AuditLog.objects.filter(
                action="DISPENSE",
                details__product_id=str(fc.product_id),
                timestamp__date=fc.forecast_date,
            ).aggregate(total=Sum(F("details__quantity")))["total"] or 0
        )

        # Find or create prediction log
        pred_log = PredictionLog.objects.filter(
            model_version=fc.model_version,
            subject_type="product",
            subject_id=str(fc.product_id),
            created_at__date=fc.created_at.date(),
        ).first()

        OutcomeLog.objects.get_or_create(
            prediction=pred_log,
            subject_type="product",
            subject_id=str(fc.product_id),
            defaults={
                "outcome": {
                    "actual_quantity": actual,
                    "predicted_quantity": fc.predicted_quantity,
                    "forecast_date": fc.forecast_date.isoformat(),
                }
            },
        )
        count += 1

    return count


def evaluate_model(model_type: str) -> dict:
    """Calculate accuracy metrics for a model type by comparing predictions to outcomes."""
    version = ModelVersion.objects.filter(model_type=model_type, is_active=True).first()
    if not version:
        return {"error": "No active model version"}

    predictions = PredictionLog.objects.filter(model_version=version)
    total = predictions.count()
    if total == 0:
        return {"accuracy": None, "total_predictions": 0}

    # For demand forecasting: calculate MAPE (Mean Absolute Percentage Error)
    if model_type == "demand_forecast":
        outcomes = OutcomeLog.objects.filter(
            prediction__model_version=version
        ).select_related("prediction")

        errors = []
        for o in outcomes:
            pred = o.prediction.prediction.get("predicted_total", 0)
            actual = o.outcome.get("actual_quantity", 0)
            if pred > 0:
                errors.append(abs(pred - actual) / pred)

        if errors:
            mape = sum(errors) / len(errors)
            accuracy = max(0.0, 1.0 - mape)
        else:
            accuracy = None

    # For supplier scoring: track if top-scored suppliers were actually chosen
    elif model_type == "supplier_scoring":
        accuracy = _evaluate_supplier_predictions(version)

    # For expiry risk: how many "high risk" lots actually expired
    elif model_type == "expiry_risk":
        accuracy = _evaluate_expiry_predictions(version)

    # For reorder point: compare predicted reorder timing to actual stockouts
    elif model_type == "reorder_point":
        accuracy = _evaluate_reorder_predictions(version)

    # For adherence: compare predicted adherence to actual refill behavior
    elif model_type == "adherence":
        accuracy = _evaluate_adherence_predictions(version)

    # For anomaly detection: precision/recall of anomaly alerts
    elif model_type == "anomaly":
        accuracy = _evaluate_anomaly_predictions(version)

    else:
        accuracy = None

    # Update model version accuracy
    if accuracy is not None:
        version.accuracy_score = round(accuracy, 4)
        version.save(update_fields=["accuracy_score"])

    return {
        "model_type": model_type,
        "version": version.version,
        "accuracy": accuracy,
        "total_predictions": total,
        "needs_retraining": accuracy is not None and accuracy < 0.7,
    }


def _evaluate_supplier_predictions(version: ModelVersion) -> float:
    """Check how often the highest-scored supplier was actually selected for orders."""
    predictions = PredictionLog.objects.filter(model_version=version)
    if not predictions.exists():
        return 1.0
    # Simplified: count predictions where outcome matched
    correct = 0
    for p in predictions:
        outcomes = p.outcomes.first()
        if outcomes and outcomes.outcome.get("selected"):
            correct += 1
    return correct / predictions.count()


def _evaluate_expiry_predictions(version: ModelVersion) -> float:
    """Check how many high-risk lots actually expired vs were consumed."""
    from apps.intelligence.models import ExpiryRiskAssessment

    assessments = ExpiryRiskAssessment.objects.filter(
        risk_level__in=["high", "critical"]
    )
    if not assessments.exists():
        return 1.0
    expired = sum(
        1
        for a in assessments
        if a.lot.is_locked and a.lot.expiry_date <= date.today()
    )
    # Lower expired rate = higher accuracy
    return 1.0 - (expired / assessments.count())


def _evaluate_reorder_predictions(version: ModelVersion) -> float:
    """Check how often reorder predictions correctly anticipated stockouts."""
    predictions = PredictionLog.objects.filter(model_version=version)
    if not predictions.exists():
        return 1.0
    correct = 0
    total_with_outcomes = 0
    for p in predictions:
        outcomes = p.outcomes.first()
        if outcomes:
            total_with_outcomes += 1
            predicted_reorder = p.prediction.get("should_reorder", False)
            actual_stockout = outcomes.outcome.get("stockout_occurred", False)
            # Correct if: we said reorder and stockout happened, OR we said no reorder and no stockout
            if predicted_reorder == actual_stockout:
                correct += 1
    if total_with_outcomes == 0:
        return 1.0
    return correct / total_with_outcomes


def _evaluate_adherence_predictions(version: ModelVersion) -> float:
    """Compare predicted adherence scores to actual refill timeliness."""
    from apps.intelligence.models import PatientAdherenceScore

    scores = PatientAdherenceScore.objects.all()
    if not scores.exists():
        return 1.0
    # Evaluate how well adherence_score correlates with days_overdue
    # Higher adherence_score should mean lower days_overdue_risk
    high_adherence = scores.filter(adherence_score__gte=70)
    low_adherence = scores.filter(adherence_score__lt=70)
    if not high_adherence.exists() or not low_adherence.exists():
        return 1.0
    high_avg_overdue = high_adherence.aggregate(avg=Avg("days_overdue_risk"))["avg"] or 0
    low_avg_overdue = low_adherence.aggregate(avg=Avg("days_overdue_risk"))["avg"] or 0
    # If high adherence patients have lower overdue risk, model is working
    if high_avg_overdue <= low_avg_overdue:
        return 0.8  # Directionally correct
    return 0.3  # Model is inverted


def _evaluate_anomaly_predictions(version: ModelVersion) -> float:
    """Evaluate anomaly detection: what fraction of alerts were marked resolved."""
    from apps.intelligence.models import AnomalyAlert

    alerts = AnomalyAlert.objects.all()
    if not alerts.exists():
        return 1.0
    resolved = alerts.filter(resolved=True).count()
    # High-severity alerts that were resolved quickly indicate good detection
    high_severity_resolved = alerts.filter(severity__in=["high", "critical"], resolved=True).count()
    high_severity_total = alerts.filter(severity__in=["high", "critical"]).count()
    if high_severity_total == 0:
        return 1.0
    return high_severity_resolved / high_severity_total


@transaction.atomic
def auto_retrain_if_needed() -> list[dict]:
    """Check all models and retrain any whose accuracy has dropped below threshold."""
    results = []
    for model_type, _ in ModelVersion.MODEL_TYPES:
        eval_result = evaluate_model(model_type)
        if eval_result.get("needs_retraining"):
            # Create new version with adjusted parameters
            old_version = ModelVersion.objects.filter(
                model_type=model_type, is_active=True
            ).first()
            if old_version:
                old_version.is_active = False
                old_version.save(update_fields=["is_active"])

            new_version_num = _bump_version(
                old_version.version if old_version else "1.0.0"
            )
            new_version = ModelVersion.objects.create(
                model_type=model_type,
                version=new_version_num,
                is_active=True,
                parameters=_adjust_parameters(model_type, eval_result),
            )
            results.append(
                {
                    "model_type": model_type,
                    "old_version": old_version.version if old_version else None,
                    "new_version": new_version_num,
                    "old_accuracy": old_version.accuracy_score if old_version else None,
                }
            )
    return results


def _bump_version(version: str) -> str:
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def _adjust_parameters(model_type: str, eval_result: dict) -> dict:
    """Adjust model parameters based on evaluation results."""
    accuracy = eval_result.get("accuracy", 0.5)
    params = {"auto_tuned": True, "previous_accuracy": accuracy}

    if model_type == "demand_forecast":
        # If accuracy is low, increase smoothing window
        if accuracy < 0.6:
            params["window"] = 14  # larger window for stability
            params["alpha"] = 0.2  # less reactive
        else:
            params["window"] = 7
            params["alpha"] = 0.3

    elif model_type == "supplier_scoring":
        if accuracy < 0.6:
            params["cost_weight"] = 0.3
            params["reliability_weight"] = 0.4
            params["quality_weight"] = 0.2
            params["speed_weight"] = 0.1
        else:
            params["cost_weight"] = 0.35
            params["reliability_weight"] = 0.25
            params["quality_weight"] = 0.25
            params["speed_weight"] = 0.15

    elif model_type == "expiry_risk":
        if accuracy < 0.6:
            params["risk_threshold_high"] = 60
            params["risk_threshold_critical"] = 80
        else:
            params["risk_threshold_high"] = 50
            params["risk_threshold_critical"] = 70

    elif model_type == "reorder_point":
        if accuracy < 0.6:
            params["lead_time_buffer_days"] = 5
            params["safety_stock_factor"] = 1.5
        else:
            params["lead_time_buffer_days"] = 3
            params["safety_stock_factor"] = 1.2

    elif model_type == "adherence":
        if accuracy < 0.6:
            params["lookback_days"] = 180
            params["min_data_points"] = 3
        else:
            params["lookback_days"] = 90
            params["min_data_points"] = 2

    elif model_type == "anomaly":
        if accuracy < 0.6:
            params["zscore_threshold"] = 2.0  # more sensitive
            params["min_deviation_pct"] = 20
        else:
            params["zscore_threshold"] = 3.0
            params["min_deviation_pct"] = 30

    return params
