from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.serializers import (
    PreferencesSerializer,
    RegisterSerializer,
    UserApprovalSerializer,
    UserSerializer,
)
from apps.accounts.throttles import LoginRateThrottle

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Register a new user account (inactive until admin approval)."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]


class LoginView(TokenObtainPairView):
    """Login with rate limiting. Sets JWT tokens as HttpOnly cookies."""

    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Set HttpOnly cookies for the frontend
        if response.status_code == 200:
            data = response.data
            access = data.get("access")
            refresh = data.get("refresh")
            if access:
                response.set_cookie(
                    "hdaos_access", access,
                    httponly=True, secure=not settings.DEBUG, samesite="Strict",
                    max_age=1800,  # 30 minutes
                )
            if refresh:
                response.set_cookie(
                    "hdaos_refresh", refresh,
                    httponly=True, secure=not settings.DEBUG, samesite="Strict",
                    max_age=604800,  # 7 days
                )
        return response


class MeView(generics.RetrieveAPIView):
    """Return the currently authenticated user's profile."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UpdatePreferencesView(generics.UpdateAPIView):
    """Update the current user's theme preference."""

    serializer_class = PreferencesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserApprovalView(generics.ListAPIView):
    """List pending users for admin approval.

    Admins can activate users via the approvals workflow
    (POST /api/approvals/{id}/approve/ with action_type USER_ACTIVATE).
    """

    serializer_class = UserApprovalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role != "ADMIN":
            return User.objects.none()
        return User.objects.filter(is_active=False).order_by("-date_joined")


class LogoutView(generics.GenericAPIView):
    """Clear JWT cookies to log the user out."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        response = Response({"detail": "Logged out"})
        response.delete_cookie("hdaos_access")
        response.delete_cookie("hdaos_refresh")
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh the access token using the refresh token from the HttpOnly cookie."""

    def post(self, request, *args, **kwargs):
        # Pull the refresh token from the cookie if not in the body
        refresh_token = request.data.get("refresh") or request.COOKIES.get(
            settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "hdaos_refresh")
        )

        if not refresh_token:
            return Response(
                {"detail": "No refresh token provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build a mutable data dict for the serializer
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data["refresh"] = refresh_token

        from rest_framework_simplejwt.serializers import TokenRefreshSerializer
        serializer = TokenRefreshSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        access = serializer.validated_data.get("access")
        new_refresh = serializer.validated_data.get("refresh")

        if access:
            response.set_cookie(
                "hdaos_access", access,
                httponly=True, secure=not settings.DEBUG, samesite="Strict", max_age=1800,
            )
        if new_refresh:
            response.set_cookie(
                "hdaos_refresh", new_refresh,
                httponly=True, secure=not settings.DEBUG, samesite="Strict", max_age=604800,
            )
        return response
