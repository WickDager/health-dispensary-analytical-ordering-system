from __future__ import annotations
from django.db import models

class LLMProviderConfig(models.Model):
    PROVIDERS = [
        ("gemini", "Google Gemini"),
        ("claude", "Anthropic Claude"),
        ("openai", "OpenAI ChatGPT"),
        ("deepseek", "DeepSeek"),
        ("openrouter", "OpenRouter"),
    ]
    name = models.CharField(max_length=16, choices=PROVIDERS, primary_key=True)
    enabled = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    model = models.CharField(max_length=128)
    base_url = models.URLField(null=True, blank=True)
    encrypted_api_key = models.BinaryField(null=True, blank=True)
    fallback_priority = models.PositiveIntegerField(default=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["enabled", "fallback_priority"])]

    def __str__(self):
        return f"{self.get_name_display()} ({'enabled' if self.enabled else 'disabled'})"
