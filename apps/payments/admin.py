from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.payments.models import PaymentInvoice, StripeCustomer, StripeWebhookEvent, Subscription


@admin.register(StripeCustomer)
class StripeCustomerAdmin(ModelAdmin):
    list_display = ('id', 'user', 'stripe_customer_id', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'stripe_customer_id')
    readonly_fields = ('stripe_customer_id', 'created_at', 'updated_at')
    raw_id_fields = ('user',)


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'status',
        'stripe_customer_id',
        'stripe_subscription_id',
        'current_period_end',
        'cancel_at_period_end',
        'created_at',
    )
    list_filter = ('status', 'cancel_at_period_end', 'created_at')
    search_fields = ('user__email', 'user__username', 'stripe_customer_id', 'stripe_subscription_id')
    readonly_fields = ('stripe_customer_id', 'stripe_subscription_id', 'created_at', 'updated_at')
    raw_id_fields = ('user',)


@admin.register(PaymentInvoice)
class PaymentInvoiceAdmin(ModelAdmin):
    list_display = ('id', 'user', 'status', 'stripe_invoice_id', 'stripe_subscription_id', 'amount_paid', 'currency', 'paid_at', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('user__email', 'user__username', 'stripe_invoice_id', 'stripe_subscription_id')
    readonly_fields = ('stripe_invoice_id', 'stripe_subscription_id', 'hosted_invoice_url', 'invoice_pdf', 'created_at')
    raw_id_fields = ('user',)


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(ModelAdmin):
    list_display = ('id', 'stripe_event_id', 'event_type', 'processed', 'processed_at', 'created_at')
    list_filter = ('event_type', 'processed', 'created_at')
    search_fields = ('stripe_event_id', 'event_type')
    readonly_fields = ('stripe_event_id', 'event_type', 'processed', 'processed_at', 'raw_payload', 'error', 'created_at')
