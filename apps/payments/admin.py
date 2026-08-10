from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.payments.models import StoreNotificationEvent, StorePurchase, SubscriptionEntitlement


@admin.register(StorePurchase)
class StorePurchaseAdmin(ModelAdmin):
    list_display = ('id', 'user', 'platform', 'product_id', 'status', 'expires_at', 'updated_at')
    list_filter = ('platform', 'status', 'environment')
    search_fields = ('user__email', 'store_purchase_id', 'original_transaction_id', 'latest_transaction_id')
    readonly_fields = ('raw_verification_response', 'created_at', 'updated_at')


@admin.register(SubscriptionEntitlement)
class SubscriptionEntitlementAdmin(ModelAdmin):
    list_display = ('id', 'user', 'platform', 'product_id', 'status', 'expires_at', 'updated_at')
    list_filter = ('platform', 'status')
    search_fields = ('user__email', 'product_id')


@admin.register(StoreNotificationEvent)
class StoreNotificationEventAdmin(ModelAdmin):
    list_display = ('id', 'platform', 'event_type', 'processed', 'created_at')
    list_filter = ('platform', 'processed', 'event_type')
    search_fields = ('event_id',)
    readonly_fields = ('raw_payload', 'created_at', 'processed_at')
