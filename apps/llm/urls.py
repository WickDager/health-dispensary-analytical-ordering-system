from rest_framework.routers import DefaultRouter

from apps.llm.views import LLMProviderViewSet

app_name = "llm"

router = DefaultRouter()
router.register(r"providers", LLMProviderViewSet, basename="llm-provider")

urlpatterns = router.urls
