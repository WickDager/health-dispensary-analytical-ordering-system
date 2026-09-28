"""Expiry risk assessment -- statistical, no sklearn.

For each lot, calculate:
- Current consumption rate (7-day moving average of dispenses)
- Projected exhaustion date (when stock hits zero at current rate)
- Risk of stock expiring before consumed
- Composite risk score and risk level
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Sequence
import math


def consumption_rate(
    dispense_history: Sequence[float], window: int = 7
) -> float:
    """Daily consumption rate from the last N days of dispense data."""
    if not dispense_history:
        return 0.0
    recent = dispense_history[-window:]
    return sum(recent) / len(recent)


def projected_exhaustion_date(
    current_stock: int, daily_rate: float
) -> date | None:
    """Date when stock reaches zero at current consumption rate."""
    if daily_rate <= 0 or current_stock <= 0:
        return None
    days_remaining = current_stock / daily_rate
    return date.today() + timedelta(days=int(math.ceil(days_remaining)))


def days_of_stock_remaining(
    current_stock: int, daily_rate: float
) -> int | None:
    """Days of inventory left at current consumption rate."""
    if daily_rate <= 0:
        return None
    return int(math.ceil(current_stock / daily_rate))


def assess_lot_risk(lot_id: str) -> dict:
    """Full expiry risk assessment for a single lot.

    Returns dict with risk_score, risk_level, daily_consumption_rate,
    estimated_exhaustion_date, days_of_stock_remaining, days_to_expiry.
    """
    from apps.lots.models import Lot
    from apps.audit.models import AuditLog

    today = date.today()

    try:
        lot = Lot.objects.select_related("product").get(id=lot_id)
    except Lot.DoesNotExist:
        return {
            "risk_score": 0,
            "risk_level": "low",
            "daily_consumption_rate": 0.0,
            "estimated_exhaustion_date": None,
            "days_of_stock_remaining": None,
            "days_to_expiry": 0,
        }

    days_to_expiry = (lot.expiry_date - today).days
    current_stock = lot.quantity

    # Get dispense history for this lot's product over the last 60 days
    dispenses = AuditLog.objects.filter(
        action="DISPENSE",
        details__product_id=str(lot.product_id),
        timestamp__gte=today - timedelta(days=60),
    ).order_by("timestamp")

    # Aggregate by day
    daily: dict[str, float] = {}
    for d in dispenses:
        day = d.timestamp.date().isoformat()
        qty = d.details.get("quantity", 0)
        daily[day] = daily.get(day, 0) + qty

    values = list(daily.values())
    rate = consumption_rate(values, window=7)

    exhaustion_date = projected_exhaustion_date(current_stock, rate)
    stock_remaining_days = days_of_stock_remaining(current_stock, rate)

    # Risk score: 0-100
    # High risk = lot expires before stock is consumed
    if rate <= 0:
        # No consumption data -- risk based on expiry proximity
        if days_to_expiry <= 30:
            risk_score = 75.0
            risk_level = "high"
        elif days_to_expiry <= 90:
            risk_score = 50.0
            risk_level = "medium"
        else:
            risk_score = 20.0
            risk_level = "low"
    elif exhaustion_date is None:
        risk_score = 0.0
        risk_level = "low"
    else:
        risk_days = (lot.expiry_date - exhaustion_date).days
        shelf_life = (lot.expiry_date - lot.manufacture_date).days
        if shelf_life <= 0:
            shelf_life = 365

        # Time pressure
        if days_to_expiry <= 0:
            time_pressure = 1.0
        elif days_to_expiry >= shelf_life:
            time_pressure = 0.0
        else:
            time_pressure = 1.0 - (days_to_expiry / shelf_life)

        # Waste ratio
        if risk_days >= 0:
            # Stock will be consumed before expiry -- low risk
            risk = time_pressure * 50.0  # only time pressure matters
        else:
            # Stock will expire before consumption
            waste_ratio = min(1.0, abs(risk_days) / shelf_life)
            risk = (0.6 * waste_ratio + 0.4 * time_pressure) * 100.0

        risk_score = max(0.0, min(100.0, risk))

        if risk_score >= 80:
            risk_level = "critical"
        elif risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"

    return {
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "daily_consumption_rate": round(rate, 3),
        "estimated_exhaustion_date": (
            exhaustion_date.isoformat() if exhaustion_date else None
        ),
        "days_of_stock_remaining": stock_remaining_days,
        "days_to_expiry": days_to_expiry,
    }


def assess_all_lot_risks() -> list[dict]:
    """Run expiry risk assessment for every active lot and persist results."""
    from apps.lots.models import Lot
    from apps.intelligence.models import (
        ExpiryRiskAssessment,
        ModelVersion,
        PredictionLog,
    )

    model_version, _ = ModelVersion.objects.get_or_create(
        model_type="expiry_risk",
        version="3.0.0",
        defaults={
            "is_active": True,
            "parameters": {"method": "consumption_rate_projection"},
        },
    )
    ModelVersion.objects.filter(
        model_type="expiry_risk", is_active=True
    ).exclude(pk=model_version.pk).update(is_active=False)

    results: list[dict] = []
    for lot in Lot.objects.filter(is_locked=False, quantity__gt=0):
        assessment = assess_lot_risk(str(lot.id))

        exhaustion_date = None
        if assessment["estimated_exhaustion_date"]:
            exhaustion_date = date.fromisoformat(
                assessment["estimated_exhaustion_date"]
            )

        ExpiryRiskAssessment.objects.create(
            lot=lot,
            risk_score=assessment["risk_score"],
            risk_level=assessment["risk_level"],
            estimated_exhaustion_date=exhaustion_date,
            days_of_stock_remaining=assessment["days_of_stock_remaining"],
            daily_consumption_rate=assessment["daily_consumption_rate"],
        )

        PredictionLog.objects.create(
            model_version=model_version,
            subject_type="lot",
            subject_id=str(lot.id),
            prediction=assessment,
        )

        assessment["lot_id"] = str(lot.id)
        assessment["batch_number"] = lot.batch_number
        assessment["product_name"] = lot.product.name
        results.append(assessment)

    return results
