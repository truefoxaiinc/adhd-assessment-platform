from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIClient, APIRequestFactory

from helpers.exceptions.exceptions import handle_exception


def test_content_auth_failure_logs_safe_request_and_response():
    request = APIRequestFactory().get(
        '/api/content/v1/contents/12?token=query-secret',
        HTTP_AUTHORIZATION='Bearer bearer-secret',
        HTTP_X_ENTITLEMENT_TOKEN='guest-secret',
        HTTP_COOKIE='sessionid=cookie-secret',
    )
    with patch('helpers.exceptions.exceptions.auth_logger.warning') as warning:
        response = handle_exception(AuthenticationFailed('Invalid entitlement token.'), {'request': request})

    assert response.status_code == 401
    warning.assert_called_once()
    message = warning.call_args.args[1]
    assert 'invalid_guest_token' in message
    assert '/api/content/v1/contents/12' in message
    assert 'response_body' in message
    for secret in ('query-secret', 'bearer-secret', 'guest-secret', 'cookie-secret'):
        assert secret not in message


def test_content_auth_logger_does_not_log_other_endpoints():
    request = APIRequestFactory().get('/api/users/v1/users/get-user-profile')
    with patch('helpers.exceptions.exceptions.auth_logger.warning') as warning:
        handle_exception(AuthenticationFailed(), {'request': request})
    warning.assert_not_called()


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
