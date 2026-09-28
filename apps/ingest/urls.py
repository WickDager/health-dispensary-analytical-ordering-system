from django.urls import path

from apps.ingest.views import upload_invoice, ingest_status, commit_ingest

app_name = "ingest"

urlpatterns = [
    path("", upload_invoice, name="ingest-upload"),
    path("status/", ingest_status, name="ingest-status"),
    path("<uuid:task_id>/status/", ingest_status, name="ingest-task-status"),
    path("commit/", commit_ingest, name="ingest-commit"),
]
