"""LLM-powered insights using the existing multi-provider gateway."""
from __future__ import annotations

import json
import logging

from django.db import models

from apps.llm.gateway import get_provider_chain, decrypt_key
from apps.llm.adapters import ADAPTER_REGISTRY

logger = logging.getLogger("hdaos.intelligence.llm")


def _call_llm(prompt: str, system: str = "You are a pharmacy supply chain AI analyst.") -> str:
    """Call the best available LLM with a prompt. Returns text response."""
    chain = get_provider_chain()
    last_error = None
    for provider in chain:
        adapter_cls = ADAPTER_REGISTRY.get(provider.name)
        if not adapter_cls:
            continue
        try:
            api_key = decrypt_key(provider)
            if not api_key:
                last_error = f"No API key for {provider.name}"
                continue

            # Use direct SDK calls for general chat completion
            if provider.name == "gemini":
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(provider.model)
                response = model.generate_content(f"{system}\n\n{prompt}")
                return response.text

            elif provider.name == "claude":
                import anthropic

                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=provider.model,
                    max_tokens=1024,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text

            else:
                from openai import OpenAI

                client_kwargs = {"api_key": api_key}
                if provider.base_url:
                    client_kwargs["base_url"] = provider.base_url
                client = OpenAI(**client_kwargs)
                response = client.chat.completions.create(
                    model=provider.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content

        except Exception as e:
            last_error = str(e)
            logger.warning("LLM provider %s failed: %s", provider.name, e)
            continue

    raise RuntimeError(f"All LLM providers failed. Last: {last_error}")


def generate_supplier_comparison(supplier_ids: list[str]) -> dict:
    """LLM generates a narrative comparison of suppliers with recommendations."""
    from apps.catalog.models import Supplier
    from apps.intelligence.models import SupplierScore

    suppliers = Supplier.objects.filter(id__in=supplier_ids)
    context = []
    for s in suppliers:
        score = SupplierScore.objects.filter(supplier=s).first()
        context.append({
            "name": s.name,
            "lead_time": s.lead_time if hasattr(s, "lead_time") else None,
            "rating": s.rating if hasattr(s, "rating") else None,
            "min_order": s.min_order_value if hasattr(s, "min_order_value") else None,
            "scores": {
                "overall": score.overall_score if score else None,
                "cost": score.cost_score if score else None,
                "reliability": score.reliability_score if score else None,
                "speed": score.speed_score if score else None,
            } if score else None,
        })

    prompt = f"""Analyze these pharmaceutical suppliers and recommend which to use:

Suppliers:
{json.dumps(context, indent=2)}

Provide:
1. Which supplier is best for cost-sensitive orders
2. Which supplier is most reliable
3. Which supplier is fastest
4. Overall ranking from best to worst
5. Any risks or concerns

Respond as JSON:
{{"best_cost": "name", "best_reliability": "name", "best_speed": "name", "ranking": ["name1", "name2", ...], "risks": ["risk1", "risk2"], "recommendation": "summary paragraph"}}"""

    try:
        result = _call_llm(prompt)
        # Extract JSON from response
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result.strip())
    except Exception as exc:
        logger.exception("supplier_comparison failed")
        return {"error": "LLM analysis failed", "raw_scores": context}


def explain_anomaly(anomaly_id: str) -> str:
    """LLM explains why an anomaly was detected in plain English."""
    from apps.intelligence.models import AnomalyAlert

    anomaly = AnomalyAlert.objects.get(pk=anomaly_id)

    prompt = f"""An anomaly was detected in the pharmacy inventory system:

Type: {anomaly.get_anomaly_type_display()}
Severity: {anomaly.severity}
Title: {anomaly.title}
Data: {json.dumps(anomaly.data_snapshot, indent=2)}

Explain in 2-3 sentences:
1. What likely caused this anomaly
2. What action the pharmacy manager should take
Keep it practical and actionable."""

    try:
        return _call_llm(prompt, system="You are a pharmacy operations expert.")
    except Exception:
        return (
            f"Anomaly: {anomaly.title}. "
            f"Review {anomaly.get_anomaly_type_display()} data for unusual patterns."
        )


def generate_procurement_recommendation() -> dict:
    """LLM analyzes current stock, forecasts, and suppliers to recommend what to order."""
    from apps.catalog.models import Product
    from apps.intelligence.models import DemandForecast

    # Gather context
    products = Product.objects.select_related("supplier").all()[:20]
    forecast_data = {}
    for p in products:
        fc = DemandForecast.objects.filter(product=p).order_by("-forecast_date").first()
        forecast_data[p.name] = {
            "current_stock": p.soh if hasattr(p, "soh") else None,
            "reorder_point": p.reorder_point if hasattr(p, "reorder_point") else None,
            "daily_demand": fc.predicted_quantity if fc else "unknown",
            "supplier": p.supplier.name if p.supplier else "none",
        }

    prompt = f"""Current inventory state and demand forecasts:

{json.dumps(forecast_data, indent=2)}

Recommend:
1. Top 5 products that need reordering most urgently
2. For each, suggested order quantity and supplier
3. Any products at risk of stockout in the next 7 days

Respond as JSON with keys: "urgent_reorders", "at_risk_stockout", "summary" """

    try:
        result = _call_llm(prompt)
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result.strip())
    except Exception as exc:
        logger.exception("procurement_recommendation failed")
        return {
            "error": "LLM analysis failed",
            "note": "Use statistical forecasts as fallback",
        }


def generate_dashboard_summary() -> str:
    """LLM generates a natural language summary of the current state for the dashboard."""
    from datetime import date, timedelta

    from apps.catalog.models import Product
    from apps.lots.models import Lot
    from apps.intelligence.models import AnomalyAlert

    total_products = Product.objects.count()
    low_stock = Product.objects.filter(
        soh__lte=models.F("reorder_point"), soh__gt=0
    ).count()
    stockout = Product.objects.filter(soh__lte=0).count()
    expiring_30d = Lot.objects.filter(
        expiry_date__lte=date.today() + timedelta(days=30), is_locked=False
    ).count()
    anomalies = AnomalyAlert.objects.filter(resolved=False).count()

    prompt = f"""Current pharmacy inventory status:
- {total_products} total products
- {low_stock} products below reorder point
- {stockout} products out of stock
- {expiring_30d} lots expiring within 30 days
- {anomalies} unresolved anomalies

Write a 2-sentence executive summary of the most critical action items."""

    try:
        return _call_llm(prompt)
    except Exception:
        return (
            f"Alert: {stockout} stockouts, {expiring_30d} lots expiring soon. "
            f"Review Anomaly Center for details."
        )
