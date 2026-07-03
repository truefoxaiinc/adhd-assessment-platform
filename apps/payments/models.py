from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SubscriptionStatus(models.TextChoices):
    INCOMPLETE = 'incomplete', _('Incomplete')
    INCOMPLETE_EXPIRED = 'incomplete_expired', _('Incomplete expired')
    TRIALING = 'trialing', _('Trialing')
    ACTIVE = 'active', _('Active')
    PAST_DUE = 'past_due', _('Past due')
    CANCELED = 'canceled', _('Canceled')
    UNPAID = 'unpaid', _('Unpaid')
    PAUSED = 'paused', _('Paused')
    DELETED = 'deleted', _('Deleted')


class StripeCustomer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stripe_customer')
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'StripeCustomer'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['stripe_customer_id']),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.stripe_customer_id}'


class Subscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    stripe_customer_id = models.CharField(max_length=255, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=50, choices=SubscriptionStatus.choices, db_index=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True, db_index=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Subscription'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'current_period_end']),
            models.Index(fields=['stripe_subscription_id']),
        ]

    @property
    def is_active(self):
        return (
            self.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}
            and self.current_period_end is not None
            and self.current_period_end >= timezone.now()
        )

    def __str__(self):
        return f'{self.user_id}:{self.status}'


class PaymentInvoice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_invoices')
    stripe_invoice_id = models.CharField(max_length=255, unique=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    amount_paid = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=50, blank=True, db_index=True)
    hosted_invoice_url = models.URLField(max_length=500, blank=True, null=True)
    invoice_pdf = models.URLField(max_length=500, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'PaymentInvoice'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['stripe_subscription_id']),
        ]

    def __str__(self):
        return self.stripe_invoice_id


class StripeWebhookEvent(models.Model):
    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100, db_index=True)
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    raw_payload = models.JSONField()
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'StripeWebhookEvent'
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['processed', 'created_at']),
        ]

    def mark_processed(self):
        self.processed = True
        self.processed_at = timezone.now()
        self.error = ''
        self.save(update_fields=['processed', 'processed_at', 'error'])

    def mark_failed(self, message):
        self.processed = False
        self.error = message[:4000]
        self.save(update_fields=['processed', 'error'])

    def __str__(self):
        return f'{self.event_type}:{self.stripe_event_id}'
