"""Statistical anomaly detection -- pure Python/SciPy, no sklearn.

Methods:
- IQR (Inter-Quartile Range) detection
- Modified Z-score detection (MAD-based, robust to outliers)
- Full pipeline: scan products, suppliers, orders for anomalies
"""
from __future__ import annotations
from datetime import date, timedelta
import math


def detect_anomalies_iqr(
    values: list[float], multiplier: float = 1.5
) -> list[int]:
    """Returns indices of anomalous values using IQR method."""
    if len(values) < 4:
        return []

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    q1_idx = n // 4
    q3_idx = 3 * n // 4
    q1 = sorted_vals[q1_idx]
    q3 = sorted_vals[q3_idx]

    iqr = q3 - q1
    if iqr == 0:
        return []

    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    return [i for i, v in enumerate(values) if v < lower or v > upper]


def detect_anomalies_zscore(
    values: list[float], threshold: float = 3.0
) -> list[int]:
    """Returns indices of anomalous values using Z-score method."""
    if len(values) < 3:
        return []

    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)

    if std == 0:
        return []

    return [i for i, v in enumerate(values) if abs((v - mean) / std) > threshold]


def detect_anomalies_modified_zscore(
    values: list[float], threshold: float = 3.5
) -> list[int]:
    """Returns indices of anomalous values using Modified Z-score (MAD-based)."""
    if len(values) < 4:
        return []

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    if n % 2 == 1:
        median = sorted_vals[n // 2]
    else:
        median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    abs_deviations = sorted([abs(v - median) for v in values])
    if n % 2 == 1:
        mad = abs_deviations[n // 2]
    else:
        mad = (abs_deviations[n // 2 - 1] + abs_deviations[n // 2]) / 2.0

    if mad == 0:
        return []

    anomalous = []
    for i, v in enumerate(values):
        modified_z = 0.6745 * (v - median) / mad
        if abs(modified_z) > threshold:
            anomalous.append(i)

    return anomalous


def detect_anomalies(
    values: list[float],
    method: str = "iqr",
    multiplier: float = 1.5,
) -> dict:
    """Unified anomaly detection interface.

    Returns dict with indices, lower_bound, upper_bound, method.
    """
    if method == "iqr":
        indices = detect_anomalies_iqr(values, multiplier)

        if len(values) >= 4:
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            q1 = sorted_vals[n // 4]
            q3 = sorted_vals[3 * n // 4]
            iqr = q3 - q1
            lower = q1 - multiplier * iqr
            upper = q3 + multiplier * iqr
        else:
            lower = upper = 0.0

    elif method == "modified_zscore":
        indices = detect_anomalies_modified_zscore(values, multiplier)

        if len(values) >= 4:
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            if n % 2 == 1:
                median = sorted_vals[n // 2]
            else:
                median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

            abs_deviations = sorted([abs(v - median) for v in values])
            if n % 2 == 1:
                mad = abs_deviations[n // 2]
            else:
                mad = (abs_deviations[n // 2 - 1] + abs_deviations[n // 2]) / 2.0

            if mad > 0:
                lower = median - (multiplier / 0.6745) * mad
                upper = median + (multiplier / 0.6745) * mad
            else:
                lower = upper = median
        else:
            lower = upper = 0.0

    else:  # zscore
        indices = detect_anomalies_zscore(values, multiplier)

        if len(values) >= 3:
            n = len(values)
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            std = math.sqrt(variance)
            lower = mean - multiplier * std
            upper = mean + multiplier * std
        else:
            lower = upper = 0.0

    return {
        "indices": indices,
        "lower_bound": round(lower, 4),
        "upper_bound": round(upper, 4),
        "method": method,
        "anomaly_count": len(indices),
        "total_values": len(values),
    }


def _anomaly_type_for_dimension(dimension: str) -> str:
    """Map a dimension name to the AnomalyAlert.anomaly_type choices."""
    mapping = {
        "daily_consumption": "unusual_dispense",
        "order_quantity": "unusual_order",
        "unit_cost": "price_spike",
        "stock_level": "stock_discrepancy",
    }
    return mapping.get(dimension, "unusual_velocity")


def _severity_from_distance(
    value: float, lower: float, upper: float
) -> str:
    """Classify severity based on distance from bounds."""
    if lower == upper:
        return "medium"
    span = upper - lower if upper > lower else 1.0
    if value > upper:
        distance = (value - upper) / span
    else:
        distance = (lower - value) / span
    if distance > 3:
        return "critical"
    elif distance > 2:
        return "high"
    elif distance > 1:
        return "medium"
    return "low"


def _scan_product_consumption(product_id: str) -> list[dict]:
    """Detect anomalies in daily consumption for a product."""
    from apps.audit.models import AuditLog

    today = date.today()
    dispenses = (
        AuditLog.objects.filter(
            action="DISPENSE",
            details__product_id=product_id,
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
    if len(values) < 5:
        return []

    result = detect_anomalies(values, method="iqr", multiplier=1.5)
    alerts: list[dict] = []
    for idx in result["indices"]:
        anom_type = _anomaly_type_for_dimension("daily_consumption")
        severity = _severity_from_distance(
            values[idx], result["lower_bound"], result["upper_bound"]
        )
        alerts.append({
            "anomaly_type": anom_type,
            "severity": severity,
            "subject_type": "product",
            "subject_id": product_id,
            "title": f"Unusual dispense for product {product_id}",
            "description": (
                f"Daily consumption of {values[idx]:.1f} units is outside expected "
                f"range [{result['lower_bound']:.1f}, {result['upper_bound']:.1f}] "
                f"(method: {result['method']})."
            ),
            "data_snapshot": {
                "observed_value": values[idx],
                "expected_range_low": result["lower_bound"],
                "expected_range_high": result["upper_bound"],
                "method": result["method"],
                "total_values": result["total_values"],
            },
        })
    return alerts


def _scan_supplier_costs(supplier_id: str) -> list[dict]:
    """Detect anomalies in unit costs from a supplier."""
    from apps.orders.models import OrderItem

    today = date.today()
    window = today - timedelta(days=180)

    items = OrderItem.objects.filter(
        order__supplier_id=supplier_id,
        order__order_date__gte=window,
    ).values_list("unit_cost", flat=True)

    values = list(items)
    if len(values) < 5:
        return []

    result = detect_anomalies(values, method="modified_zscore", multiplier=3.5)
    alerts: list[dict] = []
    for idx in result["indices"]:
        anom_type = _anomaly_type_for_dimension("unit_cost")
        severity = _severity_from_distance(
            values[idx], result["lower_bound"], result["upper_bound"]
        )
        alerts.append({
            "anomaly_type": anom_type,
            "severity": severity,
            "subject_type": "supplier",
            "subject_id": supplier_id,
            "title": f"Price spike from supplier {supplier_id}",
            "description": (
                f"Unit cost of {values[idx]:.2f} is outside expected "
                f"range [{result['lower_bound']:.2f}, {result['upper_bound']:.2f}] "
                f"(method: {result['method']})."
            ),
            "data_snapshot": {
                "observed_value": values[idx],
                "expected_range_low": result["lower_bound"],
                "expected_range_high": result["upper_bound"],
                "method": result["method"],
                "total_values": result["total_values"],
            },
        })
    return alerts


def _scan_order_quantities() -> list[dict]:
    """Detect anomalies in order-item quantities across all products."""
    from apps.orders.models import OrderItem

    today = date.today()
    window = today - timedelta(days=90)

    items = OrderItem.objects.filter(order__order_date__gte=window)

    by_product: dict[str, list[float]] = {}
    by_product_obj: dict[str, object] = {}
    for item in items.select_related("product"):
        pid = str(item.product_id)
        by_product.setdefault(pid, []).append(float(item.quantity))
        by_product_obj[pid] = item.product

    alerts: list[dict] = []
    for pid, quantities in by_product.items():
        if len(quantities) < 5:
            continue

        result = detect_anomalies(quantities, method="iqr", multiplier=1.5)
        product = by_product_obj.get(pid)
        product_name = product.name if product else "Unknown"

        for idx in result["indices"]:
            anom_type = _anomaly_type_for_dimension("order_quantity")
            severity = _severity_from_distance(
                quantities[idx], result["lower_bound"], result["upper_bound"]
            )
            alerts.append({
                "anomaly_type": anom_type,
                "severity": severity,
                "subject_type": "product",
                "subject_id": pid,
                "title": f"Unusual order quantity for {product_name}",
                "description": (
                    f"Order quantity of {quantities[idx]:.0f} for {product_name} "
                    f"is outside expected range [{result['lower_bound']:.0f}, "
                    f"{result['upper_bound']:.0f}] (method: {result['method']})."
                ),
                "data_snapshot": {
                    "observed_value": quantities[idx],
                    "expected_range_low": result["lower_bound"],
                    "expected_range_high": result["upper_bound"],
                    "method": result["method"],
                    "total_values": result["total_values"],
                    "product_name": product_name,
                },
            })

    return alerts


def detect_all_anomalies() -> list[dict]:
    """Run anomaly detection across all dimensions and persist alerts."""
    from apps.catalog.models import Product, Supplier
    from apps.intelligence.models import AnomalyAlert

    all_alerts: list[dict] = []

    # Scan consumption per product
    for product in Product.objects.all():
        pid = str(product.id)
        alerts = _scan_product_consumption(pid)
        for alert in alerts:
            obj = AnomalyAlert.objects.create(
                anomaly_type=alert["anomaly_type"],
                severity=alert["severity"],
                subject_type=alert["subject_type"],
                subject_id=alert["subject_id"],
                title=alert["title"],
                description=alert["description"],
                data_snapshot=alert["data_snapshot"],
            )
            alert["alert_id"] = str(obj.id)
        all_alerts.extend(alerts)

    # Scan supplier costs
    for supplier in Supplier.objects.all():
        sid = str(supplier.id)
        alerts = _scan_supplier_costs(sid)
        for alert in alerts:
            obj = AnomalyAlert.objects.create(
                anomaly_type=alert["anomaly_type"],
                severity=alert["severity"],
                subject_type=alert["subject_type"],
                subject_id=alert["subject_id"],
                title=alert["title"],
                description=alert["description"],
                data_snapshot=alert["data_snapshot"],
            )
            alert["alert_id"] = str(obj.id)
        all_alerts.extend(alerts)

    # Scan order quantities
    order_alerts = _scan_order_quantities()
    for alert in order_alerts:
        obj = AnomalyAlert.objects.create(
            anomaly_type=alert["anomaly_type"],
            severity=alert["severity"],
            subject_type=alert["subject_type"],
            subject_id=alert["subject_id"],
            title=alert["title"],
            description=alert["description"],
            data_snapshot=alert["data_snapshot"],
        )
        alert["alert_id"] = str(obj.id)
    all_alerts.extend(order_alerts)

    return all_alerts
