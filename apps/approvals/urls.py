from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.approvals.views import ApprovalViewSet

app_name = "approvals"

router = DefaultRouter()
router.register(r"", ApprovalViewSet, basename="approval")

urlpatterns = router.urls
