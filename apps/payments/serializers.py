from rest_framework import serializers

from apps.payments.models import Subscription


class CheckoutSessionRequestSerializer(serializers.Serializer):
    success_url = serializers.URLField(required=False, allow_blank=True)
    cancel_url = serializers.URLField(required=False, allow_blank=True)


class BillingPortalSessionRequestSerializer(serializers.Serializer):
    return_url = serializers.URLField(required=False, allow_blank=True)


class SubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'is_active',
            'status',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'stripe_subscription_id',
        ]
