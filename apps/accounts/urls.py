from django.urls import path

from apps.accounts.views import (
    CookieTokenRefreshView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    UpdatePreferencesView,
    UserApprovalView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", CookieTokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/preferences/", UpdatePreferencesView.as_view(), name="auth-preferences"),
    path("users/pending/", UserApprovalView.as_view(), name="auth-pending"),
]
