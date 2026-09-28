from datetime import date, timedelta

from django.db.models import F, Sum
from rest_framework import status, viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response

try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    DjangoFilterBackend = None

from apps.catalog.models import Product, Supplier
from apps.catalog.serializers import ProductSerializer, SupplierSerializer


class IsAdminOrReadOnly(IsAuthenticated):
    """Allow read-only access to authenticated users; mutations require ADMIN role."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == "ADMIN"


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().prefetch_related("products")
    serializer_class = SupplierSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    search_fields = ["name", "contact_email"]
    ordering_fields = ["name", "rating", "lead_time", "created_at"]
    ordering = ["name"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = (
        Product.objects
        .select_related("supplier")
        .prefetch_related("lots")
        .all()
    )
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ["api", "supplier"]
    search_fields = ["name", "api", "strength"]
    ordering_fields = ["name", "soh", "unit_cost", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        stock_status = self.request.query_params.get("stock_status")
        if stock_status:
            if stock_status == "STOCKOUT":
                qs = qs.filter(soh__lte=0)
            elif stock_status == "CRITICAL":
                qs = qs.filter(soh__gt=0, soh__lte=F("min_stock"))
            elif stock_status == "LOW":
                qs = qs.filter(soh__gt=F("min_stock"), soh__lte=F("reorder_point"))
            elif stock_status == "HEALTHY":
                qs = qs.filter(soh__gt=F("reorder_point"))
        return qs

    def destroy(self, request, *args, **kwargs):
        """Delete a product, guarding the Lot.product PROTECT constraint.

        Without this, deleting a product that still has stock lots raises a
        database ProtectedError and surfaces as an opaque 500; the client
        gets a clear 409 instead.
        """
        from django.db.models import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "Product has stock lots or orders and cannot be "
                          "deleted. Remove or transfer its lots first."},
                status=status.HTTP_409_CONFLICT,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Aggregated stats for the dashboard."""
    from apps.lots.models import Lot
    from apps.approvals.models import ApprovalRequest
    from apps.crm.models import Contact, Opportunity

    products = Product.objects.all()
    today = date.today()

    pipeline_value = (
        Opportunity.objects.filter(
            stage__in=["QUALIFICATION", "PROPOSAL", "NEGOTIATION"]
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    return Response({
        "total_products": products.count(),
        "healthy_products": products.filter(soh__gt=F("reorder_point")).count(),
        "low_stock_products": products.filter(
            soh__gt=F("min_stock"), soh__lte=F("reorder_point")
        ).count(),
        "critical_stock_products": products.filter(
            soh__gt=0, soh__lte=F("min_stock")
        ).count(),
        "stockout_products": products.filter(soh__lte=0).count(),
        "expiring_30d": Lot.objects.filter(
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gt=today,
            is_locked=False,
        ).count(),
        "expiring_60d": Lot.objects.filter(
            expiry_date__lte=today + timedelta(days=60),
            expiry_date__gt=today + timedelta(days=30),
            is_locked=False,
        ).count(),
        "expiring_90d": Lot.objects.filter(
            expiry_date__lte=today + timedelta(days=90),
            expiry_date__gt=today + timedelta(days=60),
            is_locked=False,
        ).count(),
        "pending_approvals": ApprovalRequest.objects.filter(status="PENDING").count(),
        "total_contacts": Contact.objects.count(),
        "pipeline_value": float(pipeline_value),
    })
