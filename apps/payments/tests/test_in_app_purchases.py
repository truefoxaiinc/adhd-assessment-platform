from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.models import EntitlementStatus, StorePlatform, StorePurchase, SubscriptionEntitlement
from apps.payments.services import _google_service, save_verified_purchase, verify_google_purchase
from apps.users.models import Users


@pytest.fixture
def user():
    return Users.objects.create_user(
        username='iap_user', email='iap@test.com', password='Password123!', is_verified=True
    )


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def verified_purchase(user, **overrides):
    values = {
        'platform': StorePlatform.ANDROID,
        'store_purchase_id': 'google-purchase-token',
        'original_transaction_id': 'google-purchase-token',
        'latest_transaction_id': 'GPA.1234',
        'product_id': 'attentionminder.monthly',
        'environment': 'test',
        'status': EntitlementStatus.ACTIVE,
        'purchased_at': timezone.now(),
        'expires_at': timezone.now() + timezone.timedelta(days=30),
        'auto_renewing': True,
        'raw_verification_response': {'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE'},
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_verification_endpoint_requires_authentication(client):
    response = client.post(
        '/api/payments/v1/payments/verify-in-app-purchase/',
        {'platform': 'android', 'product_id': 'attentionminder.monthly', 'purchase_token': 'token'},
        content_type='application/json',
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_invalid_verification_request_logs_safe_context(authed_client, user, caplog):
    response = authed_client.post(
        '/api/payments/v1/payments/verify-in-app-purchase/',
        {
            'platform': 'android',
            'product_id': 'attentionminder.monthly',
            'purchase_token': 'secret-purchase-token',
            'is_restore': 'not-a-boolean',
        },
        format='json',
    )

    assert response.status_code == 400
    assert 'In-app purchase request validation failed' in caplog.text
    assert f"'user_id': {user.pk}" in caplog.text
    assert 'secret-purchase-token' not in caplog.text


@pytest.mark.django_db
def test_android_verification_returns_entitlement(authed_client, user):
    with patch(
        'apps.payments.views.verify_in_app_purchase',
        side_effect=lambda request_user, attrs: save_verified_purchase(request_user, verified_purchase(user)),
    ):
        response = authed_client.post(
            '/api/payments/v1/payments/verify-in-app-purchase/',
            {
                'platform': 'android',
                'product_id': 'attentionminder.monthly',
                'purchase_id': 'GPA.1234',
                'verification_data': 'google-purchase-token',
                'verification_source': 'google_play',
            },
            format='json',
        )

    assert response.status_code == 200
    assert response.data['data']['verified'] is True
    assert response.data['data']['subscription_status'] == 'active'
    assert StorePurchase.objects.get().user == user
    assert SubscriptionEntitlement.objects.get(user=user).is_active is True


@pytest.mark.django_db
def test_store_evidence_cannot_be_credited_to_two_users(user):
    save_verified_purchase(user, verified_purchase(user))
    another = Users.objects.create_user(username='other', email='other@test.com')

    with pytest.raises(Exception) as exc_info:
        save_verified_purchase(another, verified_purchase(another))

    assert 'another account' in str(exc_info.value)
    assert StorePurchase.objects.count() == 1


@pytest.mark.django_db
@override_settings(GOOGLE_PLAY_PACKAGE_NAME='com.trufox.attentionminder')
def test_google_purchase_is_verified_with_subscriptions_v2(user):
    payload = {
        'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE',
        'startTime': '2026-08-01T00:00:00Z',
        'latestOrderId': 'GPA.1234',
        'lineItems': [{
            'productId': 'attentionminder.monthly',
            'expiryTime': '2099-09-10T12:00:00Z',
            'autoRenewingPlan': {'autoRenewEnabled': True},
        }],
    }
    execute = MagicMock(return_value=payload)
    get = MagicMock(return_value=MagicMock(execute=execute))
    service = MagicMock()
    service.purchases.return_value.subscriptionsv2.return_value.get = get

    with patch('apps.payments.services._google_service', return_value=service):
        result = verify_google_purchase(user, {
            'product_id': 'attentionminder.monthly',
            'purchase_token': 'server-verification-token',
        })

    get.assert_called_once_with(
        packageName='com.trufox.attentionminder', token='server-verification-token'
    )
    assert result['status'] == EntitlementStatus.ACTIVE
    assert result['expires_at'].year == 2099


@override_settings(
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON='{"type":"service_account"}',
    GOOGLE_PLAY_SERVICE_ACCOUNT_FILE='C:/secrets/google-play.json',
)
def test_google_credentials_reject_ambiguous_configuration():
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _google_service()

    assert 'only one' in str(exc_info.value)


@override_settings(
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON='',
    GOOGLE_PLAY_SERVICE_ACCOUNT_FILE='C:/missing/google-play.json',
)
def test_google_credentials_report_missing_file_without_exposing_path():
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _google_service()

    message = str(exc_info.value)
    assert 'readable file' in message
    assert 'C:/missing' not in message


@override_settings(
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON='not-json',
    GOOGLE_PLAY_SERVICE_ACCOUNT_FILE='',
)
def test_google_credentials_report_invalid_json_safely():
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _google_service()

    assert str(exc_info.value) == 'GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is invalid'


@pytest.mark.django_db
def test_expired_entitlement_is_not_verified(authed_client, user):
    purchase = StorePurchase.objects.create(
        user=user, **verified_purchase(user, status=EntitlementStatus.EXPIRED,
                                       expires_at=timezone.now() - timezone.timedelta(days=1))
    )
    SubscriptionEntitlement.objects.create(
        user=user,
        platform=purchase.platform,
        product_id=purchase.product_id,
        status=purchase.status,
        expires_at=purchase.expires_at,
        source_purchase=purchase,
    )

    response = authed_client.get('/api/payments/v1/payments/entitlement/')

    assert response.status_code == 200
    assert response.data['data']['verified'] is False
    assert response.data['data']['subscription_status'] == 'expired'
