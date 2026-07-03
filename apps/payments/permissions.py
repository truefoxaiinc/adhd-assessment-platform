from rest_framework.permissions import BasePermission

from apps.payments.selectors import user_has_active_subscription


class HasActiveSubscription(BasePermission):
    message = 'An active subscription is required to access this resource.'

    def has_permission(self, request, view):
        return user_has_active_subscription(request.user)
