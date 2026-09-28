from __future__ import annotations

from django.db.models import F
from rest_framework import filters, viewsets, status

try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    DjangoFilterBackend = None
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.orders.models import Order, OrderStatus
from apps.orders.serializers import (
    OrderSerializer,
    ProcurementSuggestionSerializer,
)
from apps.catalog.models import Product, Supplier
from apps.approvals.models import ApprovalRequest


class OrderViewSet(viewsets.ModelViewSet):
    queryset = (
        Order.objects
        .select_related("supplier")
        .prefetch_related("items__product")
        .all()
        .order_by("-order_date")
    )
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ["supplier", "status"]
    search_fields = ["supplier__name"]
    ordering_fields = ["order_date", "total_cost", "status"]
    ordering = ["-order_date"]

    def get_permissions(self):
        if self.action not in ("list", "retrieve", "procurement_suggestions", "submit"):
            from apps.catalog.views import IsAdminOrReadOnly
            return [IsAdminOrReadOnly()]
        return super().get_permissions()

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """
        POST /api/orders/orders/{pk}/submit/ — stage an ORDER_SUBMIT approval.
        The order is NOT sent until an admin approves.
        """
        order = self.get_object()
        if order.status != OrderStatus.PENDING:
            return Response(
                {"error": f"Order is {order.status}, only PENDING orders can be submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approval = ApprovalRequest.objects.create(
            action_type="ORDER_SUBMIT",
            payload={"order_id": str(order.id)},
            requested_by=request.user,
        )

        return Response(
            {
                "message": "Order submitted for approval.",
                "approval_id": str(approval.id),
                "order_id": str(order.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def procurement_suggestions(request):
    """
    GET /api/orders/procurement-suggestions/?supplier_id=<uuid>&min_stock_only=true

    Returns products whose SOH is below their reorder point (or min_stock),
    grouped by supplier, with recommended order quantities.
    """
    serializer = ProcurementSuggestionSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    threshold_field = "min_stock" if data["min_stock_only"] else "reorder_point"

    products = Product.objects.select_related("supplier").filter(
        soh__lte=F(threshold_field)
    )

    if data.get("supplier_id"):
        products = products.filter(supplier_id=data["supplier_id"])

    # Group by supplier
    supplier_map: dict = {}
    for product in products.order_by("supplier__name", "name"):
        if not product.supplier:
            continue
        sid = str(product.supplier.id)
        if sid not in supplier_map:
            supplier_map[sid] = {
                "supplier_id": sid,
                "supplier_name": product.supplier.name,
                "items": [],
                "estimated_total": 0.0,
            }

        deficit = product.max_stock - product.soh
        if deficit <= 0:
            deficit = product.reorder_point

        item = {
            "product_id": str(product.id),
            "product_name": product.name,
            "api": product.api,
            "strength": product.strength,
            "current_soh": product.soh,
            "min_stock": product.min_stock,
            "reorder_point": product.reorder_point,
            "max_stock": product.max_stock,
            "recommended_qty": deficit,
            "unit_cost": product.unit_cost,
            "line_total": round(deficit * product.unit_cost, 2),
        }
        supplier_map[sid]["items"].append(item)
        supplier_map[sid]["estimated_total"] = round(
            supplier_map[sid]["estimated_total"] + item["line_total"], 2
        )

    return Response(list(supplier_map.values()))
