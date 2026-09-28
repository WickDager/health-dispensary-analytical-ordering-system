from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrator"
    PHARMACIST = "PHARMACIST", "Pharmacist"
    LOGISTICS = "LOGISTICS", "Logistics Manager"
    PROCUREMENT = "PROCUREMENT", "Procurement Officer"
    SALES = "SALES", "Account Manager"
    VIEWER = "VIEWER", "Viewer"


class ThemePref(models.TextChoices):
    LIGHT = "light", "Light"
    DARK = "dark", "Dark"
    SYSTEM = "system", "System"


class User(AbstractUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.PHARMACIST,
    )
    mrn_access = models.BooleanField(
        default=False,
        help_text="Whether the user can access Medical Record Numbers.",
    )
    theme_preference = models.CharField(
        max_length=8,
        choices=ThemePref.choices,
        default=ThemePref.SYSTEM,
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Users are inactive by default until approved by an admin.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
        ]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"
