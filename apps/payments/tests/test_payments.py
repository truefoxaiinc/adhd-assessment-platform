import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.models import PaymentInvoice, StripeCustomer, StripeWebhookEvent, Subscription, SubscriptionStatus
from apps.payments.permissions import HasActiveSubscription
from apps.payments.selectors import user_has_active_subscription
from apps.payments.services import process_webhook_event
from apps.users.models import Users


@pytest.fixture
def user():
    return Users.objects.create_user(
        username='payment_user',
        email='payment@test.com',
        password='Password123!',
        is_verified=True,
    )


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
@override_settings(
    STRIPE_SECRET_KEY='sk_test_123',
    STRIPE_MONTHLY_PRICE_ID='price_monthly',
    STRIPE_SUCCESS_URL='https://app.example.com/success',
    STRIPE_CANCEL_URL='https://app.example.com/cancel',
    STRIPE_ALLOWED_REDIRECT_HOSTS=['app.example.com'],
)
def test_checkout_session_creation(authed_client):
    session = SimpleNamespace(id='cs_test', url='https://checkout.stripe.com/pay/cs_test')
    customer = SimpleNamespace(id='cus_test')
    with patch('apps.payments.services.stripe.Customer.create', return_value=customer), patch(
        'apps.payments.services.stripe.checkout.Session.create',
        return_value=session,
    ) as create_session:
        response = authed_client.post('/api/payments/create-checkout-session/', {}, format='json')

    assert response.status_code == 200
    assert response.data['data']['session_id'] == 'cs_test'
    assert StripeCustomer.objects.filter(stripe_customer_id='cus_test').exists()
    assert create_session.call_args.kwargs['mode'] == 'subscription'


@pytest.mark.django_db
def test_unauthenticated_checkout_blocked(client):
    response = client.post('/api/payments/create-checkout-session/', {}, content_type='application/json')
    assert response.status_code in (401, 403)


def test_payment_result_pages_are_public(client):
    success_response = client.get('/payment/success/')
    cancel_response = client.get('/payment/cancel/')

    assert success_response.status_code == 200
    assert b'Payment successful' in success_response.content
    assert b'attentionminder://payments/success' in success_response.content
    assert cancel_response.status_code == 200
    assert b'Payment cancelled' in cancel_response.content
    assert b'attentionminder://payments/cancel' in cancel_response.content


@pytest.mark.django_db
def test_subscription_status_api(authed_client, user):
    Subscription.objects.create(
        user=user,
        stripe_customer_id='cus_test',
        stripe_subscription_id='sub_test',
        stripe_price_id='price_monthly',
        status=SubscriptionStatus.ACTIVE,
        current_period_end=timezone.now() + timezone.timedelta(days=30),
    )

    response = authed_client.get('/api/payments/subscription/')

    assert response.status_code == 200
    assert response.data['data']['is_active'] is True
    assert response.data['data']['stripe_subscription_id'] == 'sub_test'


@pytest.mark.django_db
@override_settings(
    STRIPE_SECRET_KEY='sk_test_123',
    STRIPE_BILLING_PORTAL_RETURN_URL='https://app.example.com/account',
    STRIPE_ALLOWED_REDIRECT_HOSTS=['app.example.com'],
)
def test_billing_portal_session(authed_client, user):
    StripeCustomer.objects.create(user=user, stripe_customer_id='cus_test')
    portal = SimpleNamespace(url='https://billing.stripe.com/session/test')
    with patch('apps.payments.services.stripe.billing_portal.Session.create', return_value=portal):
        response = authed_client.post('/api/payments/create-billing-portal-session/', {}, format='json')

    assert response.status_code == 200
    assert response.data['data']['portal_url'] == portal.url


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY='sk_test_123', STRIPE_WEBHOOK_SECRET='whsec_test')
def test_webhook_signature_verification(client):
    event = {'id': 'evt_test', 'type': 'customer.subscription.updated', 'data': {'object': {'id': 'sub_missing'}}}
    with patch('apps.payments.services.stripe.Webhook.construct_event', return_value=event) as construct_event:
        response = client.post(
            '/api/payments/webhook/',
            data=json.dumps(event),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=123,v1=sig',
        )

    assert response.status_code == 200
    construct_event.assert_called_once()


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY='sk_test_123')
def test_checkout_session_completed(user):
    StripeCustomer.objects.create(user=user, stripe_customer_id='cus_test')
    stripe_subscription = {
        'id': 'sub_test',
        'customer': 'cus_test',
        'status': 'active',
        'current_period_start': 1_700_000_000,
        'current_period_end': 4_102_444_800,
        'cancel_at_period_end': False,
        'items': {'data': [{'price': {'id': 'price_monthly'}}]},
        'metadata': {'user_id': str(user.id)},
    }
    event = {
        'id': 'evt_checkout',
        'type': 'checkout.session.completed',
        'data': {'object': {'id': 'cs_test', 'customer': 'cus_test', 'subscription': 'sub_test', 'metadata': {'user_id': str(user.id)}}},
    }
    with patch('apps.payments.services.stripe.Subscription.retrieve', return_value=stripe_subscription):
        process_webhook_event(event)

    assert Subscription.objects.get(user=user).stripe_subscription_id == 'sub_test'


@pytest.mark.django_db
def test_subscription_created(user):
    StripeCustomer.objects.create(user=user, stripe_customer_id='cus_test')
    process_webhook_event(_subscription_event('evt_created', 'customer.subscription.created', user))
    assert Subscription.objects.filter(user=user, status='active').exists()


@pytest.mark.django_db
def test_subscription_updated(user):
    StripeCustomer.objects.create(user=user, stripe_customer_id='cus_test')
    process_webhook_event(_subscription_event('evt_updated', 'customer.subscription.updated', user, status='past_due'))
    assert Subscription.objects.get(user=user).status == 'past_due'


@pytest.mark.django_db
def test_subscription_deleted(user):
    StripeCustomer.objects.create(user=user, stripe_customer_id='cus_test')
    process_webhook_event(_subscription_event('evt_deleted', 'customer.subscription.deleted', user, status='canceled'))
    assert Subscription.objects.get(user=user).status == SubscriptionStatus.DELETED


@pytest.mark.django_db
def test_invoice_payment_succeeded(user):
    Subscription.objects.create(
        user=user,
        stripe_customer_id='cus_test',
        stripe_subscription_id='sub_test',
        status='active',
        current_period_end=timezone.now() + timezone.timedelta(days=30),
    )
    process_webhook_event(_invoice_event('evt_invoice_succeeded', 'invoice.payment_succeeded'))
    assert PaymentInvoice.objects.filter(stripe_invoice_id='in_test', status='paid').exists()


@pytest.mark.django_db
def test_invoice_payment_failed(user):
    Subscription.objects.create(
        user=user,
        stripe_customer_id='cus_test',
        stripe_subscription_id='sub_test',
        status='active',
        current_period_end=timezone.now() + timezone.timedelta(days=30),
    )
    event = _invoice_event('evt_invoice_failed', 'invoice.payment_failed')
    event['data']['object']['status'] = 'open'
    process_webhook_event(event)
    assert PaymentInvoice.objects.filter(stripe_invoice_id='in_test', status='open').exists()


@pytest.mark.django_db
def test_duplicate_webhook_event_ignored(user):
    StripeCustomer.objects.create(user=user, stripe_customer_id='cus_test')
    event = _subscription_event('evt_duplicate', 'customer.subscription.created', user)
    assert process_webhook_event(event)['duplicate'] is False
    assert process_webhook_event(event)['duplicate'] is True
    assert StripeWebhookEvent.objects.filter(stripe_event_id='evt_duplicate').count() == 1


@pytest.mark.django_db
def test_active_subscription_permission(user):
    Subscription.objects.create(
        user=user,
        stripe_customer_id='cus_test',
        stripe_subscription_id='sub_test',
        status='trialing',
        current_period_end=timezone.now() + timezone.timedelta(days=1),
    )
    request = SimpleNamespace(user=user)
    assert user_has_active_subscription(user) is True
    assert HasActiveSubscription().has_permission(request, None) is True


@pytest.mark.django_db
def test_expired_subscription_blocked(user):
    Subscription.objects.create(
        user=user,
        stripe_customer_id='cus_test',
        stripe_subscription_id='sub_test',
        status='active',
        current_period_end=timezone.now() - timezone.timedelta(seconds=1),
    )
    assert user_has_active_subscription(user) is False


def _subscription_event(event_id, event_type, user, status='active'):
    return {
        'id': event_id,
        'type': event_type,
        'data': {
            'object': {
                'id': 'sub_test',
                'customer': 'cus_test',
                'status': status,
                'current_period_start': 1_700_000_000,
                'current_period_end': 4_102_444_800,
                'cancel_at_period_end': False,
                'items': {'data': [{'price': {'id': 'price_monthly'}}]},
                'metadata': {'user_id': str(user.id)},
            }
        },
    }


def _invoice_event(event_id, event_type):
    return {
        'id': event_id,
        'type': event_type,
        'data': {
            'object': {
                'id': 'in_test',
                'customer': 'cus_test',
                'subscription': 'sub_test',
                'amount_paid': 999,
                'currency': 'usd',
                'status': 'paid',
                'hosted_invoice_url': 'https://stripe.example/invoice',
                'invoice_pdf': 'https://stripe.example/invoice.pdf',
                'status_transitions': {'paid_at': 1_700_000_000},
            }
        },
    }
