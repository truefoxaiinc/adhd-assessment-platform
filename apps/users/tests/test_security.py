from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.models import (
    EntitlementStatus,
    StorePlatform,
    StorePurchase,
    SubscriptionEntitlement,
)
from apps.users.models import OAuthAccount, OAuthProvider, PasswordResetOTP, Users
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
        with patch('apps.users.tasks.EmailMultiAlternatives') as mocked_email:
            response = api_client.post(self.request_url, {'email': user.email}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        otp = mocked_email.call_args.args[1].split('code is: ')[1].split('\n')[0]

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
        with patch('apps.users.tasks.EmailMultiAlternatives') as mocked_email:
            PasswordResetService.request_reset(user.email)

        reset = PasswordResetOTP.objects.get(user=user)
        assert reset.otp is None
        assert reset.otp_hash
        mocked_email.assert_called_once()
        assert mocked_email.call_args.args[3] == [user.email]
        mocked_email.return_value.attach_alternative.assert_called_once()
        mocked_email.return_value.send.assert_called_once_with(fail_silently=False)

    @override_settings(PASSWORD_RESET_EMAIL_ASYNC=True)
    def test_request_reset_falls_back_to_direct_email_when_queue_fails(self, user):
        with patch(
            'apps.users.services.password_reset_service.send_otp_email_task.delay',
            side_effect=Exception('broker unavailable'),
        ) as mocked_delay, patch('apps.users.tasks.EmailMultiAlternatives') as mocked_email:
            PasswordResetService.request_reset(user.email)

        mocked_delay.assert_called_once()
        mocked_email.assert_called_once()
        assert mocked_email.call_args.args[3] == [user.email]

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
    update_profile_url = '/api/users/v1/users/update-profile'

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
        assert response.data['data']['has_active_subscription'] is False
        assert response.data['data']['subscription_status'] == 'inactive'
        assert response.data['data']['subscription_expires_at'] == ''

    def test_profile_without_height_and_weight_is_complete(self, api_client):
        user = Users.objects.create_user(
            username='complete_profile_user',
            email='complete_profile_user@test.com',
            password='Password123!',
            dob='1998-09-01',
            gender='MALE',
            country='India',
            height=None,
            weight=None,
            is_verified=True,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.get(self.profile_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['is_completed'] is True
        assert response.data['data']['profile_image'] is None
        assert response.data['data']['profile_image_url'] is None
        assert 'height' not in response.data['data']
        assert 'weight' not in response.data['data']

    def test_profile_update_succeeds_without_height_and_weight(self, api_client):
        user = Users.objects.create_user(
            username='profile_before_update',
            email='profile_before_update@test.com',
            password='Password123!',
            height=None,
            weight=None,
            is_verified=True,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.post(
            self.update_profile_url,
            {
                'id': user.id,
                'username': 'admin',
                'email': 'admin@gmail.com',
                'dob': '1998-09-01',
                'gender': 'MALE',
                'country': 'India',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['is_completed'] is True
        assert 'height' not in response.data['data']
        assert 'weight' not in response.data['data']
        user.refresh_from_db()
        assert user.height is None
        assert user.weight is None

    @pytest.mark.parametrize('missing_field', ['dob', 'gender', 'country'])
    def test_missing_required_profile_field_is_incomplete(
        self,
        api_client,
        missing_field,
    ):
        profile_fields = {
            'dob': '1998-09-01',
            'gender': 'MALE',
            'country': 'India',
        }
        profile_fields[missing_field] = None
        user = Users.objects.create_user(
            username=f'missing_{missing_field}_user',
            email=f'missing_{missing_field}_user@test.com',
            password='Password123!',
            is_verified=True,
            **profile_fields,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.get(self.profile_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['is_completed'] is False

    def test_profile_returns_active_subscription_details(self, api_client):
        user = Users.objects.create_user(
            username='subscribed_profile_user',
            email='subscribed_profile_user@test.com',
            password='Password123!',
            is_verified=True,
        )
        expires_at = timezone.now() + timedelta(days=30)
        purchase = StorePurchase.objects.create(
            user=user,
            platform=StorePlatform.ANDROID,
            product_id='attentionminder.monthly',
            store_purchase_id='profile-subscription-token',
            status=EntitlementStatus.ACTIVE,
            expires_at=expires_at,
        )
        SubscriptionEntitlement.objects.create(
            user=user,
            platform=StorePlatform.ANDROID,
            product_id=purchase.product_id,
            status=EntitlementStatus.ACTIVE,
            expires_at=expires_at,
            source_purchase=purchase,
        )
        self._authenticate_with_jwt(api_client, user)

        response = api_client.get(self.profile_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['has_active_subscription'] is True
        assert response.data['data']['subscription_status'] == 'active'
        assert response.data['data']['subscription_expires_at']

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


@pytest.mark.django_db
class TestDeleteAccountApi:
    delete_account_url = '/api/users/v1/users/delete-account'

    def test_logged_in_user_can_deactivate_own_account(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.delete_account_url,
            {'action': 'deactivate', 'password': 'OldPassword123!'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data'] == {
            'action': 'deactivate',
            'is_active': False,
            'is_deleted': False,
        }
        user.refresh_from_db()
        assert user.is_active is False
        assert user.is_deleted is False

    def test_logged_in_user_can_soft_delete_own_account(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.delete_account_url,
            {'action': 'delete', 'password': 'OldPassword123!'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data'] == {
            'action': 'delete',
            'is_active': False,
            'is_deleted': True,
        }
        user.refresh_from_db()
        assert user.is_active is False
        assert user.is_deleted is True

    def test_delete_account_rejects_user_id_payload(self, api_client, user):
        other_user = Users.objects.create_user(
            username='other_delete_user',
            email='other_delete_user@test.com',
            password='Password123!',
            is_verified=True,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.delete_account_url,
            {'action': 'delete', 'password': 'OldPassword123!', 'user': other_user.id},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        other_user.refresh_from_db()
        assert user.is_active is True
        assert user.is_deleted is False
        assert other_user.is_active is True
        assert other_user.is_deleted is False

    def test_delete_account_requires_authentication(self, api_client):
        response = api_client.post(
            self.delete_account_url,
            {'action': 'delete', 'password': 'OldPassword123!'},
            format='json',
        )

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_delete_account_rejects_missing_password(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.delete_account_url,
            {'action': 'delete'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['status'] is False
        user.refresh_from_db()
        assert user.is_active is True
        assert user.is_deleted is False

    def test_delete_account_rejects_wrong_password(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.delete_account_url,
            {'action': 'delete', 'password': 'WrongPassword123!'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['status'] is False
        assert response.data['errors']['password'] == ['Invalid password.']
        user.refresh_from_db()
        assert user.is_active is True
        assert user.is_deleted is False


class TestProductionSecretConfig:
    def test_missing_production_secret_fails_fast(self, monkeypatch):
        monkeypatch.setattr(project_settings, 'IS_PRODUCTION', True)

        with pytest.raises(ImproperlyConfigured):
            project_settings.get_secret_config('MISSING_REQUIRED_SECRET_FOR_TEST')


@pytest.mark.django_db
class TestGoogleSocialLogin:
    social_login_url = '/api/users/v1/users/social-login'

    def test_google_social_login_creates_user_oauth_link_and_tokens(self, api_client):
        identity = {
            'provider': OAuthProvider.GOOGLE,
            'provider_subject': 'google-subject-123',
            'email': 'google_user@test.com',
            'email_verified': True,
            'username': 'Google_User',
            'dob': None,
        }

        with patch('apps.users.api.views.SocialLoginView._verify_google_token', return_value=identity):
            response = api_client.post(
                self.social_login_url,
                {'provider': 'google', 'id_token': 'google.id.token'},
                format='json',
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] is True
        assert response.data['data']['tokens']['access']
        assert response.data['data']['tokens']['refresh']
        user = Users.objects.get(email='google_user@test.com')
        oauth_account = OAuthAccount.objects.get(
            provider=OAuthProvider.GOOGLE,
            provider_subject='google-subject-123',
        )
        assert oauth_account.user == user
        assert user.is_verified is True
        assert user.has_usable_password() is False

    def test_google_social_login_reuses_existing_link(self, api_client):
        user = Users.objects.create_user(
            username='google_user',
            email='google_user@test.com',
            is_verified=True,
        )
        OAuthAccount.objects.create(
            user=user,
            provider=OAuthProvider.GOOGLE,
            provider_subject='google-subject-123',
            email=user.email,
            email_verified=True,
        )
        identity = {
            'provider': OAuthProvider.GOOGLE,
            'provider_subject': 'google-subject-123',
            'email': user.email,
            'email_verified': True,
            'username': user.username,
            'dob': None,
        }

        with patch('apps.users.api.views.SocialLoginView._verify_google_token', return_value=identity):
            response = api_client.post(
                self.social_login_url,
                {'provider': 'google', 'id_token': 'google.id.token'},
                format='json',
            )

        assert response.status_code == status.HTTP_200_OK
        assert Users.objects.filter(email=user.email).count() == 1
        assert OAuthAccount.objects.filter(
            provider=OAuthProvider.GOOGLE,
            provider_subject='google-subject-123',
        ).count() == 1

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=['allowed-client.apps.googleusercontent.com'])
    def test_google_token_requires_configured_audience_and_verified_email(self, monkeypatch):
        view = __import__(
            'apps.users.api.views',
            fromlist=['SocialLoginView'],
        ).SocialLoginView()
        monkeypatch.setattr(
            'apps.users.api.views.google_id_token.verify_oauth2_token',
            lambda *args, **kwargs: {
                'iss': 'https://accounts.google.com',
                'aud': 'different-client.apps.googleusercontent.com',
                'sub': 'google-subject-123',
                'email': 'google_user@test.com',
                'email_verified': True,
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            view._verify_google_token('google.id.token')

        assert 'audience mismatch' in str(exc_info.value.detail['id_token'])

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=['allowed-client.apps.googleusercontent.com'])
    def test_invalid_google_token_returns_unauthorized(self, api_client):
        with patch(
            'apps.users.api.views.google_id_token.verify_oauth2_token',
            side_effect=ValueError('bad signature'),
        ):
            response = api_client.post(
                self.social_login_url,
                {'provider': 'google', 'id_token': 'invalid.google.token'},
                format='json',
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['status'] is False
        assert response.data['errors']['id_token'] == 'Invalid or expired Google ID token'


@pytest.mark.django_db
class TestAppleSocialLogin:
    social_login_url = '/api/users/v1/users/social-login'

    def test_apple_social_login_creates_user_and_oauth_link(self, api_client):
        identity = {
            'provider': OAuthProvider.APPLE,
            'provider_subject': 'apple-subject-123',
            'email': 'apple_user@test.com',
            'email_verified': True,
            'username': 'apple_user',
            'dob': None,
        }

        with patch('apps.users.api.views.SocialLoginView._verify_apple_token', return_value=identity):
            response = api_client.post(
                self.social_login_url,
                {'provider': 'apple', 'id_token': 'apple.identity.token'},
                format='json',
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] is True
        user = Users.objects.get(email='apple_user@test.com')
        oauth_account = OAuthAccount.objects.get(
            provider=OAuthProvider.APPLE,
            provider_subject='apple-subject-123',
        )
        assert oauth_account.user == user
        assert user.is_verified is True

    def test_apple_social_login_replaces_google_placeholder_username(self, api_client):
        user = Users.objects.create_user(
            username='google_existing-subject',
            email='existing_social_user@test.com',
            password='Password123!',
            is_verified=True,
        )
        identity = {
            'provider': OAuthProvider.APPLE,
            'provider_subject': 'apple-existing-subject',
            'email': user.email,
            'email_verified': True,
            'username': 'existing_social_user',
            'dob': None,
        }

        with patch('apps.users.api.views.SocialLoginView._verify_apple_token', return_value=identity):
            response = api_client.post(
                self.social_login_url,
                {
                    'provider': 'apple',
                    'id_token': 'apple.identity.token',
                    'name': 'Apple User',
                },
                format='json',
            )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.username == 'Apple_User'

    def test_apple_social_login_accepts_native_full_name_object(self, api_client):
        user = Users.objects.create_user(
            username='random_private_relay_value',
            email='private_relay@privaterelay.appleid.com',
            password='Password123!',
            is_verified=True,
        )
        OAuthAccount.objects.create(
            user=user,
            provider=OAuthProvider.APPLE,
            provider_subject='apple-native-name-subject',
            email=user.email,
            email_verified=True,
        )
        identity = {
            'provider': OAuthProvider.APPLE,
            'provider_subject': 'apple-native-name-subject',
            'email': user.email,
            'email_verified': True,
            'username': user.username,
            'dob': None,
        }

        with patch('apps.users.api.views.SocialLoginView._verify_apple_token', return_value=identity):
            response = api_client.post(
                self.social_login_url,
                {
                    'provider': 'apple',
                    'id_token': 'apple.identity.token',
                    'full_name': {
                        'givenName': 'Muhammed',
                        'familyName': 'Fahad',
                    },
                },
                format='json',
            )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.username == 'Muhammed_Fahad'

    def test_apple_social_login_rejects_inactive_linked_user(self, api_client):
        user = Users.objects.create_user(
            username='inactive_apple_user',
            email='inactive_apple_user@test.com',
            password='Password123!',
            is_verified=True,
            is_active=False,
        )
        OAuthAccount.objects.create(
            user=user,
            provider=OAuthProvider.APPLE,
            provider_subject='inactive-apple-subject',
            email=user.email,
            email_verified=True,
        )
        identity = {
            'provider': OAuthProvider.APPLE,
            'provider_subject': 'inactive-apple-subject',
            'email': user.email,
            'email_verified': True,
            'username': user.username,
            'dob': None,
        }

        with patch('apps.users.api.views.SocialLoginView._verify_apple_token', return_value=identity):
            response = api_client.post(
                self.social_login_url,
                {'provider': 'apple', 'id_token': 'apple.identity.token'},
                format='json',
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['message'] == 'Account is disabled'

    @override_settings(APPLE_OAUTH_CLIENT_IDS=['com.truefox.attentionminder'])
    def test_apple_login_without_email_requires_existing_oauth_account(self, monkeypatch):
        view = __import__(
            'apps.users.api.views',
            fromlist=['SocialLoginView'],
        ).SocialLoginView()

        monkeypatch.setattr(view, '_get_apple_signing_key', lambda token: 'signing-key')
        monkeypatch.setattr(
            'apps.users.api.views.jwt.decode',
            lambda *args, **kwargs: {
                'sub': 'new-apple-subject',
                'aud': 'com.truefox.attentionminder',
                'iss': view.apple_issuer,
                'email_verified': 'true',
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            view._verify_apple_token('apple.identity.token')

        assert 'email address' in str(exc_info.value.detail['id_token'])
