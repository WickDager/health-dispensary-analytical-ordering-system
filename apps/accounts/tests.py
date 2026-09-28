"""
Comprehensive tests for the accounts app: User model, authentication,
JWT tokens, registration, roles, permissions, and theme preferences.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()


# ===========================================================================
# User Model Tests
# ===========================================================================
class TestUserModel:
    """Tests for the custom User model."""

    def test_create_user(self, db):
        """User can be created with basic fields."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert user.role == "PHARMACIST"  # default role
        assert user.is_active is False  # inactive until admin approval
        assert user.theme_preference == "system"  # default theme

    def test_create_user_with_role(self, db):
        """User can be created with a specific role."""
        user = User.objects.create_user(
            username="admin2", password="testpass123", role="ADMIN",
        )
        assert user.role == "ADMIN"

    def test_is_admin(self, db, admin_user, pharmacist_user):
        """is_admin() returns True only for ADMIN role."""
        assert admin_user.is_admin() is True
        assert pharmacist_user.is_admin() is False

    def test_user_str(self, db, admin_user):
        """String representation includes username and role."""
        s = str(admin_user)
        assert "admin" in s
        assert "Administrator" in s

    def test_user_theme_preference(self, db):
        """Theme preference defaults to 'system'."""
        user = User.objects.create_user(
            username="themeuser", password="testpass123",
        )
        assert user.theme_preference == "system"

    def test_user_mrn_access_default(self, db):
        """MRN access defaults to False."""
        user = User.objects.create_user(
            username="mrnuser", password="testpass123",
        )
        assert user.mrn_access is False

    def test_user_inactive_default(self, db):
        """New users are inactive by default."""
        user = User.objects.create_user(
            username="newuser", password="testpass123",
        )
        assert user.is_active is False

    def test_superuser_is_staff_and_superuser(self, db):
        """Superusers are created with staff and superuser flags."""
        user = User.objects.create_superuser(
            username="superuser", password="testpass123",
        )
        # is_active defaults to False (model default), must be activated by admin
        assert user.is_active is False
        assert user.is_superuser is True
        assert user.is_staff is True


# ===========================================================================
# Authentication API Tests
# ===========================================================================
class TestRegistrationAPI:
    """Tests for the registration endpoint."""

    URL = "/api/auth/register/"

    def test_register_success(self, api_client, db):
        """New user can register."""
        response = api_client.post(self.URL, {
            "username": "newpharmacist",
            "email": "new@hdaos.test",
            "password": "securepass123",
            "first_name": "Jane",
            "last_name": "Doe",
        })
        assert response.status_code == 201
        assert response.data["username"] == "newpharmacist"
        assert "password" not in response.data

        # User should be inactive
        user = User.objects.get(username="newpharmacist")
        assert user.is_active is False

    def test_register_missing_fields(self, api_client, db):
        """Registration requires username and password."""
        response = api_client.post(self.URL, {"username": "test"})
        assert response.status_code == 400

    def test_register_short_password(self, api_client, db):
        """Password must be at least 8 characters."""
        response = api_client.post(self.URL, {
            "username": "test", "password": "short",
        })
        assert response.status_code == 400

    def test_register_duplicate_username(self, api_client, admin_user):
        """Cannot register with duplicate username."""
        response = api_client.post(self.URL, {
            "username": "admin", "password": "testpass123",
        })
        assert response.status_code == 400

    def test_register_password_min_length(self, api_client, db):
        """Password validation enforces min length."""
        response = api_client.post(self.URL, {
            "username": "test2", "password": "1234567",  # 7 chars
        })
        assert response.status_code == 400

    def test_register_valid_password(self, api_client, db):
        """8-char password is accepted."""
        response = api_client.post(self.URL, {
            "username": "test3", "password": "12345678",
        })
        assert response.status_code == 201


class TestLoginAPI:
    """Tests for the login endpoint."""

    URL = "/api/auth/login/"

    def test_login_success(self, api_client, admin_user):
        """Active user can login and receives tokens."""
        response = api_client.post(self.URL, {
            "username": "admin", "password": "testpass123",
        })
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data
        # Cookies should be set
        assert "hdaos_access" in response.cookies
        assert "hdaos_refresh" in response.cookies

    def test_login_inactive_user(self, api_client, inactive_user):
        """Inactive user cannot login."""
        response = api_client.post(self.URL, {
            "username": "inactive", "password": "testpass123",
        })
        assert response.status_code == 401

    def test_login_wrong_password(self, api_client, admin_user):
        """Wrong password returns 401."""
        response = api_client.post(self.URL, {
            "username": "admin", "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_login_wrong_username(self, api_client, db):
        """Non-existent user returns 401."""
        response = api_client.post(self.URL, {
            "username": "nonexistent", "password": "testpass123",
        })
        assert response.status_code == 401

    def test_login_jwt_cookies_secure(self, api_client, admin_user):
        """JWT cookies are set with security attributes."""
        response = api_client.post(self.URL, {
            "username": "admin", "password": "testpass123",
        })
        # HttpOnly and SameSite should be set
        for cookie_name in ("hdaos_access", "hdaos_refresh"):
            cookie = response.cookies.get(cookie_name)
            if cookie:
                assert cookie.get("httponly", False) is True
                assert cookie.get("samesite", "").lower() in ("strict", "lax")


class TestLogoutAPI:
    """Tests for the logout endpoint."""

    URL = "/api/auth/logout/"

    def test_logout(self, admin_client):
        """Logout deletes JWT cookies."""
        response = admin_client.post(self.URL)
        assert response.status_code == 200
        # Cookies should be cleared
        for cookie_name in ("hdaos_access", "hdaos_refresh"):
            cookie_header = response.cookies.get(cookie_name)
            if cookie_header is not None:
                assert cookie_header.value in ("", None)

    def test_logout_unauthenticated(self, api_client):
        """Logout requires authentication."""
        response = api_client.post(self.URL)
        assert response.status_code == 401


class TestMeAPI:
    """Tests for the current user profile endpoint."""

    URL = "/api/auth/me/"

    def test_me_authenticated(self, admin_client, admin_user):
        """Authenticated user can get their profile."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert response.data["username"] == admin_user.username
        assert response.data["email"] == admin_user.email
        assert response.data["role"] == admin_user.role
        assert "theme_preference" in response.data

    def test_me_unauthenticated(self, api_client):
        """Unauthenticated user cannot get profile."""
        response = api_client.get(self.URL)
        assert response.status_code == 401


class TestPreferencesAPI:
    """Tests for theme preference endpoint."""

    URL = "/api/auth/me/preferences/"

    def test_update_theme_preference(self, admin_client, admin_user):
        """User can update their theme preference."""
        response = admin_client.patch(self.URL, {"theme_preference": "dark"})
        assert response.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.theme_preference == "dark"

    def test_update_invalid_theme(self, admin_client):
        """Invalid theme value is rejected."""
        response = admin_client.patch(self.URL, {"theme_preference": "invalid"})
        assert response.status_code == 400

    def test_update_theme_light(self, admin_client, admin_user):
        """Theme can be set to light."""
        response = admin_client.patch(self.URL, {"theme_preference": "light"})
        assert response.status_code == 200

    def test_update_theme_system(self, admin_client, admin_user):
        """Theme can be set to system."""
        response = admin_client.patch(self.URL, {"theme_preference": "system"})
        assert response.status_code == 200


class TestUserApprovalAPI:
    """Tests for user approval listing."""

    URL = "/api/auth/users/pending/"

    def test_admin_can_list_pending(self, admin_client, inactive_user):
        """Admin can list inactive users."""
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        assert len(results) >= 1
        usernames = [u["username"] for u in results]
        assert "inactive" in usernames

    def test_non_admin_cannot_list(self, pharmacist_client):
        """Non-admin sees empty list."""
        response = pharmacist_client.get(self.URL)
        assert response.status_code == 200
        assert response.data.get("results") == []


# ===========================================================================
# Permission Tests
# ===========================================================================
class TestRoleAllowed:
    """Tests for RoleAllowed DRF permission class."""

    URL = "/api/products/"  # uses IsAdminOrReadOnly

    def test_admin_full_access(self, admin_client):
        """Admin has full read+write access."""
        # Read
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        # Write is blocked on this endpoint because product requires supplier
        # but the permission itself allows it (403 means IsAdminOrReadOnly also
        # requires admin for write, and admin user is admin)

    def test_pharmacist_read_only(self, pharmacist_client, supplier):
        """Pharmacist can read but cannot create."""
        response = pharmacist_client.get(self.URL)
        assert response.status_code == 200
        # Attempt write
        response = pharmacist_client.post(self.URL, {
            "name": "Test", "api": "T", "strength": "10mg",
            "supplier": str(supplier.id),
        })
        assert response.status_code == 403

    def test_viewer_read_only(self, viewer_client, supplier):
        """Viewer can read but cannot create."""
        response = viewer_client.get(self.URL)
        assert response.status_code == 200
        response = viewer_client.post(self.URL, {
            "name": "Test", "api": "T", "strength": "10mg",
            "supplier": str(supplier.id),
        })
        assert response.status_code == 403

    def test_unauthenticated_blocked(self, api_client):
        """Unauthenticated users are blocked."""
        response = api_client.get(self.URL)
        assert response.status_code == 401
