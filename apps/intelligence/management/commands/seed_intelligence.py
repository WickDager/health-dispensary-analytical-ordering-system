"""
Management command to seed intelligence data: document templates and initial model versions.

Usage:
    python manage.py seed_intelligence
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.intelligence.services.document_ingestion import seed_document_templates
from apps.intelligence.models import AIModuleConfig, ModelVersion
from apps.llm.models import LLMProviderConfig


class Command(BaseCommand):
    help = "Seed intelligence data: document templates and initial model versions"

    def handle(self, *args, **options):
        # -----------------------------------------------------------------
        # 1. Document templates
        # -----------------------------------------------------------------
        created = seed_document_templates()
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created {created} document template(s).")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Document templates already exist — nothing to seed.")
            )

        # -----------------------------------------------------------------
        # 2. Initial model versions
        # -----------------------------------------------------------------
        for model_type, display_name in ModelVersion.MODEL_TYPES:
            mv, was_created = ModelVersion.objects.get_or_create(
                model_type=model_type,
                is_active=True,
                defaults={
                    "version": "1.0.0",
                    "accuracy_score": None,
                    "last_trained_at": None,
                    "parameters": {},
                },
            )
            if was_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created ModelVersion: {display_name} v{mv.version}"
                    )
                )
            else:
                self.stdout.write(
                    f"ModelVersion for '{display_name}' already exists — skipped."
                )

        # -----------------------------------------------------------------
        # 3. Default AI module configs (for the settings/ai page)
        # -----------------------------------------------------------------
        DEFAULT_MODULES = [
            ("demand_forecasting", "Demand Forecasting", "Predict future inventory needs based on historical dispense data", True, 0.7),
            ("supplier_scoring", "Supplier Scoring", "Rate suppliers on delivery performance, reliability, and pricing", True, 0.65),
            ("expiry_risk", "Expiry Risk", "Identify inventory items at risk of expiring before use", True, 0.6),
            ("adherence_prediction", "Adherence Prediction", "Predict patient medication adherence patterns", False, 0.7),
            ("anomaly_detection", "Anomaly Detection", "Detect unusual patterns in orders, dispense, and inventory", True, 0.75),
            ("llm_insights", "LLM Insights", "AI-generated analysis and natural language explanations", True, 0.5),
            ("document_ingestion", "Document Ingestion", "Extract structured data from PDFs, images, and scanned documents", True, 0.55),
        ]
        for key, label, desc, enabled, threshold in DEFAULT_MODULES:
            cfg, was_created = AIModuleConfig.objects.get_or_create(
                key=key,
                defaults={
                    "label": label,
                    "description": desc,
                    "enabled": enabled,
                    "confidence_threshold": threshold,
                },
            )
            if was_created:
                self.stdout.write(self.style.SUCCESS(f"Created AIModuleConfig: {label}"))

        # -----------------------------------------------------------------
        # 4. Default LLM provider configs (for the Settings > Providers page)
        # -----------------------------------------------------------------
        DEFAULT_PROVIDERS = [
            ("gemini", "Gemini 3 Flash", "https://generativelanguage.googleapis.com/v1beta/openai/", 1),
            ("claude", "claude-sonnet-5-20251001", "", 2),
            ("openai", "gpt-4o", "", 3),
            ("deepseek", "deepseek-chat", "https://api.deepseek.com/v1", 4),
            ("openrouter", "auto", "https://openrouter.ai/api/v1", 5),
        ]
        for name, model, base_url, priority in DEFAULT_PROVIDERS:
            prov, was_created = LLMProviderConfig.objects.get_or_create(
                name=name,
                defaults={
                    "model": model,
                    "base_url": base_url or None,
                    "fallback_priority": priority,
                    "enabled": False,
                    "is_default": name == "gemini",
                },
            )
            if was_created:
                self.stdout.write(self.style.SUCCESS(f"Created LLMProviderConfig: {name}"))

        self.stdout.write(self.style.SUCCESS("\nIntelligence data seeded successfully."))
