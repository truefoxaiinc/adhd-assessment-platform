import hmac
import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.models import SubscriptionEntitlement
from apps.payments.serializers import (
    AppleNotificationSerializer,
    EntitlementSerializer,
    GoogleNotificationSerializer,
    InAppPurchaseVerificationSerializer,
)
from apps.payments.services import (
    process_apple_notification,
    process_google_rtdn,
    purchase_account_identifiers,
    verify_in_app_purchase,
)
from helpers.exceptions.exceptions import safe_exception_response
from helpers.response import ResponseInfo


logger = logging.getLogger(__name__)


def _purchase_log_context(request, data):
    """Return useful purchase diagnostics without exposing store credentials."""
    token = data.get('purchase_token') or data.get('verification_data') or ''
    return {
        'user_id': getattr(request.user, 'pk', None),
        'platform': data.get('platform'),
        'product_id': data.get('product_id'),
        'purchase_id': data.get('purchase_id'),
        'transaction_id': data.get('transaction_id'),
        'has_verification_data': bool(token),
        'verification_data_length': len(token) if isinstance(token, str) else None,
        'request_fields': sorted(data.keys()),
    }


def _error(message, http_status, errors=None):
    response = ResponseInfo(status=False, status_code=http_status, message=message).response
    if errors:
        response['errors'] = errors
    return Response(response, status=http_status)


class VerifyInAppPurchaseApiView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=['Payments'], request_body=InAppPurchaseVerificationSerializer)
    def post(self, request):
        serializer = InAppPurchaseVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                'In-app purchase request validation failed: context=%s errors=%s',
                _purchase_log_context(request, request.data),
                serializer.errors,
            )
            return _error('Invalid purchase verification request', status.HTTP_400_BAD_REQUEST, serializer.errors)
        try:
            entitlement = verify_in_app_purchase(request.user, serializer.validated_data)
            response = ResponseInfo(message='Purchase verified').response
            response['data'] = EntitlementSerializer(entitlement).data
            return Response(response, status=status.HTTP_200_OK)
        except ValidationError as exc:
            logger.warning(
                'In-app purchase store verification failed: context=%s errors=%s',
                _purchase_log_context(request, serializer.validated_data),
                exc.detail,
            )
            return _error('Purchase verification failed', status.HTTP_400_BAD_REQUEST, exc.detail)
        except ImproperlyConfigured as exc:
            logger.error(
                'In-app purchase service is not configured: context=%s error=%s',
                _purchase_log_context(request, serializer.validated_data),
                exc,
            )
            return _error(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return safe_exception_response(exc, context={'view': self})


class EntitlementApiView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=['Payments'])
    def get(self, request):
        entitlement = SubscriptionEntitlement.objects.filter(user=request.user).first()
        response = ResponseInfo(message='Success').response
        response['data'] = EntitlementSerializer(entitlement).data if entitlement else {
            'verified': False,
            'subscription_status': 'inactive',
            'platform': '',
            'product_id': '',
            'expires_at': None,
        }
        return Response(response)


class PurchaseAccountIdentifiersApiView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=['Payments'])
    def get(self, request):
        response = ResponseInfo(message='Success').response
        response['data'] = purchase_account_identifiers(request.user)
        return Response(response)


class GoogleRtdnApiView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        expected = settings.GOOGLE_RTDN_VERIFICATION_TOKEN
        supplied = request.headers.get('X-Goog-Verification-Token', '')
        if not expected or not hmac.compare_digest(expected, supplied):
            return Response({'received': False}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = GoogleNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'received': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            duplicate = process_google_rtdn(serializer.validated_data)
            return Response({'received': True, 'duplicate': duplicate})
        except ValidationError as exc:
            return Response({'received': False, 'errors': exc.detail}, status=status.HTTP_400_BAD_REQUEST)


class AppleServerNotificationApiView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AppleNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'received': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            duplicate = process_apple_notification(serializer.validated_data['signedPayload'])
            return Response({'received': True, 'duplicate': duplicate})
        except ValidationError as exc:
            return Response({'received': False, 'errors': exc.detail}, status=status.HTTP_400_BAD_REQUEST)
