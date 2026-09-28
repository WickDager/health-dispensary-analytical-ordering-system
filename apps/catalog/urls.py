from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import ProductViewSet, SupplierViewSet, dashboard_summary

app_name = "catalog"

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"suppliers", SupplierViewSet, basename="supplier")

urlpatterns = router.urls + [
    path("dashboard/summary/", dashboard_summary, name="dashboard-summary"),
]
