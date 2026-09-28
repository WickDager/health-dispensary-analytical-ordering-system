from django.urls import path

from apps.intelligence.views import ai_settings, theme_settings, user_settings_list, user_settings_detail

app_name = "settings"

urlpatterns = [
    path("ai/", ai_settings, name="ai-settings"),
    path("theme/", theme_settings, name="theme-settings"),
    path("users/", user_settings_list, name="user-settings-list"),
    path("users/<uuid:pk>/", user_settings_detail, name="user-settings-detail"),
]
