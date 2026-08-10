from rest_framework import serializers

from apps.payments.models import StorePlatform, SubscriptionEntitlement


class InAppPurchaseVerificationSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=StorePlatform.values)
    product_id = serializers.CharField(max_length=255)
    purchase_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    transaction_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    purchase_token = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    verification_data = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    verification_source = serializers.CharField(max_length=50, required=False, allow_blank=True)
    transaction_date = serializers.CharField(required=False, allow_blank=True)
    is_restore = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs['platform'] == StorePlatform.ANDROID:
            token = attrs.get('purchase_token') or attrs.get('verification_data')
            if not token:
                raise serializers.ValidationError({'purchase_token': 'Google Play purchase token is required.'})
            attrs['purchase_token'] = token
        else:
            transaction_id = attrs.get('transaction_id') or attrs.get('purchase_id')
            signed_data = attrs.get('verification_data')
            if not transaction_id and not signed_data:
                raise serializers.ValidationError({'transaction_id': 'Apple transaction ID or signed transaction is required.'})
            attrs['transaction_id'] = transaction_id or ''
        return attrs


class EntitlementSerializer(serializers.ModelSerializer):
    verified = serializers.SerializerMethodField()
    subscription_status = serializers.CharField(source='status')

    class Meta:
        model = SubscriptionEntitlement
        fields = ['verified', 'subscription_status', 'platform', 'product_id', 'expires_at']

    def get_verified(self, instance):
        return instance.is_active


class AppleNotificationSerializer(serializers.Serializer):
    signedPayload = serializers.CharField()


class GoogleNotificationSerializer(serializers.Serializer):
    message = serializers.DictField()
    subscription = serializers.CharField(required=False, allow_blank=True)
