"""
URL configuration for HDAOS v3.0.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.catalog.urls")),
    path("api/lots/", include("apps.lots.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/ingest/", include("apps.ingest.urls")),
    path("api/llm/", include("apps.llm.urls")),
    path("api/approvals/", include("apps.approvals.urls")),
    path("api/crm/", include("apps.crm.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/intelligence/", include("apps.intelligence.urls")),
    path("api/settings/", include("apps.intelligence.settings_urls")),
]
