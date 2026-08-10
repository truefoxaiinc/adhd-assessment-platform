from django.utils import timezone

from apps.payments.models import EntitlementStatus, SubscriptionEntitlement


def user_has_active_subscription(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return SubscriptionEntitlement.objects.filter(
        user=user,
        status__in=[EntitlementStatus.ACTIVE, EntitlementStatus.GRACE_PERIOD],
        expires_at__gt=timezone.now(),
    ).exists()
