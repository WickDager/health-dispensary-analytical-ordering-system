from rest_framework.routers import DefaultRouter

from apps.lots.views import LotViewSet

app_name = "lots"

router = DefaultRouter()
router.register(r"", LotViewSet, basename="lot")

urlpatterns = router.urls
