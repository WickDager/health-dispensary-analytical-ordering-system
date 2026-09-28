from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.crm.views import (
    AccountViewSet,
    ActivityViewSet,
    BulkExportView,
    CampaignViewSet,
    ContactViewSet,
    LeadViewSet,
    OpportunityViewSet,
    RefillReminderViewSet,
    TagViewSet,
    TaskViewSet,
)

app_name = "crm"

router = DefaultRouter()
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"contacts", ContactViewSet, basename="contact")
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"opportunities", OpportunityViewSet, basename="opportunity")
router.register(r"activities", ActivityViewSet, basename="activity")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"refill-reminders", RefillReminderViewSet, basename="refillreminder")

urlpatterns = router.urls + [
    path("export/", BulkExportView.as_view(), name="bulk-export"),
]
