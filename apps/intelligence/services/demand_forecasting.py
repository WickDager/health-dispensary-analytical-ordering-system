"""Demand forecasting using statistical methods (no sklearn)."""
from __future__ import annotations
from datetime import date, timedelta
from typing import Sequence
import math


def moving_average(values: Sequence[float], window: int = 7) -> float:
    """Simple moving average of the last N values."""
    if not values:
        return 0.0
    recent = values[-window:]
    return sum(recent) / len(recent)


def exponential_smoothing(values: Sequence[float], alpha: float = 0.3) -> float:
    """Exponential smoothing -- more weight to recent values."""
    if not values:
        return 0.0
    smoothed = values[0]
    for v in values[1:]:
        smoothed = alpha * v + (1 - alpha) * smoothed
    return smoothed


def double_exponential_smoothing(
    values: Sequence[float], alpha: float = 0.3, beta: float = 0.2
) -> tuple[float, float]:
    """Holt's double exponential smoothing -- returns (level, trend)."""
    if not values:
        return 0.0, 0.0
    level = values[0]
    trend = values[1] - values[0] if len(values) > 1 else 0.0
    for i in range(1, len(values)):
        prev_level = level
        level = alpha * values[i] + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return level, trend


def linear_regression_slope(
    x: Sequence[float], y: Sequence[float]
) -> tuple[float, float]:
    """Simple linear regression: y = slope * x + intercept."""
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)
    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return 0.0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def trend_direction(values: Sequence[float]) -> str:
    """Classify trend: 'rising', 'falling', 'stable'."""
    if len(values) < 3:
        return "stable"
    x = list(range(len(values)))
    slope, _ = linear_regression_slope(x, list(values))
    avg = sum(values) / len(values) if values else 1
    if avg == 0:
        return "stable"
    relative = slope / avg
    if relative > 0.05:
        return "rising"
    elif relative < -0.05:
        return "falling"
    return "stable"


def classify_velocity(
    values: Sequence[float],
    threshold_high: float = 0.8,
    threshold_low: float = 0.2,
) -> str:
    """Classify product as 'fast_mover', 'moderate', or 'slow_mover'."""
    if not values:
        return "slow_mover"
    avg = sum(values) / len(values)
    max_val = max(values) if values else 1
    if max_val == 0:
        return "slow_mover"
    normalized = avg / max_val
    if normalized > threshold_high:
        return "fast_mover"
    elif normalized > threshold_low:
        return "moderate"
    return "slow_mover"


def coefficient_of_variation(values: Sequence[float]) -> float:
    """CV = std / mean. Measures relative volatility."""
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance) / mean


def mean_absolute_percentage_error(
    actual: Sequence[float], predicted: Sequence[float]
) -> float:
    """MAPE between two equal-length sequences."""
    if not actual or len(actual) != len(predicted):
        return float("inf")
    errors = []
    for a, p in zip(actual, predicted):
        if a == 0:
            continue
        errors.append(abs((a - p) / a))
    if not errors:
        return float("inf")
    return sum(errors) / len(errors)


def predict_demand(product_id: str, days_ahead: int = 30) -> dict:
    """Full demand forecast for a product. Returns forecast dict."""
    from apps.audit.models import AuditLog

    today = date.today()

    dispenses = (
        AuditLog.objects.filter(
            action="DISPENSE",
            details__product_id=str(product_id),
            timestamp__gte=today - timedelta(days=90),
        )
        .order_by("timestamp")
    )

    daily: dict[str, float] = {}
    for d in dispenses:
        day = d.timestamp.date().isoformat()
        qty = d.details.get("quantity", 0)
        daily[day] = daily.get(day, 0) + qty

    values = list(daily.values())
    if not values:
        return {
            "predicted_daily": 0,
            "predicted_total": 0,
            "trend": "stable",
            "velocity": "slow_mover",
            "confidence": 0.0,
            "confidence_low": 0,
            "confidence_high": 0,
            "method": "ensemble(ma+es+lr)",
        }

    ma = moving_average(values, window=7)
    es = exponential_smoothing(values, alpha=0.3)

    x = list(range(len(values)))
    slope, intercept = linear_regression_slope(x, list(values))
    lr_current = max(0, slope * len(values) + intercept)

    predicted_daily = round(
        0.4 * ma + 0.3 * es + 0.3 * lr_current / (len(values) or 1)
    )
    predicted_total = predicted_daily * days_ahead

    trend = trend_direction(values)
    velocity = classify_velocity(values)

    if len(values) < 7:
        confidence = 0.3
    else:
        variance = sum((v - ma) ** 2 for v in values) / len(values)
        cv = math.sqrt(variance) / ma if ma > 0 else 1.0
        confidence = max(0.1, min(0.95, 1.0 - cv))

    ci_margin = int(predicted_total * 0.2 * (1.0 - confidence))
    confidence_low = max(0, predicted_total - ci_margin)
    confidence_high = predicted_total + ci_margin

    return {
        "predicted_daily": predicted_daily,
        "predicted_total": predicted_total,
        "trend": trend,
        "velocity": velocity,
        "confidence": round(confidence, 3),
        "confidence_low": confidence_low,
        "confidence_high": confidence_high,
        "method": "ensemble(ma+es+lr)",
    }


def forecast_all_products(days_ahead: int = 30) -> list[dict]:
    """Run demand prediction for every product and persist results."""
    from apps.catalog.models import Product
    from apps.intelligence.models import (
        DemandForecast,
        ModelVersion,
        PredictionLog,
    )

    model_version, _ = ModelVersion.objects.get_or_create(
        model_type="demand_forecast",
        version="3.0.0",
        defaults={
            "is_active": True,
            "parameters": {"method": "ensemble(ma+es+lr)", "days_ahead": days_ahead},
        },
    )
    ModelVersion.objects.filter(
        model_type="demand_forecast", is_active=True
    ).exclude(pk=model_version.pk).update(is_active=False)

    today = date.today()
    results: list[dict] = []

    for product in Product.objects.all():
        forecast = predict_demand(str(product.id), days_ahead=days_ahead)

        DemandForecast.objects.create(
            product=product,
            model_version=model_version,
            forecast_date=today,
            predicted_quantity=forecast["predicted_total"],
            confidence_low=forecast["confidence_low"],
            confidence_high=forecast["confidence_high"],
            method=forecast["method"],
        )

        PredictionLog.objects.create(
            model_version=model_version,
            subject_type="product",
            subject_id=str(product.id),
            prediction=forecast,
            confidence=forecast["confidence"],
            input_snapshot={"days_ahead": days_ahead, "today": today.isoformat()},
        )

        forecast["product_id"] = str(product.id)
        results.append(forecast)

    return results
