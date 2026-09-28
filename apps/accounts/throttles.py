from rest_framework.throttling import ScopedRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    scope = "login"


class IngestRateThrottle(ScopedRateThrottle):
    scope = "ingest"


class BulkExportRateThrottle(ScopedRateThrottle):
    scope = "bulk_export"
