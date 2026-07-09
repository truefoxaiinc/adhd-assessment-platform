from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.models import Subscription
from apps.payments.serializers import (
    BillingPortalSessionRequestSerializer,
    CheckoutSessionRequestSerializer,
    SubscriptionSerializer,
)
from apps.payments.services import (
    construct_webhook_event,
    create_billing_portal_session,
    create_checkout_session,
    process_webhook_event,
)
from helpers.exceptions.exceptions import safe_exception_response
from helpers.helper import get_token_user_or_none
from helpers.response import ResponseInfo


def payment_success_page(request):
    return render(
        request,
        'payments/payment_result.html',
        {
            'is_success': True,
            'title': 'Payment successful',
            'message': 'Your payment was completed. You can now return to the ADHD Minder app.',
        },
    )


def payment_cancel_page(request):
    return render(
        request,
        'payments/payment_result.html',
        {
            'is_success': False,
            'title': 'Payment cancelled',
            'message': 'No payment was completed. You can return to the ADHD Minder app and try again.',
        },
    )


class CreateCheckoutSessionApiView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CheckoutSessionRequestSerializer

    @swagger_auto_schema(tags=['Payments'], request_body=CheckoutSessionRequestSerializer)
    def post(self, request):
        response_format = ResponseInfo().response
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            response_format['status'] = False
            response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            response_format['errors'] = serializer.errors
            return Response(response_format, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = get_token_user_or_none(request)
            if not user:
                response_format['status'] = False
                response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
                response_format['message'] = 'Authentication credentials were not provided or are invalid'
                return Response(response_format, status=status.HTTP_401_UNAUTHORIZED)

            data = create_checkout_session(user, **serializer.validated_data)
            response_format['data'] = data
            response_format['message'] = 'Success'
            return Response(response_format, status=status.HTTP_200_OK)
        except ImproperlyConfigured as exc:
            response_format['status'] = False
            response_format['status_code'] = status.HTTP_503_SERVICE_UNAVAILABLE
            response_format['message'] = str(exc)
            return Response(response_format, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return safe_exception_response(exc, context={'view': self})


class SubscriptionApiView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=['Payments'])
    def get(self, request):
        response_format = ResponseInfo().response
        user = get_token_user_or_none(request)
        subscription = Subscription.objects.filter(user=user).first() if user else None
        if not subscription:
            response_format['data'] = {
                'is_active': False,
                'status': '',
                'current_period_start': None,
                'current_period_end': None,
                'cancel_at_period_end': False,
                'stripe_subscription_id': '',
            }
            response_format['message'] = 'Success'
            return Response(response_format, status=status.HTTP_200_OK)

        response_format['data'] = SubscriptionSerializer(subscription).data
        response_format['message'] = 'Success'
        return Response(response_format, status=status.HTTP_200_OK)


class CreateBillingPortalSessionApiView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BillingPortalSessionRequestSerializer

    @swagger_auto_schema(tags=['Payments'], request_body=BillingPortalSessionRequestSerializer)
    def post(self, request):
        response_format = ResponseInfo().response
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            response_format['status'] = False
            response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            response_format['errors'] = serializer.errors
            return Response(response_format, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = get_token_user_or_none(request)
            if not user:
                response_format['status'] = False
                response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
                response_format['message'] = 'Authentication credentials were not provided or are invalid'
                return Response(response_format, status=status.HTTP_401_UNAUTHORIZED)

            response_format['data'] = create_billing_portal_session(user, **serializer.validated_data)
            response_format['message'] = 'Success'
            return Response(response_format, status=status.HTTP_200_OK)
        except ImproperlyConfigured as exc:
            response_format['status'] = False
            response_format['status_code'] = status.HTTP_503_SERVICE_UNAVAILABLE
            response_format['message'] = str(exc)
            return Response(response_format, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return safe_exception_response(exc, context={'view': self})


class StripeWebhookApiView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @swagger_auto_schema(tags=['Payments'])
    @csrf_exempt
    def post(self, request):
        signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        try:
            event = construct_webhook_event(request.body, signature)
            result = process_webhook_event(event)
            return Response({'received': True, **result}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'received': False, 'message': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            if exc.__class__.__name__ == 'SignatureVerificationError':
                return Response({'received': False, 'message': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
            return safe_exception_response(exc, context={'view': self})
