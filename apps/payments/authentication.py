import hashlib
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from apps.payments.models import EntitlementStatus, GuestEntitlement


class GuestEntitlementAuthentication(BaseAuthentication):
    """Authenticate opaque guest tokens while leaving dotted JWTs to SimpleJWT."""
    def authenticate(self, request):
        header_token = request.headers.get('X-Entitlement-Token', '').strip()
        auth = get_authorization_header(request).split()
        bearer = auth[1].decode(errors='ignore') if len(auth) == 2 and auth[0].lower() == b'bearer' else ''
        token = header_token or bearer
        if not token:
            return None
        guest = GuestEntitlement.objects.select_related('backing_user', 'purchase').filter(
            token_digest=hashlib.sha256(token.encode()).hexdigest()
        ).first()
        if guest is None:
            if not header_token and token.count('.') == 2:
                return None
            raise AuthenticationFailed('Invalid entitlement token.')
        if not guest.is_token_active:
            raise AuthenticationFailed('Entitlement token has expired or was revoked.')
        purchase = guest.purchase
        if purchase.status not in {EntitlementStatus.ACTIVE, EntitlementStatus.GRACE_PERIOD} or not purchase.expires_at or purchase.expires_at <= timezone.now():
            raise PermissionDenied('The entitlement is inactive.')
        request.guest_entitlement = guest
        return guest.backing_user, guest

    def authenticate_header(self, request):
        return 'Bearer'
