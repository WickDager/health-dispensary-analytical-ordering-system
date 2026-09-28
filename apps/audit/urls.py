from django.urls import path

from apps.audit.views import audit_log_list

app_name = "audit"

urlpatterns = [
    path("", audit_log_list, name="audit-log-list"),
]
