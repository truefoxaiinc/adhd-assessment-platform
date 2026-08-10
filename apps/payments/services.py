import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.payments.models import (
    EntitlementStatus,
    StoreNotificationEvent,
    StorePlatform,
    StorePurchase,
    SubscriptionEntitlement,
)


GOOGLE_ACTIVE_STATES = {
    'SUBSCRIPTION_STATE_ACTIVE',
    'SUBSCRIPTION_STATE_IN_GRACE_PERIOD',
}


def _validate_product_id(product_id):
    allowed = set(getattr(settings, 'STORE_ALLOWED_PRODUCT_IDS', []))
    if not allowed:
        raise ImproperlyConfigured('STORE_ALLOWED_PRODUCT_IDS is not configured')
    if product_id not in allowed:
        raise ValidationError({'product_id': 'This subscription product is not supported.'})


def _dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime_timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=datetime_timezone.utc)
    parsed = parse_datetime(str(value))
    return parsed if parsed and parsed.tzinfo else (parsed.replace(tzinfo=datetime_timezone.utc) if parsed else None)


def _value(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _expected_account_id(user):
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        f'in-app-purchase:{user.pk}'.encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest


def purchase_account_identifiers(user):
    import uuid

    namespace = getattr(settings, 'APPLE_APP_ACCOUNT_TOKEN_NAMESPACE', '')
    if namespace:
        apple_token = str(uuid.uuid5(uuid.UUID(namespace), str(user.pk)))
    else:
        apple_token = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{settings.APPLE_BUNDLE_ID}:{user.pk}'))
    return {
        'google_obfuscated_account_id': _expected_account_id(user),
        'apple_app_account_token': apple_token,
    }


def _google_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    scopes = ['https://www.googleapis.com/auth/androidpublisher']
    credentials_json = getattr(settings, 'GOOGLE_PLAY_SERVICE_ACCOUNT_JSON', '')
    credentials_file = getattr(settings, 'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE', '')
    if credentials_json:
        try:
            credentials = service_account.Credentials.from_service_account_info(json.loads(credentials_json), scopes=scopes)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ImproperlyConfigured('GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is invalid') from exc
    elif credentials_file:
        credentials = service_account.Credentials.from_service_account_file(credentials_file, scopes=scopes)
    else:
        raise ImproperlyConfigured('Google Play service-account credentials are not configured')
    return build('androidpublisher', 'v3', credentials=credentials, cache_discovery=False)


def verify_google_purchase(user, attrs, allow_inactive=False):
    package_name = settings.GOOGLE_PLAY_PACKAGE_NAME
    if not package_name:
        raise ImproperlyConfigured('GOOGLE_PLAY_PACKAGE_NAME is not configured')
    token = attrs['purchase_token']
    service = _google_service()
    try:
        payload = service.purchases().subscriptionsv2().get(
            packageName=package_name,
            token=token,
        ).execute()
    except Exception as exc:
        raise ValidationError({'verification_data': 'Google Play could not verify this purchase.'}) from exc

    line_items = payload.get('lineItems') or []
    matching = [item for item in line_items if item.get('productId') == attrs['product_id']]
    if not matching:
        raise ValidationError({'product_id': 'Product does not match the Google Play purchase.'})
    expiry = max((_dt(item.get('expiryTime')) for item in matching), default=None)
    state = payload.get('subscriptionState', '')
    is_active = state in GOOGLE_ACTIVE_STATES and bool(expiry and expiry > timezone.now())
    if not allow_inactive and not is_active:
        raise ValidationError({'verification_data': 'Google Play subscription is not active.'})

    status_by_state = {
        'SUBSCRIPTION_STATE_IN_GRACE_PERIOD': EntitlementStatus.GRACE_PERIOD,
        'SUBSCRIPTION_STATE_PAUSED': EntitlementStatus.PAUSED,
        'SUBSCRIPTION_STATE_CANCELED': EntitlementStatus.CANCELED,
        'SUBSCRIPTION_STATE_EXPIRED': EntitlementStatus.EXPIRED,
        'SUBSCRIPTION_STATE_PENDING': EntitlementStatus.PENDING,
    }

    external_ids = payload.get('externalAccountIdentifiers') or {}
    linked_account = external_ids.get('obfuscatedExternalAccountId')
    if linked_account and not hmac.compare_digest(linked_account, _expected_account_id(user)):
        raise ValidationError({'verification_data': 'Google Play purchase belongs to another account.'})
    if getattr(settings, 'STORE_REQUIRE_ACCOUNT_ASSOCIATION', False) and not linked_account:
        raise ValidationError({'verification_data': 'Google Play purchase has no application account association.'})

    return {
        'platform': StorePlatform.ANDROID,
        'store_purchase_id': token,
        'original_transaction_id': payload.get('linkedPurchaseToken') or token,
        'latest_transaction_id': payload.get('latestOrderId') or attrs.get('purchase_id', ''),
        'product_id': attrs['product_id'],
        'environment': 'test' if payload.get('testPurchase') is not None else 'production',
        'status': status_by_state.get(state, EntitlementStatus.ACTIVE if is_active else EntitlementStatus.EXPIRED),
        'purchased_at': _dt(payload.get('startTime')),
        'expires_at': expiry,
        'auto_renewing': any(bool(item.get('autoRenewingPlan', {}).get('autoRenewEnabled')) for item in matching),
        'raw_verification_response': payload,
    }


def _apple_root_certificates():
    paths = getattr(settings, 'APPLE_ROOT_CERTIFICATE_FILES', [])
    if not paths:
        raise ImproperlyConfigured('APPLE_ROOT_CERTIFICATE_FILES is not configured')
    return [Path(path).read_bytes() for path in paths]


def _apple_verifier(environment):
    from appstoreserverlibrary.models.Environment import Environment
    from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

    env = Environment.PRODUCTION if environment == 'production' else Environment.SANDBOX
    app_id = getattr(settings, 'APPLE_APP_ID', None) if environment == 'production' else None
    return SignedDataVerifier(
        _apple_root_certificates(),
        True,
        env,
        settings.APPLE_BUNDLE_ID,
        int(app_id) if app_id else None,
    )


def _verify_apple_jws(signed_transaction):
    from appstoreserverlibrary.signed_data_verifier import VerificationException

    errors = []
    for environment in ('production', 'sandbox'):
        try:
            return _apple_verifier(environment).verify_and_decode_signed_transaction(signed_transaction), environment
        except VerificationException as exc:
            errors.append(exc)
    raise ValidationError({'verification_data': 'Apple could not verify this signed transaction.'}) from errors[-1]


def _apple_api_signed_transaction(transaction_id, environment):
    from appstoreserverlibrary.api_client import AppStoreServerAPIClient, APIException
    from appstoreserverlibrary.models.Environment import Environment

    private_key_file = getattr(settings, 'APPLE_IAP_PRIVATE_KEY_FILE', '')
    if not all([private_key_file, settings.APPLE_IAP_KEY_ID, settings.APPLE_IAP_ISSUER_ID]):
        raise ImproperlyConfigured('Apple App Store Server API credentials are not configured')
    env = Environment.PRODUCTION if environment == 'production' else Environment.SANDBOX
    client = AppStoreServerAPIClient(
        Path(private_key_file).read_bytes(),
        settings.APPLE_IAP_KEY_ID,
        settings.APPLE_IAP_ISSUER_ID,
        settings.APPLE_BUNDLE_ID,
        env,
    )
    try:
        return client.get_transaction_info(transaction_id).signedTransactionInfo
    except APIException:
        return None


def verify_apple_purchase(user, attrs, allow_inactive=False):
    if not settings.APPLE_BUNDLE_ID:
        raise ImproperlyConfigured('APPLE_BUNDLE_ID is not configured')
    signed_transaction = attrs.get('verification_data', '')
    # Flutter may provide a legacy base64 app receipt here. The modern Apple
    # verifier expects a compact JWS; use the transaction ID API for receipts.
    if signed_transaction.count('.') != 2:
        signed_transaction = ''
    if not signed_transaction:
        for environment in ('production', 'sandbox'):
            signed_transaction = _apple_api_signed_transaction(attrs['transaction_id'], environment)
            if signed_transaction:
                break
        if not signed_transaction:
            raise ValidationError({'transaction_id': 'Apple could not find this transaction.'})
    decoded, environment = _verify_apple_jws(signed_transaction)

    product_id = _value(decoded, 'productId')
    if product_id != attrs['product_id']:
        raise ValidationError({'product_id': 'Product does not match the Apple transaction.'})
    bundle_id = _value(decoded, 'bundleId')
    if bundle_id and bundle_id != settings.APPLE_BUNDLE_ID:
        raise ValidationError({'verification_data': 'Apple transaction bundle ID does not match.'})
    expires_at = _dt(_value(decoded, 'expiresDate'))
    revocation_date = _dt(_value(decoded, 'revocationDate'))
    if revocation_date and not allow_inactive:
        raise ValidationError({'verification_data': 'Apple transaction was revoked.'})
    if (not expires_at or expires_at <= timezone.now()) and not allow_inactive:
        raise ValidationError({'verification_data': 'Apple subscription is expired.'})

    app_account_token = str(_value(decoded, 'appAccountToken') or '')
    import uuid

    configured_namespace = getattr(settings, 'APPLE_APP_ACCOUNT_TOKEN_NAMESPACE', '')
    if configured_namespace:
        expected_account = str(uuid.uuid5(uuid.UUID(configured_namespace), str(user.pk)))
    else:
        expected_account = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{settings.APPLE_BUNDLE_ID}:{user.pk}'))
    if app_account_token and app_account_token != expected_account:
        raise ValidationError({'verification_data': 'Apple transaction belongs to another account.'})
    if getattr(settings, 'STORE_REQUIRE_ACCOUNT_ASSOCIATION', False) and not app_account_token:
        raise ValidationError({'verification_data': 'Apple transaction has no application account association.'})

    transaction_id = str(_value(decoded, 'transactionId') or attrs.get('transaction_id') or '')
    return {
        'platform': StorePlatform.IOS,
        'store_purchase_id': str(_value(decoded, 'originalTransactionId') or transaction_id),
        'original_transaction_id': str(_value(decoded, 'originalTransactionId') or transaction_id),
        'latest_transaction_id': transaction_id,
        'product_id': product_id,
        'environment': environment,
        'status': (
            EntitlementStatus.REVOKED if revocation_date
            else EntitlementStatus.ACTIVE if expires_at and expires_at > timezone.now()
            else EntitlementStatus.EXPIRED
        ),
        'purchased_at': _dt(_value(decoded, 'purchaseDate')),
        'expires_at': expires_at,
        'auto_renewing': True,
        'raw_verification_response': {
            'transaction_id': transaction_id,
            'original_transaction_id': str(_value(decoded, 'originalTransactionId') or ''),
            'product_id': product_id,
            'environment': environment,
        },
    }


@transaction.atomic
def save_verified_purchase(user, verified, is_restore=False):
    existing = StorePurchase.objects.select_for_update().filter(
        platform=verified['platform'], store_purchase_id=verified['store_purchase_id']
    ).first()
    if existing and existing.user_id != user.pk:
        raise ValidationError({'verification_data': 'This store purchase is already linked to another account.'})
    purchase, _ = StorePurchase.objects.update_or_create(
        platform=verified['platform'],
        store_purchase_id=verified['store_purchase_id'],
        defaults={**verified, 'user': user, 'is_restore': is_restore},
    )
    entitlement, _ = SubscriptionEntitlement.objects.update_or_create(
        user=user,
        defaults={
            'platform': purchase.platform,
            'product_id': purchase.product_id,
            'status': purchase.status,
            'expires_at': purchase.expires_at,
            'source_purchase': purchase,
        },
    )
    return entitlement


def verify_in_app_purchase(user, attrs):
    _validate_product_id(attrs['product_id'])
    verified = verify_google_purchase(user, attrs) if attrs['platform'] == StorePlatform.ANDROID else verify_apple_purchase(user, attrs)
    return save_verified_purchase(user, verified, attrs.get('is_restore', False))


def decode_google_rtdn(payload):
    message = payload['message']
    try:
        data = json.loads(base64.b64decode(message['data']).decode())
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError({'message': 'Invalid Google RTDN payload.'}) from exc
    return message.get('messageId') or hashlib.sha256(message['data'].encode()).hexdigest(), data


@transaction.atomic
def process_google_rtdn(payload):
    event_id, data = decode_google_rtdn(payload)
    event, created = StoreNotificationEvent.objects.select_for_update().get_or_create(
        platform=StorePlatform.ANDROID, event_id=event_id,
        defaults={'event_type': 'subscriptionNotification', 'raw_payload': payload},
    )
    if not created and event.processed:
        return True
    notification = data.get('subscriptionNotification') or {}
    token = notification.get('purchaseToken')
    purchase = StorePurchase.objects.select_related('user').filter(platform=StorePlatform.ANDROID, store_purchase_id=token).first()
    if purchase:
        attrs = {'platform': 'android', 'product_id': purchase.product_id, 'purchase_token': token}
        save_verified_purchase(purchase.user, verify_google_purchase(purchase.user, attrs, allow_inactive=True))
    event.processed = True
    event.processed_at = timezone.now()
    event.save(update_fields=['processed', 'processed_at'])
    return False


@transaction.atomic
def process_apple_notification(signed_payload):
    from appstoreserverlibrary.signed_data_verifier import VerificationException

    decoded = None
    environment = None
    for candidate in ('production', 'sandbox'):
        try:
            decoded = _apple_verifier(candidate).verify_and_decode_notification(signed_payload)
            environment = candidate
            break
        except VerificationException:
            continue
    if decoded is None:
        raise ValidationError({'signedPayload': 'Invalid Apple notification signature.'})
    event_id = str(_value(decoded, 'notificationUUID'))
    event, created = StoreNotificationEvent.objects.select_for_update().get_or_create(
        platform=StorePlatform.IOS, event_id=event_id,
        defaults={'event_type': str(_value(decoded, 'notificationType') or ''), 'raw_payload': {'environment': environment}},
    )
    if not created and event.processed:
        return True
    data = _value(decoded, 'data')
    signed_transaction = _value(data, 'signedTransactionInfo') if data else None
    if signed_transaction:
        transaction, _ = _verify_apple_jws(signed_transaction)
        original_id = str(_value(transaction, 'originalTransactionId') or '')
        purchase = StorePurchase.objects.select_related('user').filter(platform=StorePlatform.IOS, original_transaction_id=original_id).first()
        if purchase:
            attrs = {'platform': 'ios', 'product_id': _value(transaction, 'productId'), 'verification_data': signed_transaction}
            save_verified_purchase(purchase.user, verify_apple_purchase(purchase.user, attrs, allow_inactive=True))
    event.processed = True
    event.processed_at = timezone.now()
    event.save(update_fields=['processed', 'processed_at'])
    return False
