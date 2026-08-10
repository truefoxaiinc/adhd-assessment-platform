from rest_framework import serializers
from django.db import transaction

from apps.notifications.models import PushDevice, PushPlatform


class RegisterPushDeviceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, trim_whitespace=True)
    platform = serializers.ChoiceField(choices=PushPlatform.values)
    device_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        token = validated_data['token']
        platform = validated_data['platform']
        device_id = validated_data.get('device_id', '')

        if device_id:
            PushDevice.objects.filter(
                user=user,
                platform=platform,
                device_id=device_id,
            ).exclude(token=token).update(is_active=False)

        device, created = PushDevice.objects.update_or_create(
            token=token,
            defaults={
                'user': user,
                'platform': platform,
                'device_id': device_id,
                'is_active': True,
            },
        )
        device.was_created = created
        return device


class UnregisterPushDeviceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, trim_whitespace=True)


class PushDeviceResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = ['id', 'platform', 'device_id', 'is_active', 'last_seen_at', 'created_at']
