"""Master orchestrator that executes all AI modules in sequence.

Usage::

    from apps.intelligence.services.run_pipeline import run_full_intelligence_pipeline
    summary = run_full_intelligence_pipeline()
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils import timezone

from apps.intelligence.models import ModelVersion

logger = logging.getLogger("hdaos.intelligence.pipeline")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_full_intelligence_pipeline() -> dict:
    """Run all AI predictions, collect outcomes, and evaluate every model.

    Returns a summary dict suitable for the API response.
    """
    results: dict = {
        "started_at": timezone.now().isoformat(),
        "demand": {},
        "suppliers": {},
        "expiry": {},
        "adherence": {},
        "anomalies": {},
        "outcomes": 0,
        "evaluation": [],
    }

    # ---- 1. Demand Forecasting ------------------------------------------
    logger.info("Pipeline: starting demand forecasting ...")
    try:
        from apps.intelligence.services.demand_forecasting import (
            forecast_all_products,
        )

        results["demand"] = forecast_all_products(days_ahead=30) or {}
        logger.info("Pipeline: demand forecasting complete.")
    except ImportError:
        logger.warning("Pipeline: demand_forecasting module not available.")
        results["demand"] = {"error": "demand_forecasting module not available"}
    except Exception as exc:
        logger.exception("Pipeline: demand forecasting failed.")
        results["demand"] = {"error": str(exc)}

    # ---- 2. Supplier Scoring --------------------------------------------
    logger.info("Pipeline: starting supplier scoring ...")
    try:
        from apps.intelligence.services.supplier_scoring import score_all_suppliers

        results["suppliers"] = score_all_suppliers() or {}
        logger.info("Pipeline: supplier scoring complete.")
    except ImportError:
        logger.warning("Pipeline: supplier_scoring module not available.")
        results["suppliers"] = {"error": "supplier_scoring module not available"}
    except Exception as exc:
        logger.exception("Pipeline: supplier scoring failed.")
        results["suppliers"] = {"error": str(exc)}

    # ---- 3. Expiry Risk Assessment --------------------------------------
    logger.info("Pipeline: starting expiry risk assessment ...")
    try:
        from apps.intelligence.services.expiry_risk import assess_all_lot_risks

        results["expiry"] = assess_all_lot_risks() or {}
        logger.info("Pipeline: expiry risk assessment complete.")
    except ImportError:
        logger.warning("Pipeline: expiry_risk module not available.")
        results["expiry"] = {"error": "expiry_risk module not available"}
    except Exception as exc:
        logger.exception("Pipeline: expiry risk assessment failed.")
        results["expiry"] = {"error": str(exc)}

    # ---- 4. Patient Adherence Scoring -----------------------------------
    logger.info("Pipeline: starting patient adherence scoring ...")
    try:
        from apps.intelligence.services.adherence_scoring import (
            score_all_patient_adherence,
        )

        results["adherence"] = score_all_patient_adherence() or {}
        logger.info("Pipeline: patient adherence scoring complete.")
    except ImportError:
        logger.warning("Pipeline: adherence_scoring module not available.")
        results["adherence"] = {"error": "adherence_scoring module not available"}
    except Exception as exc:
        logger.exception("Pipeline: patient adherence scoring failed.")
        results["adherence"] = {"error": str(exc)}

    # ---- 5. Anomaly Detection -------------------------------------------
    logger.info("Pipeline: starting anomaly detection ...")
    try:
        from apps.intelligence.services.anomaly_detection import detect_all_anomalies

        results["anomalies"] = detect_all_anomalies() or {}
        logger.info("Pipeline: anomaly detection complete.")
    except ImportError:
        logger.warning("Pipeline: anomaly_detection module not available.")
        results["anomalies"] = {"error": "anomaly_detection module not available"}
    except Exception as exc:
        logger.exception("Pipeline: anomaly detection failed.")
        results["anomalies"] = {"error": str(exc)}

    # ---- 6. Collect Outcomes --------------------------------------------
    logger.info("Pipeline: collecting demand outcomes ...")
    try:
        from apps.intelligence.services.feedback_loop import collect_demand_outcomes

        results["outcomes"] = collect_demand_outcomes()
        logger.info(f"Pipeline: {results['outcomes']} outcomes recorded.")
    except ImportError:
        logger.warning("Pipeline: feedback_loop module not available.")
        results["outcomes"] = -1
    except Exception as exc:
        logger.exception("Pipeline: outcome collection failed.")
        results["outcomes"] = -1

    # ---- 7. Model Evaluation --------------------------------------------
    logger.info("Pipeline: evaluating all models ...")
    try:
        from apps.intelligence.services.feedback_loop import evaluate_model

        # Evaluate every unique model name that has an active version
        model_names = (
            ModelVersion.objects.filter(is_active=True)
            .values_list("name", flat=True)
            .distinct()
        )
        for model_name in model_names:
            try:
                eval_result = evaluate_model(model_name)
                results["evaluation"].append(eval_result)
            except Exception as exc:
                results["evaluation"].append(
                    {"model_type": model_name, "error": str(exc)}
                )
        logger.info(
            f"Pipeline: {len(results['evaluation'])} models evaluated."
        )
    except ImportError:
        logger.warning("Pipeline: feedback_loop evaluate_model not available.")
        results["evaluation"] = [
            {"error": "feedback_loop.evaluate_model not available"}
        ]
    except Exception as exc:
        logger.exception("Pipeline: model evaluation failed.")
        results["evaluation"] = [{"error": str(exc)}]

    results["finished_at"] = timezone.now().isoformat()
    logger.info("Pipeline: full intelligence pipeline complete.")
    return results
