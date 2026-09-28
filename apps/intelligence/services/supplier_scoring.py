"""Supplier scoring engine -- statistical, no sklearn.

Scores every supplier on 4 dimensions (cost, reliability, quality, speed)
using order history and pure statistical calculations.
"""
from __future__ import annotations
from datetime import date, timedelta
import math


def _score_cost(supplier_id: str, orders) -> float:
    """Cost score: how competitive are unit prices vs. other suppliers? 0-100."""
    from apps.orders.models import OrderItem

    window = date.today() - timedelta(days=180)

    own_costs: dict[str, list[float]] = {}
    for order in orders:
        for item in order.items.all():
            pid = str(item.product_id)
            own_costs.setdefault(pid, []).append(item.unit_cost)

    if not own_costs:
        return 50.0

    ratios: list[float] = []
    for pid, costs in own_costs.items():
        avg_own = sum(costs) / len(costs)

        all_items = OrderItem.objects.filter(
            product_id=pid,
            order__order_date__gte=window,
        )
        min_cost = (
            all_items.order_by("unit_cost")
            .values_list("unit_cost", flat=True)
            .first()
        )
        if min_cost is None or min_cost <= 0:
            ratios.append(1.0)
            continue

        ratios.append(min_cost / avg_own if avg_own > 0 else 0.5)

    if not ratios:
        return 50.0

    raw = sum(ratios) / len(ratios) * 100
    return max(0.0, min(100.0, raw))


def _score_reliability(supplier_id: str, orders) -> float:
    """Reliability score: on-time delivery rate. 0-100."""
    if not orders:
        return 0.0

    completed = [o for o in orders if o.status == "COMPLETED"]
    if not completed:
        return 50.0

    on_time = 0
    late = 0
    for order in completed:
        if order.expected_delivery is None:
            continue
        if order.order_date.date() <= order.expected_delivery.date():
            on_time += 1
        else:
            late += 1

    total = on_time + late
    if total == 0:
        return 50.0
    return (on_time / total) * 100.0


def _score_quality(supplier_id: str, orders) -> float:
    """Quality score: consistency of unit costs. 0-100."""
    costs_by_product: dict[str, list[float]] = {}
    for order in orders:
        for item in order.items.all():
            pid = str(item.product_id)
            costs_by_product.setdefault(pid, []).append(item.unit_cost)

    if not costs_by_product:
        return 50.0

    cvs: list[float] = []
    for costs in costs_by_product.values():
        if len(costs) < 2:
            cvs.append(0.0)
            continue
        mean = sum(costs) / len(costs)
        if mean == 0:
            cvs.append(0.0)
            continue
        variance = sum((c - mean) ** 2 for c in costs) / len(costs)
        cv = math.sqrt(variance) / mean
        cvs.append(cv)

    avg_cv = sum(cvs) / len(cvs) if cvs else 0.0
    quality = max(0.0, 100.0 - avg_cv * 100.0)
    return max(0.0, min(100.0, quality))


def _score_speed(supplier_id: str, orders) -> float:
    """Speed score: lead time vs. promised lead time. 0-100."""
    from apps.catalog.models import Supplier

    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return 0.0

    promised_lead = supplier.lead_time or 3

    completed = [o for o in orders if o.status == "COMPLETED"]
    if not completed:
        return 50.0

    ratios: list[float] = []
    for order in completed:
        actual_lead = (date.today() - order.order_date.date()).days
        actual_lead = max(1, actual_lead)
        if actual_lead <= 0:
            ratios.append(1.0)
            continue
        ratio = promised_lead / actual_lead
        ratios.append(ratio)

    if not ratios:
        return 50.0

    avg_ratio = sum(ratios) / len(ratios)
    speed = avg_ratio * 50.0
    return max(0.0, min(100.0, speed))


def _score_trend(supplier_id: str, orders) -> str:
    """Determine if aggregate scores are improving, declining, or stable."""
    from apps.orders.models import Order

    today = date.today()
    recent_cutoff = today - timedelta(days=30)
    prior_start = today - timedelta(days=60)

    recent = [o for o in orders if o.order_date.date() >= recent_cutoff]
    prior_query = Order.objects.filter(
        supplier_id=supplier_id,
        order_date__gte=prior_start,
        order_date__lt=recent_cutoff,
    )
    prior = list(prior_query)

    def completion_rate(orders_list):
        comp = [o for o in orders_list if o.status == "COMPLETED"]
        if not orders_list:
            return 0.0
        return len(comp) / len(orders_list)

    recent_rate = completion_rate(recent)
    prior_rate = completion_rate(prior)

    if prior_rate == 0:
        return "stable"

    delta = recent_rate - prior_rate
    if delta > 0.1:
        return "improving"
    elif delta < -0.1:
        return "declining"
    return "stable"


def score_supplier(supplier_id: str) -> dict:
    """Calculate a 0-100 composite score for a supplier across 4 dimensions."""
    from apps.orders.models import Order

    today = date.today()
    window = today - timedelta(days=180)

    orders = list(
        Order.objects.filter(
            supplier_id=supplier_id,
            order_date__gte=window,
        ).prefetch_related("items")
    )

    if not orders:
        return {
            "overall_score": 0,
            "cost_score": 0,
            "reliability_score": 0,
            "quality_score": 0,
            "speed_score": 0,
            "trend": "stable",
            "order_count": 0,
        }

    cost = _score_cost(supplier_id, orders)
    reliability = _score_reliability(supplier_id, orders)
    quality = _score_quality(supplier_id, orders)
    speed = _score_speed(supplier_id, orders)

    # Weighted composite: cost 25%, reliability 30%, quality 20%, speed 25%
    overall = (
        0.25 * cost + 0.30 * reliability + 0.20 * quality + 0.25 * speed
    )

    trend = _score_trend(supplier_id, orders)

    return {
        "overall_score": round(overall, 1),
        "cost_score": round(cost, 1),
        "reliability_score": round(reliability, 1),
        "quality_score": round(quality, 1),
        "speed_score": round(speed, 1),
        "trend": trend,
        "order_count": len(orders),
    }


def score_all_suppliers() -> list[dict]:
    """Run scoring for every supplier and persist results."""
    from apps.catalog.models import Supplier
    from apps.intelligence.models import (
        ModelVersion,
        PredictionLog,
        SupplierScore,
    )

    model_version, _ = ModelVersion.objects.get_or_create(
        model_type="supplier_scoring",
        version="3.0.0",
        defaults={
            "is_active": True,
            "parameters": {"weights": {"cost": 0.25, "reliability": 0.30, "quality": 0.20, "speed": 0.25}},
        },
    )
    ModelVersion.objects.filter(
        model_type="supplier_scoring", is_active=True
    ).exclude(pk=model_version.pk).update(is_active=False)

    results: list[dict] = []
    for supplier in Supplier.objects.all():
        scores = score_supplier(str(supplier.id))

        SupplierScore.objects.create(
            supplier=supplier,
            overall_score=scores["overall_score"],
            cost_score=scores["cost_score"],
            reliability_score=scores["reliability_score"],
            quality_score=scores["quality_score"],
            speed_score=scores["speed_score"],
            trend=scores["trend"],
            analysis_json={
                "weights": {"cost": 0.25, "reliability": 0.30, "quality": 0.20, "speed": 0.25},
                "order_count": scores["order_count"],
            },
        )

        PredictionLog.objects.create(
            model_version=model_version,
            subject_type="supplier",
            subject_id=str(supplier.id),
            prediction=scores,
            confidence=None,
        )

        scores["supplier_id"] = str(supplier.id)
        results.append(scores)

    return results
