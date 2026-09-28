"""Celery tasks for the HDAOS v3.0 intelligence pipeline.

All tasks are designed to run nightly via Celery Beat. Each task
can also be triggered manually for ad-hoc analysis.
"""
from __future__ import annotations

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Individual pipeline stages
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    name="intelligence.forecast_all_products",
)
def forecast_all_products_task(self, days_ahead: int = 30):
    """Run demand forecasting for every catalog product."""
    from apps.intelligence.services.demand_forecasting import forecast_all_products

    logger.info("Starting demand forecasting (days_ahead=%d)...", days_ahead)
    try:
        results = forecast_all_products(days_ahead=days_ahead)
        logger.info("Demand forecasting complete: %d products.", len(results))
        return {"status": "ok", "products_forecasted": len(results)}
    except Exception:
        logger.exception("Demand forecasting failed.")
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    name="intelligence.score_all_suppliers",
)
def score_all_suppliers_task(self):
    """Score every supplier on cost, reliability, quality, and speed."""
    from apps.intelligence.services.supplier_scoring import score_all_suppliers

    logger.info("Starting supplier scoring...")
    try:
        results = score_all_suppliers()
        logger.info("Supplier scoring complete: %d suppliers.", len(results))
        return {"status": "ok", "suppliers_scored": len(results)}
    except Exception:
        logger.exception("Supplier scoring failed.")
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    name="intelligence.assess_all_lot_risks",
)
def assess_all_lot_risks_task(self):
    """Assess expiry risk for every active (unlocked, stocked) lot."""
    from apps.intelligence.services.expiry_risk import assess_all_lot_risks

    logger.info("Starting expiry risk assessment...")
    try:
        results = assess_all_lot_risks()
        logger.info("Expiry risk complete: %d lots.", len(results))
        critical = sum(1 for r in results if r["risk_level"] == "critical")
        high = sum(1 for r in results if r["risk_level"] == "high")
        logger.info("  Critical: %d, High: %d", critical, high)
        return {
            "status": "ok",
            "lots_assessed": len(results),
            "critical": critical,
            "high": high,
        }
    except Exception:
        logger.exception("Expiry risk assessment failed.")
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    name="intelligence.score_all_patient_adherence",
)
def score_all_patient_adherence_task(self):
    """Score refill adherence for every patient contact."""
    from apps.intelligence.services.adherence import score_all_patient_adherence

    logger.info("Starting patient adherence scoring...")
    try:
        results = score_all_patient_adherence()
        logger.info("Adherence scoring complete: %d patients.", len(results))
        declining = sum(1 for r in results if r["pattern"] == "declining")
        irregular = sum(1 for r in results if r["pattern"] == "irregular")
        overdue = sum(1 for r in results if r["days_overdue_risk"] > 0)
        logger.info("  Declining: %d, Irregular: %d, Overdue: %d",
                     declining, irregular, overdue)
        return {
            "status": "ok",
            "patients_scored": len(results),
            "declining": declining,
            "irregular": irregular,
            "overdue": overdue,
        }
    except Exception:
        logger.exception("Adherence scoring failed.")
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    name="intelligence.detect_all_anomalies",
)
def detect_all_anomalies_task(self):
    """Run anomaly detection across all dimensions."""
    from apps.intelligence.services.anomaly_detection import detect_all_anomalies

    logger.info("Starting anomaly detection...")
    try:
        results = detect_all_anomalies()
        logger.info("Anomaly detection complete: %d anomalies.", len(results))
        critical = sum(1 for r in results if r["severity"] == "critical")
        high = sum(1 for r in results if r["severity"] == "high")
        medium = sum(1 for r in results if r["severity"] == "medium")
        low = sum(1 for r in results if r["severity"] == "low")
        logger.info("  Critical: %d, High: %d, Medium: %d, Low: %d",
                     critical, high, medium, low)
        return {
            "status": "ok",
            "anomalies_found": len(results),
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
        }
    except Exception:
        logger.exception("Anomaly detection failed.")
        raise


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    autoretry_for=(Exception,),
    name="intelligence.evaluate_models",
)
def evaluate_models_task(self):
    """Self-learning feedback loop: compare predictions against outcomes.

    Finds recent PredictionLog entries, computes actual-vs-predicted
    error metrics, and persists OutcomeLog records for continuous
    model improvement tracking.
    """
    from datetime import date, timedelta
    from apps.intelligence.models import PredictionLog, OutcomeLog, DemandForecast

    logger.info("Starting model evaluation (feedback loop)...")
    try:
        today = date.today()
        window = today - timedelta(days=7)

        recent_forecasts = DemandForecast.objects.filter(
            created_at__date__gte=window,
        ).select_related("product", "model_version")

        evaluated = 0
        for forecast in recent_forecasts:
            from apps.audit.models import AuditLog

            actual_dispenses = AuditLog.objects.filter(
                action="DISPENSE",
                details__product_id=str(forecast.product_id),
                timestamp__gte=forecast.created_at,
            )
            actual_total = sum(
                d.details.get("quantity", 0) for d in actual_dispenses
            )

            prediction = (
                PredictionLog.objects.filter(
                    model_version=forecast.model_version,
                    subject_type="product",
                    subject_id=str(forecast.product_id),
                    created_at__date=forecast.created_at.date(),
                )
                .first()
            )

            if prediction and actual_total > 0:
                predicted_total = forecast.predicted_quantity
                ape = abs(predicted_total - actual_total) / actual_total

                OutcomeLog.objects.create(
                    prediction=prediction,
                    subject_type="product",
                    subject_id=str(forecast.product_id),
                    outcome={
                        "actual_total_consumed": actual_total,
                        "predicted_total": predicted_total,
                        "ape": round(ape, 4),
                    },
                )
                evaluated += 1

        logger.info("Model evaluation complete: %d outcomes recorded.", evaluated)
        return {"status": "ok", "outcomes_recorded": evaluated}
    except Exception:
        logger.exception("Model evaluation failed.")
        raise


# ---------------------------------------------------------------------------
# Master pipeline orchestrator
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=1,
    name="intelligence.nightly_intelligence_pipeline",
)
def nightly_intelligence_pipeline(self):
    """Run the complete intelligence pipeline in order.

    Orchestrates all prediction, scoring, risk assessment, anomaly
    detection, and model evaluation tasks sequentially. Each stage
    is independent enough to fail without blocking the rest.
    """
    logger.info("=" * 60)
    logger.info("Nightly Intelligence Pipeline START")
    logger.info("=" * 60)

    stages = [
        ("Demand Forecasting", forecast_all_products_task),
        ("Supplier Scoring", score_all_suppliers_task),
        ("Expiry Risk Assessment", assess_all_lot_risks_task),
        ("Patient Adherence", score_all_patient_adherence_task),
        ("Anomaly Detection", detect_all_anomalies_task),
        ("Model Evaluation", evaluate_models_task),
    ]

    results = {}
    for stage_name, task_fn in stages:
        logger.info("--- Stage: %s ---", stage_name)
        try:
            result = task_fn.delay()
            results[stage_name] = {
                "status": "queued",
                "task_id": result.task_id,
            }
            logger.info("  Queued: %s", result.task_id)
        except Exception:
            logger.exception("  FAILED to queue %s", stage_name)
            results[stage_name] = {
                "status": "error",
                "task_id": None,
            }

    logger.info("=" * 60)
    logger.info("Nightly Intelligence Pipeline END -- %d stages queued",
                len(results))
    logger.info("=" * 60)

    return {
        "status": "ok",
        "stages": results,
    }
