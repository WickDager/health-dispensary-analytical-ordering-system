from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class RoleAllowed(BasePermission):
    """Fine-grained role-based access control.

    Usage in ViewSets::

        permission_classes = [
            IsAuthenticated,
            RoleAllowed({"SALES": "write"}),
        ]

        permission_classes = [
            IsAuthenticated,
            RoleAllowed({"SALES": "write", "PHARMACIST": "read"}),
        ]

    ``"write"`` grants full access (all HTTP methods).
    ``"read"``  grants access only to safe methods (GET, HEAD, OPTIONS).

    Users with the ``ADMIN`` role always have full access.
    """

    def __init__(self, role_map: dict[str, str] | None = None) -> None:
        super().__init__()
        self.role_map = role_map or {}

    def __call__(self) -> RoleAllowed:
        # Called by DRF when the class is used as an instance factory.
        return self

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(request.user, "role", None)
        if role is None:
            return False

        # ADMIN always has full access.
        if role == "ADMIN":
            return True

        access = self.role_map.get(role)
        if access is None:
            return False
        if access == "write":
            return True
        if access == "read":
            return request.method in SAFE_METHODS
        return False

    def has_object_permission(self, request, view, obj) -> bool:
        # Delegate to the same logic; object-level is not further restricted.
        return self.has_permission(request, view)
