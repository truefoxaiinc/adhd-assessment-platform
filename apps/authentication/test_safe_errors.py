from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from helpers.exceptions.exceptions import handle_exception


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestSafeApiErrors:
    def test_forced_internal_exception_returns_safe_response(self, api_client):
        leaked_error = "RuntimeError in apps/authentication/views.py tb_lineno=123 traceback"

        with patch("apps.authentication.views.LoginSerializer.is_valid", side_effect=RuntimeError(leaked_error)):
            response = api_client.post(
                "/api/auth/v1/login/",
                {"email": "user@example.com", "password": "Password123!"},
                format="json",
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data == {
            "success": False,
            "message": "Internal server error",
            "code": "INTERNAL_ERROR",
        }

    def test_internal_exception_response_does_not_leak_debug_details(self, api_client):
        leaked_error = "RuntimeError in apps/authentication/views.py tb_lineno=123 traceback"

        with patch("apps.authentication.views.LoginSerializer.is_valid", side_effect=RuntimeError(leaked_error)):
            response = api_client.post(
                "/api/auth/v1/login/",
                {"email": "user@example.com", "password": "Password123!"},
                format="json",
            )

        response_text = str(response.data).lower()
        assert "views.py" not in response_text
        assert "tb_lineno" not in response_text
        assert "traceback" not in response_text
        assert "runtimeerror" not in response_text
        assert leaked_error.lower() not in response_text

    def test_validation_errors_still_return_400(self, api_client):
        response = api_client.post("/api/auth/v1/login/", {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_authentication_errors_still_return_401(self, api_client):
        response = api_client.get("/api/users/v1/users/get-user-profile")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["success"] is False
        assert response.data["code"] == "AUTHENTICATION_ERROR"

    def test_permission_errors_still_return_403(self):
        response = handle_exception(PermissionDenied(), {})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {
            "success": False,
            "message": "You do not have permission to perform this action",
            "code": "PERMISSION_DENIED",
        }
