from apps.users.models import PasswordResetOTP, Users


def get_user_by_email(email):
    if not email:
        return None
    return Users.objects.filter(email=email).first()


def get_latest_pending_password_reset(user):
    return PasswordResetOTP.objects.filter(user=user, is_used=False).order_by('-id').first()


def iter_active_verified_password_resets(user, now):
    return PasswordResetOTP.objects.filter(
        user=user,
        is_verified=True,
        is_used=False,
        expires_at__gte=now,
    ).order_by('-id')
