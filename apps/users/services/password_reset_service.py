from django.utils import timezone
from django.db import transaction
from django.conf import settings
from rest_framework import serializers

from apps.users.models import PasswordResetOTP, Users
from apps.users.selectors import (
    get_latest_pending_password_reset,
    get_user_by_email,
    iter_active_verified_password_resets,
)
from apps.users.tasks import send_otp_email_task


class PasswordResetService:
    @staticmethod
    def request_reset(email):
        user = get_user_by_email(email)
        if not user:
            raise serializers.ValidationError({"email": "No user found with this email address"})

        _, otp = PasswordResetOTP.create_for_user(user)
        transaction.on_commit(lambda: PasswordResetService.send_reset_otp(email, otp))

    @staticmethod
    def send_reset_otp(email, otp):
        if not settings.PASSWORD_RESET_EMAIL_ASYNC:
            send_otp_email_task(email, otp)
            return

        try:
            send_otp_email_task.delay(email, otp)
        except Exception:
            send_otp_email_task(email, otp)

    @staticmethod
    def verify_otp(email, otp):
        user = get_user_by_email(email)
        if not user:
            raise serializers.ValidationError({"email": "No user found with this email address"})

        otp_instance = get_latest_pending_password_reset(user)
        if not otp_instance or not otp_instance.verify_otp(otp):
            raise serializers.ValidationError({"otp": "Invalid OTP"})

        if otp_instance.expires_at < timezone.now():
            raise serializers.ValidationError({"otp": "OTP has expired"})

        return otp_instance.issue_reset_token()

    @staticmethod
    def change_password(email, reset_token, password):
        user = get_user_by_email(email)
        if not user:
            raise serializers.ValidationError({"email": "No user found with this email address"})

        reset_instance = None
        reset_candidates = iter_active_verified_password_resets(user, timezone.now())

        for candidate in reset_candidates:
            if candidate.verify_reset_token(reset_token):
                reset_instance = candidate
                break

        if reset_instance is None:
            raise serializers.ValidationError({"reset_token": "Invalid or expired reset token"})

        user.set_password(password)
        user.save()
        reset_instance.mark_used()
        return user
