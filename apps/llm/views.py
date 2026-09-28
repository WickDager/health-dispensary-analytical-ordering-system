from __future__ import annotations

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.llm.models import LLMProviderConfig
from apps.llm.serializers import LLMProviderSerializer, ExtractTestSerializer
from apps.llm.gateway import extract_invoice, decrypt_key, AllProvidersFailed
from apps.llm.adapters import ADAPTER_REGISTRY, BaseLLMAdapter


class LLMProviderViewSet(viewsets.ModelViewSet):
    """
    CRUD for LLM provider configurations.  Admin-only for mutations;
    authenticated users can list/view masked configs.
    """
    queryset = LLMProviderConfig.objects.all()
    serializer_class = LLMProviderSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action not in ("list", "retrieve", "test", "extract"):
            from apps.catalog.views import IsAdminOrReadOnly
            return [IsAdminOrReadOnly()]
        return super().get_permissions()

    @action(detail=False, methods=["post"])
    def test(self, request):
        """
        POST /api/llm/providers/test/ — test a single provider with a short prompt.

        Body: {"text": "invoice text...", "provider": "gemini"}
        """
        serializer = ExtractTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        provider_name = data.get("provider")

        if provider_name:
            try:
                config = LLMProviderConfig.objects.get(name=provider_name, enabled=True)
            except LLMProviderConfig.DoesNotExist:
                return Response(
                    {"error": f"Provider '{provider_name}' not found or disabled."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                api_key = decrypt_key(config)
                adapter_cls = ADAPTER_REGISTRY.get(config.name)
                if adapter_cls is None:
                    return Response(
                        {"error": f"No adapter for provider '{config.name}'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                adapter: BaseLLMAdapter = adapter_cls(
                    api_key=api_key,
                    model=config.model,
                    base_url=config.base_url or None,
                )
                result = adapter.extract_invoice(data["text"])
                return Response(result)
            except Exception as exc:
                return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        else:
            # No specific provider — use the gateway's full chain
            try:
                result = extract_invoice(data["text"])
                return Response(result)
            except AllProvidersFailed as exc:
                return Response(
                    {"error": "All providers failed.", "details": exc.errors},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

    @action(detail=False, methods=["post"], url_path="extract")
    def extract(self, request):
        """
        POST /api/llm/providers/extract/ — extract invoice via full provider chain.

        Body: {"text": "invoice text..."}
        """
        serializer = ExtractTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = extract_invoice(serializer.validated_data["text"])
            return Response(result)
        except AllProvidersFailed as exc:
            return Response(
                {"error": "All providers failed.", "details": exc.errors},
                status=status.HTTP_502_BAD_GATEWAY,
            )
