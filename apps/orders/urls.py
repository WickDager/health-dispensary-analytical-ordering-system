from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.orders.views import OrderViewSet, procurement_suggestions

app_name = "orders"

router = DefaultRouter()
router.register(r"", OrderViewSet, basename="order")

urlpatterns = [
    path(
        "procurement-suggestions/",
        procurement_suggestions,
        name="procurement-suggestions",
    ),
] + router.urls
