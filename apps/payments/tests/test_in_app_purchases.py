import hashlib
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from googleapiclient.errors import HttpError
from httplib2 import Response as HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.payments.models import EntitlementStatus, GuestEntitlement, StorePlatform, StorePurchase, SubscriptionEntitlement
from apps.filehandler.models import AdhdContent
from apps.progresstracker.models import ProgressTracker, UserAssessmentDetails
from apps.payments.services import (
    _apple_api_signed_transaction,
    _google_service,
    save_verified_purchase,
    verify_apple_purchase,
    verify_google_purchase,
)
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
def test_guest_android_verification_returns_entitlement_token(client, user):
    purchase = StorePurchase.objects.create(user=user, **verified_purchase(user))
    entitlement = SubscriptionEntitlement.objects.create(
        user=user, platform=purchase.platform, product_id=purchase.product_id,
        status=purchase.status, expires_at=purchase.expires_at, source_purchase=purchase,
    )
    with patch('apps.payments.views.verify_guest_purchase', return_value=(entitlement, 'guest-token')):
        response = client.post(
            '/api/payments/v1/payments/verify-in-app-purchase/',
            {'platform': 'android', 'product_id': 'attentionminder.monthly', 'purchase_token': 'token'},
            format='json',
        )
    assert response.status_code == 200
    assert response.data['data']['entitlement_token'] == 'guest-token'


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_guest_apple_verification_returns_entitlement_token(client):
    decoded = _apple_decoded_transaction(MagicMock(pk=1))
    decoded.pop('appAccountToken')
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'sandbox')):
        response = client.post(
            '/api/payments/v1/payments/verify-in-app-purchase/',
            {'platform': 'ios', 'product_id': 'attentionminder.monthly',
             'transaction_id': 'apple-transaction-123',
             'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def'},
            format='json',
        )
    assert response.status_code == 200
    assert response.data['data']['verified'] is True
    assert response.data['data']['is_guest'] is True
    assert response.data['data']['entitlement_token']
    entitlement = client.get(
        '/api/payments/v1/payments/entitlement/',
        HTTP_X_ENTITLEMENT_TOKEN=response.data['data']['entitlement_token'],
    )
    assert entitlement.status_code == 200
    assert entitlement.data['data']['is_guest'] is True


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


def _apple_decoded_transaction(user, **overrides):
    now = timezone.now()
    app_account_token = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{"attentionminder.trufoxai.com"}:{user.pk}'))
    payload = {
        'productId': 'attentionminder.monthly',
        'bundleId': 'attentionminder.trufoxai.com',
        'purchaseDate': (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expiresDate': (now + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'transactionId': 'apple-transaction-123',
        'originalTransactionId': 'apple-original-123',
        'appAccountToken': app_account_token,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_production_verification_returns_entitlement(user):
    decoded = _apple_decoded_transaction(user)
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'production')):
        result = verify_apple_purchase(user, {
            'platform': 'ios',
            'product_id': 'attentionminder.monthly',
            'transaction_id': 'apple-transaction-123',
            'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def',
        })

    assert result['platform'] == StorePlatform.IOS
    assert result['status'] == EntitlementStatus.ACTIVE
    assert result['environment'] == 'production'


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_sandbox_verification_uses_sandbox_environment(user):
    decoded = _apple_decoded_transaction(user)
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'sandbox')):
        result = verify_apple_purchase(user, {
            'platform': 'ios',
            'product_id': 'attentionminder.monthly',
            'transaction_id': 'apple-transaction-456',
            'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def',
        })

    assert result['environment'] == 'sandbox'
    assert result['status'] == EntitlementStatus.ACTIVE


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_transaction_lookup_is_used_when_verification_data_missing(user):
    decoded = _apple_decoded_transaction(user)
    with patch('apps.payments.services._apple_api_signed_transaction', return_value='signed.jwt') as api_lookup, \
         patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'production')):
        verify_apple_purchase(user, {
            'platform': 'ios',
            'product_id': 'attentionminder.monthly',
            'transaction_id': 'apple-transaction-789',
            'verification_data': '',
        })

    api_lookup.assert_called_once_with('apple-transaction-789', 'production')


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_malformed_verification_data_falls_back_to_lookup(user):
    with patch('apps.payments.services._apple_api_signed_transaction', return_value=None):
        with pytest.raises(ValidationError) as exc_info:
            verify_apple_purchase(user, {
                'platform': 'ios',
                'product_id': 'attentionminder.monthly',
                'transaction_id': 'apple-transaction-404',
                'verification_data': 'not-a-jws',
            })

    assert 'Apple could not find this transaction' in str(exc_info.value)


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_wrong_product_id_is_rejected(user):
    decoded = _apple_decoded_transaction(user, productId='other.product')
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'production')):
        with pytest.raises(ValidationError) as exc_info:
            verify_apple_purchase(user, {
                'platform': 'ios',
                'product_id': 'attentionminder.monthly',
                'transaction_id': 'apple-transaction-999',
                'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def',
            })

    assert 'Product does not match the Apple transaction' in str(exc_info.value)


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_wrong_bundle_id_is_rejected(user):
    decoded = _apple_decoded_transaction(user, bundleId='com.example.app')
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'production')):
        with pytest.raises(ValidationError) as exc_info:
            verify_apple_purchase(user, {
                'platform': 'ios',
                'product_id': 'attentionminder.monthly',
                'transaction_id': 'apple-transaction-998',
                'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def',
            })

    assert 'bundle ID does not match' in str(exc_info.value)


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_expired_transaction_is_rejected(user):
    decoded = _apple_decoded_transaction(user, expiresDate=(timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'production')):
        with pytest.raises(ValidationError) as exc_info:
            verify_apple_purchase(user, {
                'platform': 'ios',
                'product_id': 'attentionminder.monthly',
                'transaction_id': 'apple-transaction-997',
                'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def',
            })

    assert 'expired' in str(exc_info.value)


@pytest.mark.django_db
@override_settings(APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_revoked_transaction_is_rejected(user):
    decoded = _apple_decoded_transaction(user, revocationDate=(timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))
    with patch('apps.payments.services._verify_apple_jws', return_value=(decoded, 'production')):
        with pytest.raises(ValidationError) as exc_info:
            verify_apple_purchase(user, {
                'platform': 'ios',
                'product_id': 'attentionminder.monthly',
                'transaction_id': 'apple-transaction-996',
                'verification_data': 'eyJhbGciOiJFUzI1NiJ9.abc.def',
            })

    assert 'revoked' in str(exc_info.value)


@override_settings(APPLE_IAP_PRIVATE_KEY_FILE='', APPLE_IAP_KEY_ID='key', APPLE_IAP_ISSUER_ID='issuer', APPLE_BUNDLE_ID='attentionminder.trufoxai.com')
def test_apple_missing_private_key_file_raises_improperly_configured():
    with pytest.raises(ImproperlyConfigured):
        _apple_api_signed_transaction('transaction-123', 'production')


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


@pytest.mark.django_db
@override_settings(GOOGLE_PLAY_PACKAGE_NAME='com.trufox.attentionminder')
def test_google_http_error_is_logged_without_purchase_token(user, caplog):
    http_error = HttpError(
        HttpResponse({'status': '401'}),
        b'{"error":{"code":401,"message":"Invalid Credentials"}}',
    )
    execute = MagicMock(side_effect=http_error)
    get = MagicMock(return_value=MagicMock(execute=execute))
    service = MagicMock()
    service.purchases.return_value.subscriptionsv2.return_value.get = get

    with patch('apps.payments.services._google_service', return_value=service):
        with pytest.raises(Exception) as exc_info:
            verify_google_purchase(user, {
                'product_id': 'attentionminder.monthly',
                'purchase_token': 'secret-server-verification-token',
            })

    assert 'Google Play could not verify this purchase' in str(exc_info.value)
    assert 'status=401' in caplog.text
    assert 'Invalid Credentials' in caplog.text
    assert 'secret-server-verification-token' not in caplog.text


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


@pytest.mark.django_db
def test_guest_token_accesses_premium_content_and_expiry_revokes_access(client):
    guest_user = Users.objects.create_user(username='guest-content', email=None, is_verified=True)
    purchase = StorePurchase.objects.create(
        user=guest_user, platform=StorePlatform.IOS, product_id='attentionminder.monthly',
        store_purchase_id='apple-original-content', original_transaction_id='apple-original-content',
        latest_transaction_id='apple-latest-content', status=EntitlementStatus.ACTIVE,
        expires_at=timezone.now() + timedelta(days=30),
    )
    SubscriptionEntitlement.objects.create(
        user=guest_user, platform=purchase.platform, product_id=purchase.product_id,
        status=purchase.status, expires_at=purchase.expires_at, source_purchase=purchase,
    )
    raw_token = 'secure-guest-content-token'
    GuestEntitlement.objects.create(
        purchase=purchase, backing_user=guest_user,
        token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
        token_expires_at=timezone.now() + timedelta(days=30),
    )
    UserAssessmentDetails.objects.create(
        user=guest_user, last_completed=1, last_completed_at=timezone.now() - timedelta(days=1),
    )
    content = AdhdContent.objects.create(
        title='Premium Day 2', is_management=True, age_group='adult', day=2,
        file_type='video', order_number=1, status='published',
    )
    response = client.get(
        f'/api/content/v1/contents/{content.pk}', HTTP_AUTHORIZATION=f'Bearer {raw_token}'
    )
    assert response.status_code == 200
    purchase.expires_at = timezone.now() - timedelta(seconds=1)
    purchase.status = EntitlementStatus.EXPIRED
    purchase.save(update_fields=['expires_at', 'status'])
    response = client.get(
        f'/api/content/v1/contents/{content.pk}', HTTP_AUTHORIZATION=f'Bearer {raw_token}'
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_guest_entitlement_and_progress_link_to_registered_account(authed_client, user):
    guest_user = Users.objects.create_user(username='guest-link', email=None, is_verified=True)
    purchase = StorePurchase.objects.create(
        user=guest_user, platform=StorePlatform.IOS, product_id='attentionminder.monthly',
        store_purchase_id='apple-original-link', original_transaction_id='apple-original-link',
        latest_transaction_id='apple-latest-link', status=EntitlementStatus.ACTIVE,
        expires_at=timezone.now() + timedelta(days=30),
    )
    SubscriptionEntitlement.objects.create(
        user=guest_user, platform=purchase.platform, product_id=purchase.product_id,
        status=purchase.status, expires_at=purchase.expires_at, source_purchase=purchase,
    )
    ProgressTracker.objects.create(user=guest_user, day_number=1, file_type='video', order_number='1')
    raw_token = 'secure-guest-link-token'
    guest = GuestEntitlement.objects.create(
        purchase=purchase, backing_user=guest_user,
        token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
        token_expires_at=timezone.now() + timedelta(days=30),
    )
    response = authed_client.post(
        '/api/payments/v1/payments/link-guest-entitlement/',
        {'entitlement_token': raw_token}, format='json',
    )
    assert response.status_code == 200
    purchase.refresh_from_db()
    guest.refresh_from_db()
    assert purchase.user == user
    assert guest.linked_user == user
    assert guest.revoked_at is not None
    assert ProgressTracker.objects.filter(user=user, day_number=1).exists()
