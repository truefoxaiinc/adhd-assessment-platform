from django.conf import settings
from django.db import models
from django.utils import timezone


class StorePlatform(models.TextChoices):
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'


class EntitlementStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    GRACE_PERIOD = 'grace_period', 'Grace period'
    PAUSED = 'paused', 'Paused'
    EXPIRED = 'expired', 'Expired'
    CANCELED = 'canceled', 'Canceled'
    REVOKED = 'revoked', 'Revoked'
    PENDING = 'pending', 'Pending'


class StorePurchase(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='store_purchases')
    platform = models.CharField(max_length=20, choices=StorePlatform.choices)
    product_id = models.CharField(max_length=255, db_index=True)
    store_purchase_id = models.CharField(max_length=512)
    original_transaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    latest_transaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    environment = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=30, choices=EntitlementStatus.choices, db_index=True)
    purchased_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)
    auto_renewing = models.BooleanField(default=False)
    is_restore = models.BooleanField(default=False)
    raw_verification_response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'StorePurchase'
        constraints = [
            models.UniqueConstraint(fields=['platform', 'store_purchase_id'], name='uniq_store_purchase_evidence'),
        ]
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['platform', 'original_transaction_id']),
        ]


class SubscriptionEntitlement(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription_entitlement')
    platform = models.CharField(max_length=20, choices=StorePlatform.choices)
    product_id = models.CharField(max_length=255)
    status = models.CharField(max_length=30, choices=EntitlementStatus.choices, db_index=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)
    source_purchase = models.ForeignKey(StorePurchase, on_delete=models.PROTECT, related_name='entitlements')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'SubscriptionEntitlement'

    @property
    def is_active(self):
        return self.status in {EntitlementStatus.ACTIVE, EntitlementStatus.GRACE_PERIOD} and bool(
            self.expires_at and self.expires_at > timezone.now()
        )


class StoreNotificationEvent(models.Model):
    platform = models.CharField(max_length=20, choices=StorePlatform.choices)
    event_id = models.CharField(max_length=512)
    event_type = models.CharField(max_length=100, blank=True)
    processed = models.BooleanField(default=False)
    raw_payload = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'StoreNotificationEvent'
        constraints = [
            models.UniqueConstraint(fields=['platform', 'event_id'], name='uniq_store_notification_event'),
        ]
