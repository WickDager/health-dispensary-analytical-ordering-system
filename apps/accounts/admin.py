from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "mrn_access")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("HDAOS Profile", {"fields": ("role", "mrn_access", "theme_preference")}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("HDAOS Profile", {"fields": ("role", "mrn_access", "theme_preference")}),
    )
