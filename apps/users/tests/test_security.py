from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import PasswordResetOTP, Users
from apps.users.services.password_reset_service import PasswordResetService
from project_adhd import settings as project_settings


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return Users.objects.create_user(
        username='security_user',
        email='security_user@test.com',
        password='OldPassword123!',
        is_verified=True,
    )


@pytest.mark.django_db
class TestPasswordResetSecurity:
    change_url = '/api/users/v1/users/password-reset/change'
    request_url = '/api/users/v1/users/password-reset/request'
    verify_url = '/api/users/v1/users/password-reset/otp-verify'

    def test_reset_without_token_fails(self, api_client, user):
        response = api_client.post(
            self.change_url,
            {'email': user.email, 'password': 'NewPassword123!'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.check_password('OldPassword123!')

    def test_reset_with_invalid_token_fails(self, api_client, user):
        reset, _ = PasswordResetOTP.create_for_user(user, otp='123456')
        reset.issue_reset_token()

        response = api_client.post(
            self.change_url,
            {
                'email': user.email,
                'reset_token': 'invalid-token',
                'password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.check_password('OldPassword123!')

    def test_reset_with_expired_token_fails(self, api_client, user):
        reset, _ = PasswordResetOTP.create_for_user(user, otp='123456')
        reset_token = reset.issue_reset_token()
        reset.expires_at = timezone.now() - timedelta(minutes=1)
        reset.save(update_fields=['expires_at'])

        response = api_client.post(
            self.change_url,
            {
                'email': user.email,
                'reset_token': reset_token,
                'password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.check_password('OldPassword123!')

    def test_reused_token_fails(self, api_client, user):
        reset, _ = PasswordResetOTP.create_for_user(user, otp='123456')
        reset_token = reset.issue_reset_token()

        first_response = api_client.post(
            self.change_url,
            {
                'email': user.email,
                'reset_token': reset_token,
                'password': 'NewPassword123!',
            },
            format='json',
        )
        second_response = api_client.post(
            self.change_url,
            {
                'email': user.email,
                'reset_token': reset_token,
                'password': 'AnotherPassword123!',
            },
            format='json',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.check_password('NewPassword123!')

    def test_valid_verified_token_resets_password(self, api_client, user):
        reset, _ = PasswordResetOTP.create_for_user(user, otp='123456')
        reset_token = reset.issue_reset_token()

        response = api_client.post(
            self.change_url,
            {
                'email': user.email,
                'reset_token': reset_token,
                'password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        user.refresh_from_db()
        assert user.check_password('NewPassword123!')
        reset.refresh_from_db()
        assert reset.is_used is True
        assert reset.reset_token_hash is None

    def test_otp_verification_returns_one_time_reset_token(self, api_client, user):
        with patch('apps.users.tasks.send_mail') as mocked_send_mail:
            response = api_client.post(self.request_url, {'email': user.email}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        otp = mocked_send_mail.call_args.args[1].split(': ')[1].split('.')[0]

        verify_response = api_client.post(
            self.verify_url,
            {'email': user.email, 'otp': otp},
            format='json',
        )
        replay_response = api_client.post(
            self.verify_url,
            {'email': user.email, 'otp': otp},
            format='json',
        )

        assert verify_response.status_code == status.HTTP_200_OK
        assert verify_response.data['data']['reset_token']
        assert replay_response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPasswordResetService:
    def test_request_reset_creates_hashed_otp_and_sends_email(self, user):
        with patch('apps.users.tasks.send_mail') as mocked_send_mail:
            PasswordResetService.request_reset(user.email)

        reset = PasswordResetOTP.objects.get(user=user)
        assert reset.otp is None
        assert reset.otp_hash
        mocked_send_mail.assert_called_once()
        assert mocked_send_mail.call_args.args[3] == [user.email]

    @override_settings(PASSWORD_RESET_EMAIL_ASYNC=True)
    def test_request_reset_falls_back_to_direct_email_when_queue_fails(self, user):
        with patch(
            'apps.users.services.password_reset_service.send_otp_email_task.delay',
            side_effect=Exception('broker unavailable'),
        ) as mocked_delay, patch('apps.users.tasks.send_mail') as mocked_send_mail:
            PasswordResetService.request_reset(user.email)

        mocked_delay.assert_called_once()
        mocked_send_mail.assert_called_once()
        assert mocked_send_mail.call_args.args[3] == [user.email]

    def test_verify_otp_issues_reset_token(self, user):
        reset, otp = PasswordResetOTP.create_for_user(user, otp='123456')

        reset_token = PasswordResetService.verify_otp(user.email, otp)

        reset.refresh_from_db()
        assert reset_token
        assert reset.is_verified is True
        assert reset.otp_hash is None

    def test_change_password_marks_reset_token_used(self, user):
        reset, _ = PasswordResetOTP.create_for_user(user, otp='123456')
        reset_token = reset.issue_reset_token()

        PasswordResetService.change_password(user.email, reset_token, 'NewPassword123!')

        user.refresh_from_db()
        reset.refresh_from_db()
        assert user.check_password('NewPassword123!')
        assert reset.is_used is True
        assert reset.reset_token_hash is None


@pytest.mark.django_db
class TestRegistrationPrivilegeEscalation:
    registration_url = '/api/users/v1/users/registration'

    def test_registration_cannot_self_assign_staff_or_admin(self, api_client):
        response = api_client.post(
            self.registration_url,
            {
                'username': 'public_user',
                'email': 'public_user@test.com',
                'password': 'Password123!',
                'is_staff': True,
                'is_admin': True,
                'is_superuser': True,
                'is_active': False,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        created_user = Users.objects.get(email='public_user@test.com')
        assert created_user.is_staff is False
        assert created_user.is_admin is False
        assert created_user.is_superuser is False

    def test_registration_cannot_mutate_existing_user_by_id(self, api_client):
        existing_user = Users.objects.create_user(
            username='existing_user',
            email='existing_user@test.com',
            password='Password123!',
            is_verified=True,
        )

        response = api_client.post(
            self.registration_url,
            {
                'id': existing_user.id,
                'username': 'new_public_user',
                'email': 'new_public_user@test.com',
                'password': 'Password123!',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        existing_user.refresh_from_db()
        assert existing_user.username == 'existing_user'
        assert existing_user.email == 'existing_user@test.com'
        assert Users.objects.filter(email='new_public_user@test.com').exists()


@pytest.mark.django_db
class TestJWTAuthenticationUserState:
    profile_url = '/api/users/v1/users/get-user-profile'

    def _authenticate_with_jwt(self, api_client, user):
        access_token = RefreshToken.for_user(user).access_token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def test_active_user_can_access_protected_api(self, api_client):
        user = Users.objects.create_user(
            username='active_jwt_user',
            email='active_jwt_user@test.com',
            password='Password123!',
            is_verified=True,
            is_active=True,
            is_deleted=False,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.get(self.profile_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True

    def test_inactive_user_token_is_rejected(self, api_client):
        user = Users.objects.create_user(
            username='inactive_jwt_user',
            email='inactive_jwt_user@test.com',
            password='Password123!',
            is_verified=True,
            is_active=False,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.get(self.profile_url)

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_soft_deleted_user_token_is_rejected(self, api_client):
        user = Users.objects.create_user(
            username='deleted_jwt_user',
            email='deleted_jwt_user@test.com',
            password='Password123!',
            is_verified=True,
            is_deleted=True,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.get(self.profile_url)

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


class TestProductionSecretConfig:
    def test_missing_production_secret_fails_fast(self, monkeypatch):
        monkeypatch.setattr(project_settings, 'IS_PRODUCTION', True)

        with pytest.raises(ImproperlyConfigured):
            project_settings.get_secret_config('MISSING_REQUIRED_SECRET_FOR_TEST')
