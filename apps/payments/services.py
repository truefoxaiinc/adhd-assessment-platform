from datetime import datetime, timezone as datetime_timezone
from urllib.parse import urlparse

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.payments.models import (
    PaymentInvoice,
    StripeCustomer,
    StripeWebhookEvent,
    Subscription,
    SubscriptionStatus,
)

SUPPORTED_WEBHOOK_EVENTS = {
    'checkout.session.completed',
    'customer.subscription.created',
    'customer.subscription.updated',
    'customer.subscription.deleted',
    'invoice.payment_succeeded',
    'invoice.payment_failed',
}


def _stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise ImproperlyConfigured('STRIPE_SECRET_KEY is not configured')
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _timestamp_to_datetime(value):
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=datetime_timezone.utc)


def _get_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_plain_dict(obj):
    if hasattr(obj, 'to_dict_recursive'):
        return obj.to_dict_recursive()
    if isinstance(obj, dict):
        return {
            key: _to_plain_dict(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_to_plain_dict(value) for value in obj]
    return obj


def _validate_redirect_url(url, fallback):
    candidate = (url or fallback or '').strip()
    if not candidate:
        raise ValidationError({'redirect_url': 'Redirect URL is not configured'})

    parsed = urlparse(candidate)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValidationError({'redirect_url': 'Redirect URL must be absolute'})

    allowed_hosts = set(getattr(settings, 'STRIPE_ALLOWED_REDIRECT_HOSTS', []))
    if allowed_hosts and parsed.netloc not in allowed_hosts:
        raise ValidationError({'redirect_url': 'Redirect URL host is not allowed'})
    return candidate


def get_or_create_stripe_customer(user):
    existing = StripeCustomer.objects.filter(user=user).first()
    if existing:
        return existing

    client = _stripe()
    customer = client.Customer.create(
        email=user.email,
        name=user.username or user.email,
        metadata={
            'user_id': str(user.id),
            'environment': settings.DJANGO_ENV,
        },
    )
    return StripeCustomer.objects.create(user=user, stripe_customer_id=customer.id)


def create_checkout_session(user, success_url=None, cancel_url=None):
    if not settings.STRIPE_MONTHLY_PRICE_ID:
        raise ImproperlyConfigured('STRIPE_MONTHLY_PRICE_ID is not configured')

    success_url = _validate_redirect_url(success_url, settings.STRIPE_SUCCESS_URL)
    cancel_url = _validate_redirect_url(cancel_url, settings.STRIPE_CANCEL_URL)
    customer = get_or_create_stripe_customer(user)
    client = _stripe()

    session = client.checkout.Session.create(
        mode='subscription',
        customer=customer.stripe_customer_id,
        line_items=[{'price': settings.STRIPE_MONTHLY_PRICE_ID, 'quantity': 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(user.id),
        metadata={
            'user_id': str(user.id),
            'email': user.email or '',
            'environment': settings.DJANGO_ENV,
        },
        subscription_data={
            'metadata': {
                'user_id': str(user.id),
                'email': user.email or '',
                'environment': settings.DJANGO_ENV,
            },
        },
    )
    return {'checkout_url': session.url, 'session_id': session.id}


def create_billing_portal_session(user, return_url=None):
    return_url = _validate_redirect_url(return_url, settings.STRIPE_BILLING_PORTAL_RETURN_URL)
    customer = get_or_create_stripe_customer(user)
    client = _stripe()
    session = client.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=return_url,
    )
    return {'portal_url': session.url}


def construct_webhook_event(payload, signature):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise ImproperlyConfigured('STRIPE_WEBHOOK_SECRET is not configured')
    return _stripe().Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)


def _find_user_from_customer_or_metadata(stripe_customer_id=None, metadata=None):
    user_id = (metadata or {}).get('user_id')
    User = get_user_model()
    if user_id:
        user = User.objects.filter(id=user_id).first()
        if user:
            return user

    if stripe_customer_id:
        customer = StripeCustomer.objects.select_related('user').filter(stripe_customer_id=stripe_customer_id).first()
        if customer:
            return customer.user
    return None


def _subscription_price_id(subscription):
    items = _get_value(subscription, 'items')
    data = _get_value(items, 'data', []) if items else []
    if not data:
        return ''
    price = _get_value(data[0], 'price', {})
    return _get_value(price, 'id', '') or ''


def _upsert_subscription(subscription, fallback_user=None):
    stripe_customer_id = _get_value(subscription, 'customer')
    stripe_subscription_id = _get_value(subscription, 'id')
    if not stripe_subscription_id:
        return None

    user = fallback_user or _find_user_from_customer_or_metadata(
        stripe_customer_id=stripe_customer_id,
        metadata=_get_value(subscription, 'metadata', {}),
    )
    if not user:
        return None

    status = _get_value(subscription, 'status') or SubscriptionStatus.INCOMPLETE

    subscription_record, _ = Subscription.objects.update_or_create(
        user=user,
        defaults={
            'stripe_customer_id': stripe_customer_id or '',
            'stripe_subscription_id': stripe_subscription_id,
            'stripe_price_id': _subscription_price_id(subscription),
            'status': status,
            'current_period_start': _timestamp_to_datetime(_get_value(subscription, 'current_period_start')),
            'current_period_end': _timestamp_to_datetime(_get_value(subscription, 'current_period_end')),
            'cancel_at_period_end': bool(_get_value(subscription, 'cancel_at_period_end', False)),
            'canceled_at': _timestamp_to_datetime(_get_value(subscription, 'canceled_at')),
        },
    )
    return subscription_record


def _handle_checkout_session_completed(session):
    stripe_customer_id = _get_value(session, 'customer')
    stripe_subscription_id = _get_value(session, 'subscription')
    user = _find_user_from_customer_or_metadata(
        stripe_customer_id=stripe_customer_id,
        metadata=_get_value(session, 'metadata', {}),
    )
    if not user:
        return

    StripeCustomer.objects.update_or_create(
        user=user,
        defaults={'stripe_customer_id': stripe_customer_id},
    )

    if stripe_subscription_id:
        subscription = _stripe().Subscription.retrieve(stripe_subscription_id)
        _upsert_subscription(subscription, fallback_user=user)


def _handle_subscription_deleted(subscription):
    record = _upsert_subscription(subscription)
    if record and record.status != SubscriptionStatus.DELETED:
        record.status = SubscriptionStatus.DELETED
        record.canceled_at = record.canceled_at or timezone.now()
        record.save(update_fields=['status', 'canceled_at', 'updated_at'])


def _handle_invoice(invoice):
    stripe_subscription_id = _get_value(invoice, 'subscription')
    subscription = Subscription.objects.select_related('user').filter(
        stripe_subscription_id=stripe_subscription_id,
    ).first()
    user = subscription.user if subscription else _find_user_from_customer_or_metadata(
        stripe_customer_id=_get_value(invoice, 'customer'),
    )
    if not user:
        return

    PaymentInvoice.objects.update_or_create(
        stripe_invoice_id=_get_value(invoice, 'id'),
        defaults={
            'user': user,
            'stripe_subscription_id': stripe_subscription_id,
            'amount_paid': _get_value(invoice, 'amount_paid', 0) or 0,
            'currency': _get_value(invoice, 'currency', '') or '',
            'status': _get_value(invoice, 'status', '') or '',
            'hosted_invoice_url': _get_value(invoice, 'hosted_invoice_url'),
            'invoice_pdf': _get_value(invoice, 'invoice_pdf'),
            'paid_at': _timestamp_to_datetime(_get_value(_get_value(invoice, 'status_transitions', {}), 'paid_at')),
        },
    )


@transaction.atomic
def process_webhook_event(event):
    event = _to_plain_dict(event)
    event_type = _get_value(event, 'type')
    stripe_event_id = _get_value(event, 'id')
    if not stripe_event_id:
        raise ValueError('Stripe event id is missing')
    data_object = _get_value(_get_value(event, 'data', {}), 'object', {})

    webhook_event, created = StripeWebhookEvent.objects.select_for_update().get_or_create(
        stripe_event_id=stripe_event_id,
        defaults={
            'event_type': event_type,
            'raw_payload': event,
        },
    )
    if not created and webhook_event.processed:
        return {'duplicate': True}

    webhook_event.event_type = event_type
    webhook_event.raw_payload = event
    webhook_event.save(update_fields=['event_type', 'raw_payload'])

    try:
        if event_type not in SUPPORTED_WEBHOOK_EVENTS:
            pass
        elif event_type == 'checkout.session.completed':
            _handle_checkout_session_completed(data_object)
        elif event_type in {'customer.subscription.created', 'customer.subscription.updated'}:
            _upsert_subscription(data_object)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(data_object)
        elif event_type in {'invoice.payment_succeeded', 'invoice.payment_failed'}:
            _handle_invoice(data_object)
        webhook_event.mark_processed()
    except Exception as exc:
        webhook_event.mark_failed(str(exc))
        raise

    return {'duplicate': False}
