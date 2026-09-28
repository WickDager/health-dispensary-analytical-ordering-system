"""Patient adherence scoring -- statistical, no sklearn.

Scores each patient's refill pattern per product:
- regular / declining / irregular / new
- days_overdue_risk
- adherence_score (0-100)
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Sequence
import math


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _interval_days(dates: Sequence[date]) -> list[int]:
    """Compute days between consecutive dates, sorted ascending."""
    if len(dates) < 2:
        return []
    sorted_dates = sorted(dates)
    return [
        (sorted_dates[i + 1] - sorted_dates[i]).days
        for i in range(len(sorted_dates) - 1)
    ]


def classify_refill_pattern(
    intervals: Sequence[int],
    min_events: int = 3,
    decline_threshold: float = 0.15,
) -> str:
    """Classify refill pattern from intervals between refills."""
    if len(intervals) < min_events - 1:
        return "new"

    mean_iv = _mean(intervals)
    std_iv = _std(intervals)

    if mean_iv == 0:
        return "irregular"

    cv = std_iv / mean_iv

    from apps.intelligence.services.demand_forecasting import (
        linear_regression_slope,
    )
    x = list(range(len(intervals)))
    slope, _ = linear_regression_slope(x, list(intervals))

    if len(intervals) >= 3 and slope > 0 and slope / mean_iv > decline_threshold:
        return "declining"

    if cv < 0.25:
        return "regular"

    return "irregular"


def adherence_score_from_intervals(intervals: Sequence[int]) -> float:
    """Map refill consistency to a 0-100 adherence score."""
    if len(intervals) < 1:
        return 0.0

    mean_iv = _mean(intervals)
    if mean_iv == 0:
        return 0.0

    std_iv = _std(intervals)
    cv = std_iv / mean_iv

    base_score = max(0.0, 100.0 - (cv / 1.5) * 100.0)

    if len(intervals) >= 3:
        from apps.intelligence.services.demand_forecasting import (
            linear_regression_slope,
        )
        x = list(range(len(intervals)))
        slope, _ = linear_regression_slope(x, list(intervals))
        if slope > 0:
            penalty = (slope / mean_iv) * 50.0
            base_score = max(0.0, base_score - penalty)

    return max(0.0, min(100.0, base_score))


def days_overdue(expected_interval: float, days_since_last: int) -> int:
    """Days past expected refill date. Positive = overdue."""
    if expected_interval <= 0 or days_since_last <= 0:
        return 0
    grace = expected_interval * 0.2
    threshold = expected_interval + grace
    overdue = days_since_last - threshold
    return max(0, int(overdue))


def score_patient_adherence(contact_id: str, product_id: str = None) -> dict:
    """Full adherence analysis for a single patient and product.

    Returns dict with:
        pattern, adherence_score, days_overdue_risk
    """
    from apps.crm.models import Contact, RefillReminder
    from apps.audit.models import AuditLog

    today = date.today()

    try:
        contact = Contact.objects.get(id=contact_id, contact_type="PATIENT")
    except Contact.DoesNotExist:
        return {
            "pattern": "new",
            "adherence_score": 0.0,
            "days_overdue_risk": 0,
        }

    # Get dispense events for this patient from audit log, optionally filtered by product
    dispense_filter = {
        "action": "DISPENSE",
        "details__contact_id": contact_id,
        "timestamp__gte": today - timedelta(days=365),
    }
    if product_id:
        dispense_filter["details__product_id"] = product_id

    dispenses = (
        AuditLog.objects.filter(**dispense_filter)
        .order_by("timestamp")
    )

    refill_dates: list[date] = []
    for d in dispenses:
        refill_dates.append(d.timestamp.date())

    # Also get RefillReminder history
    reminder_filter = {"contact": contact, "active": False}
    if product_id:
        reminder_filter["product_id"] = product_id
    reminders = RefillReminder.objects.filter(**reminder_filter).order_by(
        "next_due_date"
    )
    for r in reminders:
        refill_dates.append(r.next_due_date)

    intervals = _interval_days(refill_dates)

    pattern = classify_refill_pattern(intervals)
    mean_iv = _mean(intervals)

    days_since_last = 0
    if refill_dates:
        last_date = max(refill_dates)
        days_since_last = (today - last_date).days
    else:
        active_filter = {"contact": contact, "active": True, "next_due_date__lte": today}
        if product_id:
            active_filter["product_id"] = product_id
        active_reminder = RefillReminder.objects.filter(**active_filter).first()
        if active_reminder:
            days_since_last = (today - active_reminder.next_due_date).days

    overdue = days_overdue(mean_iv if mean_iv > 0 else 30, days_since_last)
    score = adherence_score_from_intervals(intervals)

    if pattern == "new" and len(refill_dates) > 0:
        score = 50.0

    return {
        "pattern": pattern,
        "adherence_score": round(score, 1),
        "days_overdue_risk": overdue,
    }


def score_all_patient_adherence() -> list[dict]:
    """Run adherence scoring for all patients and persist results."""
    from apps.crm.models import Contact
    from apps.intelligence.models import (
        ModelVersion,
        PatientAdherenceScore,
        PredictionLog,
    )

    model_version, _ = ModelVersion.objects.get_or_create(
        model_type="adherence",
        version="3.0.0",
        defaults={
            "is_active": True,
            "parameters": {"method": "refill_interval_analysis"},
        },
    )
    ModelVersion.objects.filter(
        model_type="adherence", is_active=True
    ).exclude(pk=model_version.pk).update(is_active=False)

    results: list[dict] = []
    for contact in Contact.objects.filter(contact_type="PATIENT"):
        # For now score per-patient, using a generic product reference.
        # In production this would iterate over each product the patient takes.
        assessment = score_patient_adherence(str(contact.id))

        # Find a default product for this patient from RefillReminder
        from apps.crm.models import RefillReminder
        default_product = (
            RefillReminder.objects.filter(contact=contact, active=True)
            .select_related("product")
            .first()
        )

        if default_product:
            product = default_product.product
        else:
            # Fallback: use first product in catalog
            from apps.catalog.models import Product
            product = Product.objects.first()

        if product is None:
            continue

        PatientAdherenceScore.objects.create(
            contact=contact,
            product=product,
            adherence_score=assessment["adherence_score"],
            days_overdue_risk=assessment["days_overdue_risk"],
            pattern=assessment["pattern"],
        )

        PredictionLog.objects.create(
            model_version=model_version,
            subject_type="patient",
            subject_id=str(contact.id),
            prediction=assessment,
        )

        assessment["contact_id"] = str(contact.id)
        assessment["patient_name"] = str(contact)
        assessment["product_id"] = str(product.id)
        results.append(assessment)

    return results
