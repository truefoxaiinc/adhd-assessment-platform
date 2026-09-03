import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from googleapiclient.errors import HttpError

from apps.payments.models import (
    EntitlementStatus,
    GuestEntitlement,
    StoreNotificationEvent,
    StorePlatform,
    StorePurchase,
    SubscriptionEntitlement,
)


logger = logging.getLogger(__name__)


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


def _mask_transaction_id(value):
    if value is None:
        return ''
    value = str(value).strip()
    if not value:
        return ''
    if len(value) <= 8:
        return value[:2] + '***' if len(value) > 4 else '***'
    return value[:8] + '...'


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
    credentials_json = getattr(settings, 'GOOGLE_PLAY_SERVICE_ACCOUNT_JSON', '').strip()
    credentials_file = getattr(settings, 'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE', '').strip()
    if credentials_json and credentials_file:
        raise ImproperlyConfigured(
            'Configure only one of GOOGLE_PLAY_SERVICE_ACCOUNT_JSON or '
            'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE'
        )

    if credentials_json:
        try:
            service_account_info = json.loads(credentials_json)
            if not isinstance(service_account_info, dict):
                raise ValueError('Service-account JSON must contain an object')
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=scopes,
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ImproperlyConfigured('GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is invalid') from exc
    elif credentials_file:
        credential_path = Path(credentials_file)
        if not credential_path.is_file():
            raise ImproperlyConfigured(
                'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE does not point to a readable file'
            )
        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(credential_path),
                scopes=scopes,
            )
        except (OSError, ValueError, TypeError) as exc:
            raise ImproperlyConfigured(
                'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE contains invalid credentials'
            ) from exc
    else:
        raise ImproperlyConfigured('Google Play service-account credentials are not configured')
    logger.info(
        'Google Play service account: %s',
        credentials.service_account_email,
    )
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
    except HttpError as exc:
        content = exc.content
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        logger.exception(
            'Google Play verification failed: status=%s content=%s',
            getattr(exc.resp, 'status', None),
            content,
        )
        raise ValidationError({'verification_data': 'Google Play could not verify this purchase.'}) from exc
    except Exception as exc:
        logger.exception(
            'Unexpected Google Play verification failure: package=%s error_type=%s',
            package_name,
            type(exc).__name__,
        )
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
    authenticated_user = user and getattr(user, 'is_authenticated', False)
    if authenticated_user and linked_account and not hmac.compare_digest(linked_account, _expected_account_id(user)):
        raise ValidationError({'verification_data': 'Google Play purchase belongs to another account.'})
    if authenticated_user and getattr(settings, 'STORE_REQUIRE_ACCOUNT_ASSOCIATION', False) and not linked_account:
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
            logger.info('Attempting Apple JWS verification: environment=%s', environment)
            return _apple_verifier(environment).verify_and_decode_signed_transaction(signed_transaction), environment
        except VerificationException as exc:
            logger.warning(
                'Apple JWS verification failed: environment=%s error_type=%s',
                environment,
                type(exc).__name__,
            )
            errors.append(exc)
        except Exception as exc:
            logger.exception(
                'Unexpected Apple JWS verification failure: environment=%s error_type=%s',
                environment,
                type(exc).__name__,
            )
            errors.append(exc)
    raise ValidationError({'verification_data': 'Apple could not verify this signed transaction.'}) from errors[-1]


def _apple_api_signed_transaction(transaction_id, environment):
    from appstoreserverlibrary.api_client import AppStoreServerAPIClient, APIException
    from appstoreserverlibrary.models.Environment import Environment

    if not transaction_id or not str(transaction_id).strip():
        raise ValidationError({'transaction_id': 'Apple transaction ID is required for server-side verification.'})

    private_key_file = getattr(settings, 'APPLE_IAP_PRIVATE_KEY_FILE', '').strip()
    if not private_key_file:
        raise ImproperlyConfigured('Apple App Store Server API private key file is not configured')
    if not Path(private_key_file).is_file():
        raise ImproperlyConfigured('Apple App Store Server API private key file is not readable')
    if not settings.APPLE_IAP_KEY_ID or not settings.APPLE_IAP_ISSUER_ID:
        raise ImproperlyConfigured('Apple App Store Server API key ID and issuer ID are not configured')

    try:
        key_bytes = Path(private_key_file).read_bytes()
    except OSError as exc:
        logger.exception('Apple App Store API key file could not be read: path=%s', private_key_file)
        raise ImproperlyConfigured('Apple App Store Server API private key file is not readable') from exc

    env = Environment.PRODUCTION if environment == 'production' else Environment.SANDBOX
    try:
        client = AppStoreServerAPIClient(
            key_bytes,
            settings.APPLE_IAP_KEY_ID,
            settings.APPLE_IAP_ISSUER_ID,
            settings.APPLE_BUNDLE_ID,
            env,
        )
    except (TypeError, ValueError, OSError) as exc:
        logger.exception(
            'Apple App Store API client configuration is invalid: environment=%s transaction_id=%s',
            environment,
            _mask_transaction_id(transaction_id),
        )
        raise ImproperlyConfigured('Apple App Store Server API credentials are invalid') from exc

    try:
        response = client.get_transaction_info(transaction_id)
        return getattr(response, 'signedTransactionInfo', None)
    except APIException as exc:
        status = getattr(exc, 'status_code', None) or getattr(getattr(exc, 'response', None), 'status', None)
        message = getattr(exc, 'message', str(exc))
        if status in {400, 404}:
            logger.warning(
                'Apple transaction lookup returned not found/invalid: environment=%s transaction_id=%s status=%s',
                environment,
                _mask_transaction_id(transaction_id),
                status,
            )
            return None
        logger.warning(
            'Apple App Store API request failed: environment=%s transaction_id=%s status=%s error_type=%s message=%s',
            environment,
            _mask_transaction_id(transaction_id),
            status,
            type(exc).__name__,
            message,
        )
        raise ImproperlyConfigured(
            f'Apple App Store API verification failed: {status or "unknown status"}'
        ) from exc
    except Exception as exc:
        logger.exception(
            'Unexpected Apple App Store API transaction lookup failure: environment=%s transaction_id=%s',
            environment,
            _mask_transaction_id(transaction_id),
        )
        raise ImproperlyConfigured('Apple App Store API verification failed unexpectedly') from exc


def verify_apple_purchase(user, attrs, allow_inactive=False):
    if not settings.APPLE_BUNDLE_ID:
        raise ImproperlyConfigured('APPLE_BUNDLE_ID is not configured')

    product_id = attrs.get('product_id')
    transaction_id = str(attrs.get('transaction_id') or attrs.get('purchase_id') or '')
    signed_transaction = attrs.get('verification_data', '')
    logger.info(
        'Starting Apple purchase verification: product_id=%s transaction_id=%s verification_data_supplied=%s',
        product_id,
        _mask_transaction_id(transaction_id),
        bool(signed_transaction),
    )

    # Flutter may provide a legacy base64 app receipt here. The modern Apple
    # verifier expects a compact JWS; use the transaction ID API for receipts.
    if signed_transaction and signed_transaction.count('.') != 2:
        logger.warning(
            'Apple verification_data is not a signed JWS; attempting transaction lookup: product_id=%s transaction_id=%s',
            product_id,
            _mask_transaction_id(transaction_id),
        )
        signed_transaction = ''
    if not signed_transaction:
        for environment in ('production', 'sandbox'):
            try:
                logger.info(
                    'Looking up Apple transaction via App Store API: environment=%s product_id=%s transaction_id=%s',
                    environment,
                    product_id,
                    _mask_transaction_id(transaction_id),
                )
                signed_transaction = _apple_api_signed_transaction(transaction_id, environment)
            except ImproperlyConfigured:
                raise
            if signed_transaction:
                break
        if not signed_transaction:
            raise ValidationError({'transaction_id': 'Apple could not find this transaction.'})
    decoded, environment = _verify_apple_jws(signed_transaction)

    product_id = _value(decoded, 'productId')
    if product_id != attrs['product_id']:
        logger.warning(
            'Apple product mismatch: expected=%s actual=%s transaction_id=%s',
            attrs.get('product_id'),
            product_id,
            _mask_transaction_id(transaction_id or _value(decoded, 'transactionId')),
        )
        raise ValidationError({'product_id': 'Product does not match the Apple transaction.'})
    bundle_id = _value(decoded, 'bundleId')
    if bundle_id and bundle_id != settings.APPLE_BUNDLE_ID:
        logger.warning(
            'Apple bundle mismatch: expected=%s actual=%s transaction_id=%s',
            settings.APPLE_BUNDLE_ID,
            bundle_id,
            _mask_transaction_id(transaction_id or _value(decoded, 'transactionId')),
        )
        raise ValidationError({'verification_data': 'Apple transaction bundle ID does not match.'})
    expires_at = _dt(_value(decoded, 'expiresDate'))
    revocation_date = _dt(_value(decoded, 'revocationDate'))
    if revocation_date and not allow_inactive:
        raise ValidationError({'verification_data': 'Apple transaction was revoked.'})
    if (not expires_at or expires_at <= timezone.now()) and not allow_inactive:
        raise ValidationError({'verification_data': 'Apple subscription is expired.'})

    app_account_token = str(_value(decoded, 'appAccountToken') or '')
    import uuid

    expected_account = None
    if user and getattr(user, 'is_authenticated', False):
        configured_namespace = getattr(settings, 'APPLE_APP_ACCOUNT_TOKEN_NAMESPACE', '')
        if configured_namespace:
            expected_account = str(uuid.uuid5(uuid.UUID(configured_namespace), str(user.pk)))
        else:
            expected_account = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{settings.APPLE_BUNDLE_ID}:{user.pk}'))
    if expected_account and app_account_token and app_account_token != expected_account:
        logger.warning(
            'Apple appAccountToken mismatch: user_id=%s transaction_id=%s',
            user.pk,
            _mask_transaction_id(transaction_id or _value(decoded, 'transactionId')),
        )
        raise ValidationError({'verification_data': 'Apple transaction belongs to another account.'})
    if expected_account and getattr(settings, 'STORE_REQUIRE_ACCOUNT_ASSOCIATION', False) and not app_account_token:
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


def _token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@transaction.atomic
def verify_guest_purchase(attrs):
    _validate_product_id(attrs['product_id'])
    if attrs['platform'] == StorePlatform.IOS:
        verified = verify_apple_purchase(None, attrs)
        lookup = {'platform': StorePlatform.IOS, 'original_transaction_id': verified['original_transaction_id']}
    else:
        verified = verify_google_purchase(None, attrs)
        lookup = {'platform': StorePlatform.ANDROID, 'store_purchase_id': verified['store_purchase_id']}
    existing = StorePurchase.objects.select_for_update().filter(**lookup).first()
    if existing and not hasattr(existing, 'guest_entitlement'):
        raise ValidationError({'verification_data': 'This store purchase is already linked to an account.'})
    raw_token = secrets.token_urlsafe(48)
    lifetime = timezone.timedelta(days=getattr(settings, 'GUEST_ENTITLEMENT_TOKEN_DAYS', 90))
    if existing:
        purchase = existing
        for field, value in verified.items():
            setattr(purchase, field, value)
        purchase.is_restore = attrs.get('is_restore', False)
        purchase.save()
        entitlement = SubscriptionEntitlement.objects.get(user=purchase.user)
        entitlement.status, entitlement.expires_at = purchase.status, purchase.expires_at
        entitlement.product_id, entitlement.source_purchase = purchase.product_id, purchase
        entitlement.save()
        guest = purchase.guest_entitlement
        guest.token_digest = _token_digest(raw_token)
        guest.token_expires_at = min(purchase.expires_at, timezone.now() + lifetime)
        guest.revoked_at = None
        guest.save()
    else:
        from apps.users.models import Users
        original_id = f"{verified['platform']}:{verified['original_transaction_id']}"
        backing_user = Users.objects.create_user(
            username=f'guest-{hashlib.sha256(original_id.encode()).hexdigest()[:32]}', email=None, is_verified=True
        )
        backing_user.set_unusable_password()
        backing_user.save(update_fields=['password'])
        entitlement = save_verified_purchase(backing_user, verified, attrs.get('is_restore', False))
        GuestEntitlement.objects.create(
            purchase=entitlement.source_purchase, backing_user=backing_user,
            token_digest=_token_digest(raw_token),
            token_expires_at=min(verified['expires_at'], timezone.now() + lifetime),
        )
    return entitlement, raw_token


@transaction.atomic
def link_guest_entitlement(user, raw_token):
    guest = GuestEntitlement.objects.select_for_update().select_related('purchase').filter(
        token_digest=_token_digest(raw_token)
    ).first()
    if not guest or not guest.is_token_active:
        raise ValidationError({'entitlement_token': 'Invalid or expired guest entitlement token.'})
    if guest.linked_user_id and guest.linked_user_id != user.pk:
        raise ValidationError({'entitlement_token': 'This entitlement is already linked to another account.'})
    if guest.linked_user_id == user.pk:
        return SubscriptionEntitlement.objects.get(user=user)
    old_user, purchase = guest.backing_user, guest.purchase
    existing = SubscriptionEntitlement.objects.filter(user=user).first()
    if existing and existing.source_purchase_id != purchase.pk:
        raise ValidationError({'entitlement_token': 'This account already has a different entitlement.'})
    SubscriptionEntitlement.objects.filter(user=old_user).update(user=user)
    purchase.user = user
    purchase.save(update_fields=['user'])
    from apps.progresstracker.models import ProgressTracker, UserAssessmentDetails, ManagementActivitySession
    from apps.filehandler.models import ContentAttempt
    ProgressTracker.objects.filter(user=old_user).update(user=user)
    ManagementActivitySession.objects.filter(user=old_user).update(user=user)
    ContentAttempt.objects.filter(user=old_user).update(user=user)
    assessment = UserAssessmentDetails.objects.filter(user=old_user).first()
    if assessment and not UserAssessmentDetails.objects.filter(user=user).exists():
        assessment.user = user
        assessment.save(update_fields=['user'])
    guest.linked_user, guest.revoked_at = user, timezone.now()
    guest.save(update_fields=['linked_user', 'revoked_at', 'updated_at'])
    return SubscriptionEntitlement.objects.get(user=user)


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
