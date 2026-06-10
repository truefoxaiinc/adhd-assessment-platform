from rest_framework import serializers
from apps.users.models import  Users
from django.utils.translation import gettext_lazy as _
from helpers.helper import get_object_or_none


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        try:
            Users.objects.get(email=value)
        except Users.DoesNotExist:
            raise serializers.ValidationError("No account found with this email")
        return value


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

    def validate_refresh(self, value):
        if not value:
            raise serializers.ValidationError("Refresh token is required")
        return value