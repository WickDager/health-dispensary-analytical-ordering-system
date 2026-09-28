"""Dynamic reorder-point calculation -- statistical, no sklearn.

Calculates per-product reorder points based on:
- Consumption velocity (from demand_forecasting)
- Supplier lead time
- Safety stock (based on demand variance)
- Service-level target (Z-score for desired fill rate)
"""
from __future__ import annotations
from datetime import date, timedelta
import math


def service_level_z(service_level: float = 0.95) -> float:
    """Z-score for a given service level (probability of no stock-out).

    Uses the Hastings approximation of the normal quantile function.
    Common values: 0.90->1.28, 0.95->1.645, 0.99->2.33
    """
    p = service_level
    if p <= 0.5:
        return 0.0
    if p >= 1.0:
        return 4.0

    p = 1.0 - p if p > 0.5 else p
    t = math.sqrt(-2.0 * math.log(max(p, 1e-10)))
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308
    z = t - (c0 + c1 * t + c2 * t * t) / (
        1.0 + d1 * t + d2 * t * t + d3 * t * t * t
    )
    return -z


def safety_stock(
    daily_demand_std: float,
    lead_time_days: int,
    service_level: float = 0.95,
) -> int:
    """Safety stock = Z * sigma_d * sqrt(lead_time)."""
    if daily_demand_std <= 0 or lead_time_days <= 0:
        return 0
    z = service_level_z(service_level)
    ss = z * daily_demand_std * math.sqrt(lead_time_days)
    return max(0, int(math.ceil(ss)))


def reorder_point(
    avg_daily_demand: float,
    lead_time_days: int,
    safety_stock_units: int = 0,
) -> int:
    """ROP = (avg_daily_demand * lead_time) + safety_stock."""
    if avg_daily_demand <= 0 or lead_time_days <= 0:
        return 0
    demand_during_lead = avg_daily_demand * lead_time_days
    return int(math.ceil(demand_during_lead + safety_stock_units))


def economic_order_quantity(
    annual_demand: float,
    ordering_cost: float = 50.0,
    holding_cost_per_unit: float = 5.0,
) -> int:
    """EOQ = sqrt(2 * D * S / H)."""
    if annual_demand <= 0 or ordering_cost <= 0 or holding_cost_per_unit <= 0:
        return 0
    eoq = math.sqrt(2 * annual_demand * ordering_cost / holding_cost_per_unit)
    return max(1, int(math.ceil(eoq)))


def compute_demand_stats(
    product_id: str, lookback_days: int = 90
) -> tuple[float, float]:
    """Compute mean and std of daily demand for a product.

    Returns (avg_daily_demand, daily_demand_std).
    """
    from apps.audit.models import AuditLog

    today = date.today()
    dispenses = (
        AuditLog.objects.filter(
            action="DISPENSE",
            details__product_id=product_id,
            timestamp__gte=today - timedelta(days=lookback_days),
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
        return 0.0, 0.0

    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0

    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = math.sqrt(variance)
    return mean, std


def calculate_reorder_point(
    product_id: str,
    service_level: float = 0.95,
    ordering_cost: float = 50.0,
    holding_cost_per_unit: float = 5.0,
) -> dict:
    """Calculate the full reorder plan for a single product."""
    from apps.catalog.models import Product

    try:
        product = Product.objects.select_related("supplier").get(id=product_id)
    except Product.DoesNotExist:
        return {
            "avg_daily_demand": 0.0,
            "daily_demand_std": 0.0,
            "lead_time_days": 0,
            "safety_stock": 0,
            "reorder_point": 0,
            "eoq": 0,
            "service_level": service_level,
        }

    lead_time = product.supplier.lead_time if product.supplier else 3
    avg_demand, std_demand = compute_demand_stats(product_id)

    ss = safety_stock(std_demand, lead_time, service_level)
    rop = reorder_point(avg_demand, lead_time, ss)

    annual_demand = avg_demand * 365
    eoq = economic_order_quantity(annual_demand, ordering_cost, holding_cost_per_unit)

    # Update the product's reorder_point field if meaningful
    if rop > 0 and rop != product.reorder_point:
        product.reorder_point = max(product.min_stock, rop)
        product.save(update_fields=["reorder_point"])

    return {
        "avg_daily_demand": round(avg_demand, 3),
        "daily_demand_std": round(std_demand, 3),
        "lead_time_days": lead_time,
        "safety_stock": ss,
        "reorder_point": rop,
        "eoq": eoq,
        "service_level": service_level,
    }
