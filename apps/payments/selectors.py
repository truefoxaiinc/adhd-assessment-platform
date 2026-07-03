from django.utils import timezone

from apps.payments.models import Subscription, SubscriptionStatus


def user_has_active_subscription(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    return Subscription.objects.filter(
        user=user,
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
        current_period_end__gte=timezone.now(),
    ).exists()
