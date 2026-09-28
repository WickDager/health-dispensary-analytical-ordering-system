"""Cookie-based JWT authentication for HDAOS.

Reads the access token from the `hdaos_access` HttpOnly cookie
so the React frontend (which cannot touch HttpOnly cookies)
can authenticate transparently via `credentials: 'include'`.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate using the JWT access token stored in an HttpOnly cookie."""

    def authenticate(self, request):
        # Try cookie first, then fall back to Authorization header
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get("AUTH_COOKIE", "hdaos_access"))
        if raw_token is None:
            # Fall back to header-based auth (for API testing with Bearer tokens)
            header = self.get_header(request)
            if header is not None:
                raw_token = self.get_raw_token(header)
            else:
                return None

        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            return None

        return self.get_user(validated_token), validated_token
