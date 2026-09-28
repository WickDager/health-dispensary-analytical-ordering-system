from __future__ import annotations

from rest_framework import filters, viewsets, status

try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    DjangoFilterBackend = None
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.lots.models import Lot
from apps.lots.serializers import (
    LotSerializer,
    DispenseRequestSerializer,
    FEFOSuggestionSerializer,
)
from apps.lots.services import dispense_fefo, get_fefo_suggestion, InsufficientStock


class LotViewSet(viewsets.ModelViewSet):
    queryset = Lot.objects.select_related("product").all()
    serializer_class = LotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ["product", "is_locked"]
    search_fields = ["batch_number", "product__name"]
    ordering_fields = ["expiry_date", "quantity", "created_at"]
    ordering = ["expiry_date"]

    def get_permissions(self):
        """Allow read-only for all authenticated users; mutations require ADMIN."""
        if self.action not in ("list", "retrieve", "fefo_suggestion"):
            from apps.catalog.views import IsAdminOrReadOnly
            return [IsAdminOrReadOnly()]
        return super().get_permissions()

    @action(detail=False, methods=["post"])
    def dispense(self, request):
        """POST /api/lots/lots/dispense/ — dispense using FEFO logic."""
        serializer = DispenseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            result = dispense_fefo(
                product_id=str(data["product_id"]),
                quantity=data["quantity"],
                mrn=data["mrn"],
                user=request.user,
            )
            return Response(result, status=status.HTTP_200_OK)
        except InsufficientStock as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def fefo_suggestion(self, request):
        """GET /api/lots/lots/fefo_suggestion/?product_id=<uuid> — preview FEFO order."""
        serializer = FEFOSuggestionSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        product_id = str(serializer.validated_data["product_id"])
        suggestion = get_fefo_suggestion(product_id)
        return Response({"lots": suggestion})
